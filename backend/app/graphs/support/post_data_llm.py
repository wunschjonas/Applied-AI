from __future__ import annotations

import json
import re
from typing import Any, Callable

from app.graphs.support import messages, post_fields
from app.graphs.support.language import (
    GERMAN_OUTPUT_RULE,
    contains_non_german_script,
)
from app.services.huggingface_service import HuggingFaceService

POST_DATA_KEYS = (
    "topic",
    "platform",
    "target_audience",
    "tone_of_voice",
    "text_context",
    "text_length",
    "image_context",
    "image_style",
)

EXTRACT_SYSTEM = (
    "You extract marketing post Steckbrief fields from a German or English chat message. "
    "Return ONLY a JSON object with any of these optional keys: "
    "topic, platform, target_audience, tone_of_voice, text_context, text_length, "
    "image_context, image_style. "
    "Use free-form values when the user states them (e.g. tone_of_voice may be "
    "'angeberisch'). For platform ONLY use one of: linkedin, instagram, x, blog, "
    "tiktok, facebook — never invent platform from unrelated questions. "
    "Put the marketing subject in topic. Put what the marketing text should say in "
    "text_context. Put desired text length in text_length (e.g. kurz/mittel/lang). "
    "Put visual motif / what should appear in the image into image_context "
    "(people, objects, background, flags, setting). Put visual style into image_style "
    "(e.g. fotorealistisch, illustration). Do not merge image motif into topic when both "
    "are stated. "
    "If text_context is already set in Current Steckbrief and the user adds more content "
    "(e.g. 'zusätzlich', 'außerdem', 'auch noch', 'ergänze'), return text_context as the "
    "FULL combined brief: keep the existing points and append the new ones. "
    "Never return only the addition when prior text_context exists. "
    "If the user asks about memory/RAG/Gedaechtnis content, return {}. "
    "If the user explicitly asks to search the web/internet "
    "(without asking to write a marketing post), return {}. "
    "Omit keys that are not clearly stated as brief facts. No markdown."
)

COMPOSE_SYSTEM = (
    "You are a helpful German marketing manager agent chatting with a user. "
    "Write ONE short natural reply in German (2-5 sentences). "
    f"{GERMAN_OUTPUT_RULE} "
    "If the source mixes languages, answer only in German about the German-relevant content. "
    "Acknowledge what you learned, ask at most one clear next question if needed, "
    "and stay concrete. Do not mention that you are an AI. Do not use markdown fences. "
    "Never repeat the same sentence or question twice in one reply. "
    "When the situation says generation finished: do NOT invent or paste marketing copy, "
    "captions, image prompts, or long quotes — only confirm readiness and where to look."
)

COMPOSE_WEB_SYSTEM = (
    "You are a German marketing manager agent. The user asked for web research. "
    "Write ONE short German answer (3-6 sentences) that SUMMARIZES the search snippets. "
    f"{GERMAN_OUTPUT_RULE} "
    "Synthesize the key facts in your own words; do not paste the raw numbered result list. "
    "Stay faithful to the snippets — do not invent facts. "
    "Do not ask for Steckbrief fields, platform, audience, tone, or whether to generate a post. "
    "Do not use markdown fences. Never repeat the same sentence twice."
)

COMPOSE_TEXT_SYSTEM = (
    "You are a German marketing text agent chatting with a user. "
    "Write ONE short natural reply in German (2-4 sentences). "
    f"{GERMAN_OUTPUT_RULE} "
    "Speak as one agent: use ich/mir, never uns/unser. "
    "Acknowledge the refine request and briefly describe what you changed in the copy. "
    "Do not paste the full marketing text. Do not mention that you are an AI. "
    "No markdown fences. Never repeat the same sentence twice."
)

COMPOSE_IMAGE_SYSTEM = (
    "You are a German marketing image agent chatting with a user. "
    "Write ONE short natural reply in German (2-4 sentences). "
    f"{GERMAN_OUTPUT_RULE} "
    "Speak as one agent: use ich/mir, never uns/unser. "
    "Acknowledge the image refine request and briefly say what you changed visually. "
    "Do not paste the full image prompt. Do not mention that you are an AI. "
    "No markdown fences. Never repeat the same sentence twice."
)

COMPOSE_TEXT_FIRST_SYSTEM = (
    "You are a German marketing text agent. The marketing text was just created "
    "from the post Steckbrief (first generation, not a refine). "
    "Write ONE short natural reply in German (2-3 sentences). "
    f"{GERMAN_OUTPUT_RULE} "
    "Speak as one agent: ich/mir, never uns/unser. "
    "Say that you created the text from the post info, ask how they like it and "
    "what they want to change. Do not paste the marketing text. Do not invent "
    "new topics. No markdown. Never repeat the same sentence twice."
)

COMPOSE_IMAGE_FIRST_SYSTEM = (
    "You are a German marketing image agent. The image was just created "
    "from the post Steckbrief (first generation, not a refine). "
    "Write ONE short natural reply in German (2-3 sentences). "
    f"{GERMAN_OUTPUT_RULE} "
    "Speak as one agent: ich/mir, never uns/unser. "
    "Say that you created an image from the post info, ask how they like it and "
    "what they want to change. Do NOT talk about writing marketing text. "
    "Do not paste the image prompt. Do not invent new topics. No markdown. "
    "Never repeat the same sentence twice."
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


_TEXT_CONTEXT_APPEND_MARKERS = (
    "zusätzlich",
    "zusaetzlich",
    "außerdem",
    "ausserdem",
    "darüber hinaus",
    "daruber hinaus",
    "auch noch",
    "ergänz",
    "erganz",
    "und auch",
    "plus ",
)


def _message_extends_text_context(message: str) -> bool:
    lowered = (message or "").lower()
    return any(marker in lowered for marker in _TEXT_CONTEXT_APPEND_MARKERS)


def _merge_text_context(current: str, incoming: str, message: str) -> str | None:
    """Combine existing + new text_context when the user extends the brief."""
    current = (current or "").strip()
    incoming = (incoming or "").strip()
    if not incoming:
        return None
    if not current:
        return incoming
    if incoming == current:
        return None
    # LLM already returned a full merge that keeps the prior content.
    if current[:80] in incoming or current in incoming:
        return incoming
    # Incoming is only a subset of what we already have.
    if incoming in current:
        return None
    if _message_extends_text_context(message):
        return f"{current.rstrip()} {incoming}".strip()
    return None


def _clean_llm_updates(
    data: dict[str, Any],
    post: dict[str, Any],
    message: str = "",
) -> dict[str, Any]:
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
        current = str(post.get(key) or "").strip()
        if key in ("topic", "target_audience") and current:
            continue
        if key == "text_context" and current:
            merged = _merge_text_context(current, value, message)
            if not merged:
                continue
            value = merged[:max_len]
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
        llm_updates = _clean_llm_updates(parsed, post, message)
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
    first_generation: bool = False,
) -> str:
    """LLM ack for text/image agent chats; falls back to static headline strings."""
    if hf is None:
        return fallback

    if first_generation:
        system = COMPOSE_IMAGE_FIRST_SYSTEM if role == "image" else COMPOSE_TEXT_FIRST_SYSTEM
        title = (post or {}).get("title") or (post or {}).get("topic") or "dem Post"
        user_prompt = (
            f"Situation: {situation}\n"
            f"Post title/topic: {title}\n"
            f"Artifact summary: {artifact_summary or 'none'}\n"
            "Write the assistant reply now. Do not treat any manager briefing as a user chat."
        )
    else:
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
        reply = hf.generate(
            system_prompt=system,
            user_prompt=user_prompt,
            max_tokens=220,
            temperature=0.4,
        ).strip()
    except Exception:
        return fallback
    if len(reply) < 12:
        return fallback
    reply = _ensure_german_reply(_dedupe_repeated_sentences(reply), fallback)
    if _has_plural_team_voice(reply):
        return fallback
    if first_generation and role == "image" and _looks_like_text_agent_reply(reply):
        return fallback
    return reply


def _has_plural_team_voice(text: str) -> bool:
    lowered = (text or "").casefold()
    return any(
        token in lowered
        for token in (
            " unser ",
            " unsere ",
            " unserem ",
            " unseren ",
            " mit uns",
            "teile uns",
            "erzähl uns",
            "erzaehl uns",
            "willkommen bei unserem",
        )
    ) or lowered.startswith("unser ")


def _looks_like_text_agent_reply(text: str) -> bool:
    lowered = (text or "").casefold()
    return any(
        token in lowered
        for token in (
            "den text",
            "marketing-text",
            "marketingtext",
            "den post text",
            "text ausführlich",
            "text ausfuehrlich",
            "caption",
        )
    )


def _ensure_german_reply(reply: str, fallback: str) -> str:
    """Drop model output that drifted into Chinese/other scripts; keep German fallback."""
    if contains_non_german_script(reply):
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
        f"Ich sehe, du willst einen Post zum Thema „{title}“ erstellen. "
        "Erzähl mir bitte, für welche Plattform er gedacht ist, wen du ansprechen "
        "möchtest und welche Tonalität passen soll."
    )
    if hf is None:
        return fallback

    system = (
        "You are a single German marketing manager agent (not a team). "
        "Write ONE short welcome message (2-4 sentences) in German. "
        f"{GERMAN_OUTPUT_RULE} "
        "Always use first person singular: ich/mir — never uns/unser/unsere "
        "or 'Willkommen bei unserem Post'. "
        "Open by noticing the user wants to create a post about the given title only. "
        "Do not invent extra domains, products, or topics beyond that title. "
        "Then ask them (to you: mir) for platform, target audience and tone. "
        "Do NOT ask for a content sketch, Skizze, Skizzenbild, or draft of the post body. "
        "Vary the wording naturally. No markdown."
    )
    try:
        reply = hf.generate(
            system_prompt=system,
            user_prompt=f"Post title (use exactly this topic, nothing else): {title}",
            max_tokens=220,
            temperature=0.55,
        ).strip()
    except Exception:
        return fallback
    if len(reply) < 20 or title.casefold() not in reply.casefold():
        return fallback
    reply = _ensure_german_reply(_dedupe_repeated_sentences(reply), fallback)
    if _has_plural_team_voice(reply):
        return fallback
    lowered = reply.casefold()
    if any(
        marker in lowered
        for marker in ("skizzenbild", "skizze", "inhalt skizz", "kurz den inhalt")
    ):
        return fallback
    return reply


INTENT_LABELS = frozenset(
    {
        "clarification_needed",
        "field_briefing",
        "text_only",
        "image_only",
        "text_and_image",
        "web_inquiry",
        "memory_inquiry",
        "memory_store",
        "post_status_inquiry",
    }
)

INTENT_CLASSIFY_SYSTEM = (
    "You classify the user's intent for a German marketing multi-agent manager. "
    "Return ONLY a JSON object: {\"label\": \"...\", \"decision\": \"short reason\"}. "
    "Allowed label values:\n"
    "- field_briefing: user fills Steckbrief fields (Thema/Plattform/Zielgruppe/Tonalität/"
    "Textcontext/Bildmotiv/…) without asking to generate or research\n"
    "- text_only: user asks to create/write only the marketing text\n"
    "- image_only: user asks to create only the image/visual\n"
    "- text_and_image: user asks to create text and image (or a full post)\n"
    "- web_inquiry: user wants public/web facts or an internet search (not writing a post)\n"
    "- memory_inquiry: user asks what is in RAG/memory/Gedächtnis\n"
    "- memory_store: user asks to remember/save a fact\n"
    "- post_status_inquiry: user asks what is already set on the current post/brief\n"
    "- clarification_needed: unclear whether to generate text, image, both, or just chat\n"
    "Rules:\n"
    "- Interpret the whole message; do not key off single topical words like aktuell/heute/trend.\n"
    "- 'Textcontext: … aktuelle Saison …' while filling fields = field_briefing, NOT web_inquiry.\n"
    "- Only web_inquiry when they clearly want research/search, not when describing post content.\n"
    "- Generate verbs (erstelle/schreibe/generiere) without nur-text/nur-bild → text_and_image.\n"
    "No markdown."
)


def classify_manager_intent_with_llm(
    *,
    hf: HuggingFaceService | None,
    user_message: str,
    post: dict[str, Any] | None = None,
) -> dict[str, str] | None:
    """Return {label, decision} from HF, or None if unavailable/invalid."""
    if hf is None or not (user_message or "").strip():
        return None
    post = post or {}
    snapshot = {
        "awaiting_field": post.get(post_fields.AWAITING_FIELD_KEY),
        "topic": post.get("topic"),
        "platform": post.get("platform"),
        "missing": post_fields.missing_fields(post) if post else [],
    }
    user_prompt = (
        f"User message:\n{user_message.strip()}\n\n"
        f"Post snapshot:\n{json.dumps(snapshot, ensure_ascii=False)}\n\n"
        "Classify intent. JSON only."
    )
    try:
        raw = hf.generate(
            system_prompt=INTENT_CLASSIFY_SYSTEM,
            user_prompt=user_prompt,
            max_tokens=120,
            temperature=0.1,
        )
    except Exception:
        return None
    data = _parse_json_object(raw or "")
    if not data:
        return None
    label = str(data.get("label") or "").strip().lower()
    if label not in INTENT_LABELS:
        return None
    if label == "field_briefing":
        label = "clarification_needed"
    decision = str(data.get("decision") or "").strip() or f"LLM classified as {label}."
    return {"label": label, "decision": decision}


def try_hf(hf_factory: Callable[[], HuggingFaceService] | None) -> HuggingFaceService | None:
    if hf_factory is None:
        return None
    try:
        return hf_factory()
    except Exception:
        return None
