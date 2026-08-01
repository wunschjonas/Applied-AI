from __future__ import annotations

import json
import re
from typing import Any, Callable

from app.graphs.support import messages, post_fields
from app.services.huggingface_service import HuggingFaceService

BRIEF_KEYS = ("topic", "platform", "target_audience", "tone_of_voice", "additional_context")

EXTRACT_SYSTEM = (
    "You extract marketing post brief fields from a German or English chat message. "
    "Return ONLY a JSON object with any of these optional keys: "
    "topic, platform, target_audience, tone_of_voice, additional_context. "
    "Use free-form values when the user states them (e.g. tone_of_voice may be "
    "'angeberisch'). For platform prefer one of: linkedin, instagram, x, blog, "
    "tiktok, facebook when clear. Omit keys that are not mentioned. No markdown."
)

COMPOSE_SYSTEM = (
    "You are a helpful German marketing manager agent chatting with a user. "
    "Write ONE short natural reply in German (2-5 sentences). "
    "Acknowledge what you learned, ask at most one clear next question if needed, "
    "and stay concrete. Do not mention that you are an AI. Do not use markdown fences."
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


def _normalize_platform(value: str) -> str:
    alias = post_fields.extract_platform(value)
    if alias:
        return alias
    lowered = value.strip().lower()
    return post_fields.PLATFORM_ALIASES.get(lowered, value.strip())


def _clean_llm_updates(data: dict[str, Any], post: dict[str, Any]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for key in BRIEF_KEYS:
        if key not in data or data[key] is None:
            continue
        value = str(data[key]).strip()
        if len(value) < post_fields.FIELD_MIN_LENGTH:
            continue
        if key == "platform":
            value = _normalize_platform(value)
        max_len = post_fields.FIELD_MAX_LENGTH.get(key, 300)
        value = value[:max_len]
        current = post.get(key)
        if key in ("topic", "target_audience", "additional_context") and current:
            continue
        if value != current:
            updates[key] = value
    return updates


def extract_brief_with_llm(
    message: str,
    post: dict[str, Any],
    hf: HuggingFaceService | None,
) -> dict[str, Any]:
    """Prefer LLM extraction; always merge with regex/alias fallback."""
    regex_updates = post_fields.extract_fields(message, post)
    if hf is None:
        return regex_updates

    brief_snapshot = {key: post.get(key) for key in BRIEF_KEYS}
    awaiting = post.get(post_fields.AWAITING_FIELD_KEY)
    user_prompt = (
        f"Current brief: {json.dumps(brief_snapshot, ensure_ascii=False)}\n"
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
    brief_updates: dict[str, Any] | None = None,
    next_question: str | None = None,
    artifact_summary: str | None = None,
) -> str:
    if hf is None:
        return fallback

    brief = post_fields.brief_summary(post) if post else "no post"
    user_prompt = (
        f"Situation: {situation}\n"
        f"User message: {user_message}\n"
        f"Brief status: {brief}\n"
        f"Just saved updates: {json.dumps(brief_updates or {}, ensure_ascii=False)}\n"
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
    return reply


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
    return reply


def try_hf(hf_factory: Callable[[], HuggingFaceService] | None) -> HuggingFaceService | None:
    if hf_factory is None:
        return None
    try:
        return hf_factory()
    except Exception:
        return None
