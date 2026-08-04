from __future__ import annotations

import json
import re
from typing import Any, Callable

from app.graphs.support import messages, post_fields
from app.services.huggingface_service import HuggingFaceService

POST_DATA_KEYS = (
    "topic",
    "platform",
    "target_audience",
    "tone_of_voice",
    "additional_context",
    "image_context",
)

EXTRACT_SYSTEM = (
    "You extract marketing post Steckbrief fields from a German or English chat message. "
    "Return ONLY a JSON object with any of these optional keys: "
    "topic, platform, target_audience, tone_of_voice, additional_context, image_context. "
    "Use free-form values when the user states them (e.g. tone_of_voice may be "
    "'angeberisch'). For platform ONLY use one of: linkedin, instagram, x, blog, "
    "tiktok, facebook — never invent platform from unrelated questions. "
    "Put the marketing subject in topic. Put visual motif / what should appear in the "
    "image into image_context (people, objects, background, flags, setting) — do not "
    "merge image motif into topic when both are stated. "
    "If the user asks about memory/RAG/Gedaechtnis content, return {}. "
    "If the user asks to search the web/internet or about current news/events/trends "
    "(without asking to write a marketing post), return {}. "
    "Omit keys that are not clearly stated as brief facts. No markdown."
)

COMPOSE_SYSTEM = (
    "You are a helpful German marketing manager agent chatting with a user. "
    "Write ONE short natural reply in German (2-5 sentences). "
    "Reply EXCLUSIVELY in German (Hochdeutsch). Never use Chinese, English paragraphs, "
    "or any other language — not even mid-sentence. If the source mixes languages, "
    "answer only in German about the German-relevant content. "
    "Acknowledge what you learned, ask at most one clear next question if needed, "
    "and stay concrete. Do not mention that you are an AI. Do not use markdown fences. "
    "Never repeat the same sentence or question twice in one reply."
)

COMPOSE_WEB_SYSTEM = (
    "You are a German marketing manager agent. The user asked for web research. "
    "Write ONE short German answer (3-6 sentences) that SUMMARIZES the search snippets. "
    "Reply EXCLUSIVELY in German. Never use Chinese or other non-German languages. "
    "Synthesize the key facts in your own words; do not paste the raw numbered result list. "
    "Stay faithful to the snippets — do not invent facts. "
    "Do not ask for Steckbrief fields, platform, audience, tone, or whether to generate a post. "
    "Do not use markdown fences. Never repeat the same sentence twice."
)

COMPOSE_TEXT_SYSTEM = (
    "You are a German marketing text agent chatting with a user. "
    "Write ONE short natural reply in German (2-4 sentences). "
    "Reply EXCLUSIVELY in German. Never use Chinese or other languages. "
    "Acknowledge the refine request and briefly describe what you changed in the copy. "
    "Do not paste the full marketing text. Do not mention that you are an AI. "
    "No markdown fences. Never repeat the same sentence twice."
)

COMPOSE_IMAGE_SYSTEM = (
    "You are a German marketing image agent chatting with a user. "
    "Write ONE short natural reply in German (2-4 sentences). "
    "Reply EXCLUSIVELY in German. Never use Chinese or other languages. "
    "Acknowledge the image request and briefly say how you used the current post image "
    "and/or reference image if mentioned in the situation. "
    "Do not paste the full image prompt. Do not mention that you are an AI. "
    "No markdown fences. Never repeat the same sentence twice."
)


def _parse_json_object(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _normalize_platform(value: str) -> str | None:
    alias = post_fields.extract_platform(value)
    if alias:
        return alias
    lowered = value.strip().lower()
    return post_fields.PLATFORM_ALIASES.get(lowered)


def _clean_llm_updates(data: dict[str, Any], post: dict[str, Any]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for key in POST_DATA_KEYS:
        if key not in data or data[key] is None:
            continue
        value = str(data[key]).strip()
        if len(value) < post_fields.FIELD_MIN_LENGTH:
            continue
        if key == "platform":
            value = _normalize_platform(value)
            if not value:
                continue
        max_len = post_fields.FIELD_MAX_LENGTH.get(key, 300)
        value = value[:max_len]
        current = post.get(key)
        if key in ("topic", "target_audience", "additional_context") and current:
            continue
        if value != current:
            updates[key] = value
    return updates


def extract_post_data_with_llm(
    message: str,
    post: dict[str, Any],
    hf: HuggingFaceService | None,
) -> dict[str, Any]:
    """Prefer LLM extraction; always merge with regex/alias fallback."""
    if (
        post_fields.is_memory_inquiry(message)
        or post_fields.is_memory_store_request(message)
        or post_fields.is_post_status_inquiry(message)
        or (post_fields.is_web_inquiry(message) and not post_fields.wants_generation(message))
        or (post_fields.is_question_message(message) and not post_fields.wants_generation(message))
    ):
        return {}

    regex_updates = post_fields.extract_fields(message, post)
    if hf is None:
        return regex_updates

    brief_snapshot = {key: post.get(key) for key in POST_DATA_KEYS}
    awaiting = post.get(post_fields.AWAITING_FIELD_KEY)
    user_prompt = (
        f"Current Steckbrief: {json.dumps(brief_snapshot, ensure_ascii=False)}\n"
        f"Awaiting field: {awaiting or 'none'}\n"
        f"User message: {message}"
    )
    try:
        raw = hf.generate(system_prompt=EXTRACT_SYSTEM, user_prompt=user_prompt, max_tokens=300)
        parsed = _parse_json_object(raw)
        if not parsed:
            return regex_updates
        llm_updates = _clean_llm_updates(parsed, post)
    except Exception:
        return regex_updates

    merged = dict(llm_updates)
    for key, value in regex_updates.items():
        merged.setdefault(key, value)
    return merged


def compose_manager_reply(
    *,
    hf: HuggingFaceService | None,
    fallback: str,
    situation: str,
    user_message: str,
    post: dict[str, Any] | None,
    post_data_updates: dict[str, Any] | None = None,
    next_question: str | None = None,
    artifact_summary: str | None = None,
) -> str:
    if hf is None:
        return fallback

    brief = post_fields.post_data_summary(post) if post else "no post"
    user_prompt = (
        f"Situation: {situation}\n"
        f"User message: {user_message}\n"
        f"Steckbrief status: {brief}\n"
        f"Just saved updates: {json.dumps(post_data_updates or {}, ensure_ascii=False)}\n"
        f"Suggested next question (optional): {next_question or 'none'}\n"
        f"Artifact summary: {artifact_summary or 'none'}\n"
        "Write the assistant reply now."
    )
    try:
        reply = hf.generate(system_prompt=COMPOSE_SYSTEM, user_prompt=user_prompt, max_tokens=280).strip()
    except Exception:
        return fallback
    if len(reply) < 12:
        return fallback
    return _ensure_german_reply(_dedupe_repeated_sentences(reply), fallback)


def compose_web_summary(
    *,
    hf: HuggingFaceService | None,
    user_message: str,
    web_context: str,
) -> str:
    """Summarize web_search snippets for chat; never dump only the raw result list."""
    snippets = (web_context or "").strip()
    fallback = _fallback_web_summary(user_message, snippets)
    if hf is None or not snippets:
        return fallback

    user_prompt = (
        f"User question: {user_message}\n\n"
        f"Web search snippets:\n{snippets[:1600]}\n\n"
        "Summarize these snippets as the full assistant reply now."
    )
    try:
        reply = hf.generate(system_prompt=COMPOSE_WEB_SYSTEM, user_prompt=user_prompt, max_tokens=320).strip()
    except Exception:
        return fallback
    if len(reply) < 20:
        return fallback
    # Prefer summary over a reply that mostly re-lists numbered hits.
    numbered = sum(1 for line in reply.splitlines() if re.match(r"^\s*\d+\.\s+", line))
    if numbered >= 2 and "http" in reply.lower():
        return fallback
    return _ensure_german_reply(_dedupe_repeated_sentences(reply), fallback)


def _fallback_web_summary(user_message: str, snippets: str) -> str:
    """Readable short summary without HF — not a raw dump of the tool observation."""
    if not snippets.strip():
        return (
            "Die Websuche hat gerade keine brauchbaren Treffer geliefert. "
            "Formuliere die Frage gern konkreter oder versuche es gleich noch einmal."
        )
    points: list[str] = []
    for line in snippets.splitlines():
        cleaned = re.sub(r"^\s*\d+\.\s*", "", line).strip()
        cleaned = re.sub(r"\s*\(https?://[^)]+\)\s*$", "", cleaned).strip()
        if ":" in cleaned:
            title, _, body = cleaned.partition(":")
            piece = f"{title.strip()}: {body.strip()}" if body.strip() else title.strip()
        else:
            piece = cleaned
        if len(piece) >= 12:
            points.append(piece[:220])
        if len(points) >= 3:
            break
    if not points:
        return f"Zur Frage „{user_message.strip()[:80]}“ habe ich im Web nur unklare Treffer gefunden."
    bullets = "\n".join(f"- {p}" for p in points)
    return (
        f"Kurz zusammengefasst zu deiner Web-Frage:\n{bullets}\n\n"
        "Das sind die Kernpunkte aus den aktuellen Suchtreffern."
    )


def compose_specialist_reply(
    *,
    role: str,
    hf: HuggingFaceService | None,
    fallback: str,
    situation: str,
    user_message: str,
    post: dict[str, Any] | None,
    artifact_summary: str | None = None,
) -> str:
    """LLM ack for text/image agent chats; falls back to static headline strings."""
    if hf is None:
        return fallback

    system = COMPOSE_IMAGE_SYSTEM if role == "image" else COMPOSE_TEXT_SYSTEM
    brief = post_fields.post_data_summary(post) if post else "no post"
    user_prompt = (
        f"Situation: {situation}\n"
        f"User message: {user_message}\n"
        f"Steckbrief status: {brief}\n"
        f"Artifact summary: {artifact_summary or 'none'}\n"
        "Write the assistant reply now."
    )
    try:
        reply = hf.generate(system_prompt=system, user_prompt=user_prompt, max_tokens=220).strip()
    except Exception:
        return fallback
    if len(reply) < 12:
        return fallback
    return _ensure_german_reply(_dedupe_repeated_sentences(reply), fallback)


_CJK_OR_NON_LATIN_RE = re.compile(
    r"[\u0400-\u04FF\u0600-\u06FF\u3040-\u30FF\u3400-\u9FFF\uAC00-\uD7AF\uF900-\uFAFF]"
)


def _ensure_german_reply(reply: str, fallback: str) -> str:
    """Drop model output that drifted into Chinese/other scripts; keep German fallback."""
    if _CJK_OR_NON_LATIN_RE.search(reply or ""):
        return fallback
    return reply


def _dedupe_repeated_sentences(text: str) -> str:
    """Collapse exact consecutive duplicate sentences the model sometimes emits twice."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    cleaned: list[str] = []
    for part in parts:
        normalized = re.sub(r"\s+", " ", part).strip().casefold()
        if cleaned and re.sub(r"\s+", " ", cleaned[-1]).strip().casefold() == normalized:
            continue
        cleaned.append(part.strip())
    return " ".join(p for p in cleaned if p)


def welcome_message(title: str, hf: HuggingFaceService | None = None) -> str:
    fallback = (
        f"Hallo! Ich sehe, du moechtest einen Post zu „{title}“ erstellen. "
        "Erzaehl mir gern, worum es inhaltlich gehen soll, fuer welche Plattform "
        "der Post gedacht ist und welche Zielgruppe sowie Tonalitaet du dir vorstellst. "
        "Danach lege ich mit Text und Bild los."
    )
    if hf is None:
        return fallback

    system = (
        "You are a friendly German marketing manager agent. "
        "Write ONE short welcome message (3-5 sentences) in German. "
        "Reply EXCLUSIVELY in German. Never use Chinese or other languages. "
        "Greet the user, mention the post title, and invite them to share topic, "
        "platform, audience and tone. No markdown."
    )
    try:
        reply = hf.generate(
            system_prompt=system,
            user_prompt=f"Post title: {title}",
            max_tokens=220,
        ).strip()
    except Exception:
        return fallback
    if len(reply) < 20 or title.casefold() not in reply.casefold():
        return fallback
    return _ensure_german_reply(reply, fallback)


def try_hf(hf_factory: Callable[[], HuggingFaceService] | None) -> HuggingFaceService | None:
    if hf_factory is None:
        return None
    try:
        return hf_factory()
    except Exception:
        return None
