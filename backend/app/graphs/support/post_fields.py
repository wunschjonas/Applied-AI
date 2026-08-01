from __future__ import annotations

import re
from typing import Any

REQUIRED_FIELDS = ("topic", "platform")
OPTIONAL_FIELDS = ("target_audience", "tone_of_voice")
BRIEF_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS
FREE_TEXT_FIELDS = ("topic", "platform", "target_audience", "tone_of_voice", "additional_context")

FIELD_QUESTIONS = {
    "topic": "Worum soll der Post inhaltlich gehen?",
    "platform": "Fuer welche Plattform ist der Post gedacht? LinkedIn, Instagram, X, Blog, TikTok oder Facebook?",
    "target_audience": "Wen willst du damit ansprechen?",
    "tone_of_voice": "Welche Tonalitaet passt? Zum Beispiel professionell, locker oder humorvoll.",
}

PLATFORM_ALIASES = {
    "linkedin": "linkedin",
    "instagram": "instagram",
    "insta": "instagram",
    "twitter": "x",
    "tweet": "x",
    "x": "x",
    "blog": "blog",
    "tiktok": "tiktok",
    "facebook": "facebook",
    "fb": "facebook",
}

TONE_ALIASES = {
    "professionell": "professionell",
    "professional": "professionell",
    "locker": "locker",
    "casual": "locker",
    "humorvoll": "humorvoll",
    "humorous": "humorvoll",
    "sachlich": "sachlich",
    "freundlich": "freundlich",
    "formell": "formell",
    "formal": "formell",
    "inspirierend": "inspirierend",
}

GENERATE_MARKERS = (
    "erstell",
    "erzeug",
    "generier",
    "schreib",
    "entwirf",
    "create",
    "generate",
    "write",
    "draft",
)

TOPIC_PATTERNS = (
    r"zum thema\s+(.{3,200}?)(?:[.!?\n]|$)",
    r"\bthema\s*:\s*(.{3,200}?)(?:[.!?\n]|$)",
    r"\bueber\s+(.{3,200}?)(?:[.!?\n]|$)",
    r"\büber\s+(.{3,200}?)(?:[.!?\n]|$)",
    r"\babout\s+(.{3,200}?)(?:[.!?\n]|$)",
)
AUDIENCE_PATTERNS = (
    r"zielgruppe\s*(?:ist|sind|:)?\s*(.{3,300}?)(?:[.!?\n]|$)",
    r"richtet sich an\s+(.{3,300}?)(?:[.!?\n]|$)",
    r"target audience\s*(?:is|:)?\s*(.{3,300}?)(?:[.!?\n]|$)",
)
TONE_PATTERNS = (
    r"tonalitaet\s*(?:ist|:)?\s*(.{3,120}?)(?:[.!?\n]|$)",
    r"tonalität\s*(?:ist|:)?\s*(.{3,120}?)(?:[.!?\n]|$)",
    r"\btone\s*(?:of voice\s*)?(?:is|:)?\s*(.{3,120}?)(?:[.!?\n]|$)",
)

FIELD_MAX_LENGTH = {
    "topic": 200,
    "target_audience": 300,
    "tone_of_voice": 120,
    "platform": 40,
    "additional_context": 1000,
}
FIELD_MIN_LENGTH = 3

AWAITING_FIELD_KEY = "awaiting_field"


def wants_generation(message: str) -> bool:
    normalized = message.lower()
    return any(marker in normalized for marker in GENERATE_MARKERS)


def extract_platform(message: str) -> str | None:
    normalized = message.lower()
    for alias, canonical in PLATFORM_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", normalized):
            return canonical
    return None


def extract_tone(message: str) -> str | None:
    patterned = _first_match(message, TONE_PATTERNS)
    if patterned:
        alias = None
        for key, canonical in TONE_ALIASES.items():
            if re.search(rf"\b{re.escape(key)}\b", patterned.lower()):
                alias = canonical
                break
        return alias or patterned[: FIELD_MAX_LENGTH["tone_of_voice"]]

    normalized = message.lower()
    for alias, canonical in TONE_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", normalized):
            return canonical
    return None


def _first_match(message: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip(" \t,;:-")
            if len(value) >= FIELD_MIN_LENGTH:
                return value
    return None


def _clean_answer(field: str, message: str) -> str | None:
    value = message.strip(" \t\n.,;:!?-")
    if len(value) < FIELD_MIN_LENGTH:
        return None
    if field == "platform":
        return extract_platform(value) or value[: FIELD_MAX_LENGTH["platform"]]
    if field == "tone_of_voice":
        return extract_tone(value) or value[: FIELD_MAX_LENGTH["tone_of_voice"]]
    return value[: FIELD_MAX_LENGTH.get(field, 300)]


def extract_fields(message: str, post: dict[str, Any]) -> dict[str, Any]:
    """Collect post field updates from a chat message (regex/alias path)."""
    updates: dict[str, Any] = {}
    awaiting = post.get(AWAITING_FIELD_KEY)

    platform = extract_platform(message)
    if platform and platform != post.get("platform"):
        updates["platform"] = platform

    tone = extract_tone(message)
    if tone and tone != post.get("tone_of_voice"):
        updates["tone_of_voice"] = tone

    topic = _first_match(message, TOPIC_PATTERNS)
    if topic and not post.get("topic"):
        updates["topic"] = topic[: FIELD_MAX_LENGTH["topic"]]

    audience = _first_match(message, AUDIENCE_PATTERNS)
    if audience and not post.get("target_audience"):
        updates["target_audience"] = audience[: FIELD_MAX_LENGTH["target_audience"]]

    # Awaited free-text answers fill the field the manager just asked for.
    if awaiting in FREE_TEXT_FIELDS and awaiting not in updates and not wants_generation(message):
        # Prefer not to overwrite a just-detected platform/tone with the whole message
        # unless that field is the awaited one.
        answer = _clean_answer(awaiting, message)
        if answer:
            # If the message only matched another field, keep that and skip whole-message fill.
            if updates and awaiting not in updates:
                pass
            else:
                updates[awaiting] = answer

    return updates


def missing_fields(post: dict[str, Any]) -> list[str]:
    return [field for field in BRIEF_FIELDS if not post.get(field)]


def missing_required_fields(post: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_FIELDS if not post.get(field)]


def next_question(post: dict[str, Any]) -> tuple[str, str] | None:
    """Return the next field to ask for plus its question text."""
    for field in missing_fields(post):
        return field, FIELD_QUESTIONS[field]
    return None


def brief_context(post: dict[str, Any]) -> dict[str, Any]:
    """Post fields in the shape the delegation helpers expect."""
    context: dict[str, Any] = {}
    if post.get("platform"):
        context["platform"] = post["platform"]
    if post.get("tone_of_voice"):
        context["tone"] = post["tone_of_voice"]
    if post.get("target_audience"):
        context["target_audience"] = post["target_audience"]
    if post.get("topic"):
        context["topic"] = post["topic"]
    if post.get("additional_context"):
        context["additional_context"] = post["additional_context"]
    return context


def brief_summary(post: dict[str, Any]) -> str:
    parts = [f"{field}={post.get(field) or 'offen'}" for field in BRIEF_FIELDS]
    return "; ".join(parts)
