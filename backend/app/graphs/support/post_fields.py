from __future__ import annotations

import re
from typing import Any

REQUIRED_FIELDS = ("topic", "platform", "target_audience", "tone_of_voice")
TEXT_INTENT_EXTRA_FIELDS = ("text_context", "text_length")
IMAGE_INTENT_EXTRA_FIELDS = ("image_context", "image_style")
OPTIONAL_FIELDS: tuple[str, ...] = TEXT_INTENT_EXTRA_FIELDS + IMAGE_INTENT_EXTRA_FIELDS
POST_DATA_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS
FREE_TEXT_FIELDS = (
    "topic",
    "platform",
    "target_audience",
    "tone_of_voice",
    "text_context",
    "text_length",
    "image_context",
    "image_style",
)

FIELD_QUESTIONS = {
    "topic": "Worum soll der Post inhaltlich gehen?",
    "platform": "Fuer welche Plattform ist der Post gedacht? LinkedIn, Instagram, X, Blog, TikTok oder Facebook?",
    "target_audience": "Wen willst du damit ansprechen?",
    "tone_of_voice": "Welche Tonalitaet passt? Zum Beispiel professionell, locker oder humorvoll.",
    "text_context": "Was soll der Text inhaltlich sagen oder abdecken? Kernbotschaft und wichtige Punkte.",
    "text_length": "Wie lang soll der Text sein? Zum Beispiel kurz, mittel oder lang.",
    "image_context": "Was soll auf dem Bild zu sehen sein? Beschreibe Motiv, Personen und Hintergrund.",
    "image_style": "Welcher Bildstil passt? Zum Beispiel fotorealistisch, Illustration oder clean commercial.",
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
IMAGE_CONTEXT_PATTERNS = (
    r"(?:im\s+)?bildmotiv\s*(?:soll(?:te)?|ist|:)\s*(.{10,500})",
    r"bildmotiv\s*:\s*(.{10,500})",
    r"image\s*context\s*:\s*(.{10,500})",
    r"auf\s+dem\s+bild\s+soll(?:en|te)?\s*(.{10,500})",
    r"im\s+bild\s+soll(?:en|te)?\s*(.{10,500})",
    r"image\s*(?:motif|context)\s*(?:should(?:\s+be)?|:)?\s*(.{10,500})",
)
TEXT_CONTEXT_PATTERNS = (
    r"text\s*context\s*:\s*(.{10,1000})",
    r"textkontext\s*:\s*(.{10,1000})",
    r"(?:im\s+)?text\s+(?:soll(?:te)?|geht\s+es\s+um)\s*(.{10,1000})",
    r"kernbotschaft\s*(?:ist|:)?\s*(.{10,1000})",
)
TEXT_LENGTH_PATTERNS = (
    r"text\s*length\s*:\s*(.{3,40})",
    r"textl(?:ä|ae|a)nge\s*(?:ist|:)?\s*(.{3,40})",
    r"(?:text\s+)?(?:soll\s+)?(.{0,10}?\b(?:kurz|mittel|lang)\b.{0,10})",
)
IMAGE_STYLE_PATTERNS = (
    r"image\s*style\s*:\s*(.{3,120})",
    r"bildstil\s*(?:ist|:)?\s*(.{3,120})",
    r"visual\s*style\s*:\s*(.{3,120})",
    r"(?:stil|style)\s*(?:soll(?:te)?|ist|:)\s*(.{3,120})",
)

FIELD_MAX_LENGTH = {
    "topic": 200,
    "target_audience": 300,
    "tone_of_voice": 120,
    "platform": 40,
    "text_context": 1000,
    "text_length": 40,
    "image_context": 500,
    "image_style": 120,
}
FIELD_MIN_LENGTH = 3

AWAITING_FIELD_KEY = "awaiting_field"

# Maps free-form text_length answers to hard prompt guidance for TextAgent.
TEXT_LENGTH_GUIDANCE = {
    "short": "Write approximately 40-80 words in 1-2 short paragraphs.",
    "medium": "Write approximately 80-150 words in 2-3 paragraphs.",
    "long": "Write approximately 150-250 words in 3-4 paragraphs.",
}


def normalize_text_length_guidance(text_length: str | None) -> str | None:
    """Turn kurz/mittel/lang (and EN aliases) into a concrete length rule for prompts."""
    raw = (text_length or "").strip()
    if not raw:
        return None
    lowered = raw.casefold()
    if any(token in lowered for token in ("kurz", "short", "knapp", "brief")):
        return TEXT_LENGTH_GUIDANCE["short"]
    if any(token in lowered for token in ("mittel", "medium", "normal", "standard")):
        return TEXT_LENGTH_GUIDANCE["medium"]
    if any(token in lowered for token in ("lang", "long", "ausfuehrlich", "ausführlich", "detailed")):
        return TEXT_LENGTH_GUIDANCE["long"]
    return f"Approximate this requested length: {raw}."


MEMORY_INQUIRY_MARKERS = (
    "gedächtnis",
    "gedachtnis",
    "gedaechtnis",
    "memory",
    "knowledge base",
    "im rag",
    "dein rag",
    "deinem rag",
    "vom rag",
    "aus dem rag",
    "zum rag",
    "unsere daten",
    "was steht in",
    "hast du im",
    "gespeichert",
    "hochgeladen",
    "was weißt du über",
    "was weisst du ueber",
    "was weisst du über",
    "kennst du details",
    "kennst du etwas",
    "hast du infos",
    "gibt es infos",
)

MEMORY_INQUIRY_PATTERNS = (
    r"\b(?:im|aus dem|vom|zum)\s+rag\b",
    r"\brag\b.{0,40}\b(?:zu|über|ueber|zum thema)\b",
    r"\b(?:zu|über|ueber|zum thema)\b.{0,80}\b(?:rag|gedächtnis|gedachtnis|gedaechtnis|memory)\b",
    r"\b(?:rag|gedächtnis|gedachtnis|gedaechtnis|memory)\b.{0,80}\b(?:zu|über|ueber|thema)\b",
    r"was\s+(?:steht|wei[sß]t|findest).{0,40}\b(?:rag|gedächtnis|gedachtnis|gedaechtnis|memory|daten)\b",
    r"was\s+wei[sß]t\s+du\s+(?:über|ueber|zu|zur|zum|zum thema)\b",
    r"kennst\s+du\s+(?:details|etwas|infos)\s+(?:zu|zur|zum|über|ueber|zum thema)\b",
    r"was\s+kannst\s+du\s+mir\s+(?:über|ueber|zu|zur|zum)\b",
    r"(?:hast|gibt)\s+(?:du\s+)?infos?\s+(?:zu|zur|zum|über|ueber)\b",
)

MEMORY_QUERY_PATTERNS = (
    r"(?:was steht|was wei[sß]t du|was findest du|was kannst du mir).*(?:zum thema|über|ueber|zur|zum|zu)\s+(.+)$",
    r"(?:kennst du (?:details|etwas|infos)|hast du infos|gibt es infos).*(?:zum thema|über|ueber|zur|zum|zu)\s+(.+)$",
    r"(?:im rag|im gedächtnis|im gedachtnis|im gedaechtnis|in memory).*(?:zum thema|über|ueber|zur|zum|zu)\s+(.+)$",
    r"(?:zum thema|über|ueber)\s+(.+?)(?:\s+(?:im|aus dem|vom)\s+(?:rag|gedächtnis|gedachtnis|gedaechtnis|memory).*)?$",
    r"(?:zur|zum|zu)\s+(.+?)(?:\s+(?:im|aus dem|vom)\s+(?:rag|gedächtnis|gedachtnis|gedaechtnis|memory).*)?$",
    r"(?:rag|gedächtnis|gedachtnis|gedaechtnis|memory).*(?:zum thema|über|ueber|zur|zum|zu)\s+(.+)$",
)

POST_STATUS_MARKERS = (
    "aktueller post",
    "aktuellen post",
    "zum post",
    "zum aktuellen post",
    "post-status",
    "post status",
    "post-data-status",
    "brief status",
    "welche felder",
    "offene felder",
    "was haben wir bereits",
    "was wissen wir schon",
    "was ist schon gesetzt",
    "was steht in posts",
    "post-daten",
    "post daten",
    "zeig den brief",
    "zeig mir den brief",
    "zeig den post",
)

POST_STATUS_PATTERNS = (
    r"\b(?:aktueller|aktuellen|dieser|diesen)\s+post\b",
    r"\b(?:zum|ueber den|über den)\s+(?:aktuellen\s+)?post\b",
    r"\b(?:brief|post)[\s-]?status\b",
    r"was\s+(?:wissen|haben)\s+wir\s+(?:schon|bereits)\b",
    r"welche\s+felder\b",
    r"was\s+ist\s+schon\s+gesetzt\b",
    r"zeig(?:\s+mir)?\s+den\s+(?:brief|post)\b",
)

WEB_INQUIRY_MARKERS = (
    "aktuell",
    "heutige",
    "heute",
    "trend",
    "trends",
    "nachrichten",
    "news",
    "recherchier",
    "im web",
    "im internet",
    "suche im web",
    "suche im internet",
    "such im web",
    "such im internet",
    "websearch",
    "web search",
    "was passiert",
    "aktueller stand der",
    "neuigkeiten",
)

WEB_INQUIRY_PATTERNS = (
    r"\b(?:aktuell(?:e|er|en|es)?|heutige[rnsm]?)\b.{0,40}\b(?:trend|news|nachricht|lage|stand)\b",
    r"\b(?:trend|nachrichten|news)\b",
    r"\b(?:recherchier|googlen|suche?)\b.{0,30}\b(?:web|internet|online)\b",
    r"\b(?:im|aufs?)\s+(?:web|internet)\b",
    r"was\s+passiert\s+(?:gerade|heute|aktuell)\b",
)


def wants_generation(message: str) -> bool:
    normalized = message.lower()
    return any(marker in normalized for marker in GENERATE_MARKERS)


def is_image_motif_briefing(message: str) -> bool:
    """True when the user describes/fills Bildmotiv without asking to generate."""
    if wants_generation(message):
        return False
    lowered = (message or "").strip().lower()
    if not lowered:
        return False
    return any(
        marker in lowered
        for marker in (
            "bildmotiv",
            "bild motiv",
            "image motif",
            "image_context",
            "image context",
            "auf dem bild soll",
            "im bild soll",
        )
    )


def is_question_message(message: str) -> bool:
    """True for interrogative turns that should not fill Steckbrief fields."""
    text = (message or "").strip()
    if not text:
        return False
    if "?" in text:
        return True
    lowered = text.lower()
    starters = (
        "wer ",
        "was ",
        "wie ",
        "wo ",
        "wann ",
        "warum ",
        "wieso ",
        "weshalb ",
        "welche ",
        "welcher ",
        "welches ",
        "kennst du",
        "weißt du",
        "weisst du",
        "hast du",
        "gibt es",
        "suche im",
        "such im",
        "recherchier",
    )
    return any(lowered.startswith(s) for s in starters)


def is_memory_store_request(message: str) -> bool:
    """True when the user asks to save/remember a fact into RAG/memory."""
    lowered = (message or "").strip().lower()
    if not lowered:
        return False
    return any(
        token in lowered
        for token in (
            "merk dir",
            "merke dir",
            "speicher",
            "remember",
            "store this",
            "save this",
        )
    )


def is_post_status_inquiry(message: str) -> bool:
    """True when the user asks about the current post's stored brief/preview data."""
    normalized = message.lower()
    if any(marker in normalized for marker in POST_STATUS_MARKERS):
        return True
    return any(re.search(pattern, normalized) for pattern in POST_STATUS_PATTERNS)


def is_memory_inquiry(message: str) -> bool:
    """True when the user asks what is stored in RAG/memory rather than briefing a post."""
    if is_post_status_inquiry(message) or is_memory_store_request(message):
        return False
    normalized = message.lower()
    if any(marker in normalized for marker in MEMORY_INQUIRY_MARKERS):
        return True
    return any(re.search(pattern, normalized) for pattern in MEMORY_INQUIRY_PATTERNS)


def is_web_inquiry(message: str) -> bool:
    """True when the user wants public/current web facts (not memory, not post status)."""
    if is_post_status_inquiry(message) or is_memory_inquiry(message):
        return False
    normalized = message.lower()
    if any(marker in normalized for marker in WEB_INQUIRY_MARKERS):
        return True
    return any(re.search(pattern, normalized) for pattern in WEB_INQUIRY_PATTERNS)


def memory_search_query(message: str) -> str:
    """Extract a focused search query from a memory/RAG question about topic X."""
    cleaned = re.sub(r"\s+", " ", (message or "").strip())
    if not cleaned:
        return "brand facts"
    lowered = cleaned.lower()
    for pattern in MEMORY_QUERY_PATTERNS:
        match = re.search(pattern, lowered, flags=re.IGNORECASE)
        if match:
            topic = match.group(1).strip(" \t,;:!?-")
            topic = re.sub(
                r"\b(?:im|aus dem|vom|dein|deinem|unser|unsere)?\s*"
                r"(?:rag|gedächtnis|gedachtnis|gedaechtnis|memory|daten)\b",
                "",
                topic,
                flags=re.IGNORECASE,
            ).strip(" \t,;:!?-")
            if len(topic) >= FIELD_MIN_LENGTH:
                return topic[:200]
    # Fallback: drop filler words but keep the topical remainder.
    stripped = re.sub(
        r"\b(?:was|steht|wei[sß]t|du|findest|kennst|details|etwas|infos|kannst|"
        r"sagen|hast|gibt|es|im|aus|dem|vom|zum|rag|gedächtnis|gedachtnis|"
        r"gedaechtnis|memory|bitte|mir|dazu|ueber|über)\b",
        " ",
        lowered,
        flags=re.IGNORECASE,
    )
    stripped = re.sub(r"\s+", " ", stripped).strip(" \t,;:!?-")
    return (stripped or cleaned)[:200]


def is_valid_platform(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in PLATFORM_ALIASES.values()


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
        # Never persist free-text questions as platform — only known enum values.
        return extract_platform(value)
    if field == "tone_of_voice":
        return extract_tone(value) or value[: FIELD_MAX_LENGTH["tone_of_voice"]]
    return value[: FIELD_MAX_LENGTH.get(field, 300)]


def extract_fields(message: str, post: dict[str, Any]) -> dict[str, Any]:
    """Collect post field updates from a chat message (regex/alias path)."""
    if is_memory_inquiry(message) or is_post_status_inquiry(message):
        return {}

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

    text_ctx = _first_match(message, TEXT_CONTEXT_PATTERNS)
    if text_ctx and not post.get("text_context"):
        updates["text_context"] = text_ctx[: FIELD_MAX_LENGTH["text_context"]]

    text_len = _first_match(message, TEXT_LENGTH_PATTERNS)
    if text_len and not post.get("text_length"):
        updates["text_length"] = text_len[: FIELD_MAX_LENGTH["text_length"]]

    image_motif = _first_match(message, IMAGE_CONTEXT_PATTERNS)
    if image_motif and not post.get("image_context"):
        updates["image_context"] = image_motif[: FIELD_MAX_LENGTH["image_context"]]
    elif is_image_motif_briefing(message) and not post.get("image_context") and "image_context" not in updates:
        # Whole message is the motif description (e.g. multi-sentence "Im Bildmotiv …").
        cleaned = re.sub(
            r"^(?:im\s+)?bildmotiv\s*(?:soll(?:te)?|ist|:)\s*",
            "",
            message.strip(),
            flags=re.IGNORECASE,
        ).strip()
        if len(cleaned) >= FIELD_MIN_LENGTH:
            updates["image_context"] = cleaned[: FIELD_MAX_LENGTH["image_context"]]

    image_style = _first_match(message, IMAGE_STYLE_PATTERNS)
    if image_style and not post.get("image_style"):
        updates["image_style"] = image_style[: FIELD_MAX_LENGTH["image_style"]]

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
    return [field for field in POST_DATA_FIELDS if not post.get(field)]


def missing_required_fields(post: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_FIELDS if not post.get(field)]


def missing_fields_for_intent(post: dict[str, Any], intent: str | None = None) -> list[str]:
    """Required Steckbrief fields plus intent-specific text/image extras."""
    missing = missing_required_fields(post)
    if intent in {"text_only", "text_and_image"}:
        for field in TEXT_INTENT_EXTRA_FIELDS:
            if not post.get(field) and field not in missing:
                missing.append(field)
    if intent in {"image_only", "text_and_image"}:
        for field in IMAGE_INTENT_EXTRA_FIELDS:
            if not post.get(field) and field not in missing:
                missing.append(field)
    return missing


def next_question(post: dict[str, Any], intent: str | None = None) -> tuple[str, str] | None:
    """Return the next field to ask for plus its question text."""
    if intent in {"text_only", "image_only", "text_and_image"}:
        ordered = missing_fields_for_intent(post, intent)
    else:
        ordered = missing_required_fields(post)
        if not ordered:
            ordered = [field for field in OPTIONAL_FIELDS if not post.get(field)]
    for field in ordered:
        question = FIELD_QUESTIONS.get(field)
        if question:
            return field, question
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
    if post.get("text_context"):
        context["text_context"] = post["text_context"]
    if post.get("text_length"):
        context["text_length"] = post["text_length"]
    if post.get("image_context"):
        context["image_context"] = post["image_context"]
    if post.get("image_style"):
        context["image_style"] = post["image_style"]
        context["visual_style"] = post["image_style"]
    return context


def post_data_summary(post: dict[str, Any]) -> str:
    parts = [f"{field}={post.get(field) or 'offen'}" for field in POST_DATA_FIELDS]
    return "; ".join(parts)


def post_status_summary(post: dict[str, Any]) -> str:
    """Human-readable snapshot of the current posts.json entry for chat answers."""
    from app.graphs.support.messages import FIELD_LABELS

    lines = [
        f"Titel: {post.get('title') or '—'}",
        f"Status: {post.get('status') or '—'}",
    ]
    for field in POST_DATA_FIELDS:
        label = FIELD_LABELS.get(field, field)
        value = post.get(field)
        lines.append(f"{label}: {value if value else 'offen'}")

    preview = post.get("preview") or {}
    if isinstance(preview, dict):
        text = (preview.get("generated_text") or "").strip()
        hashtags = preview.get("hashtags") or []
        image_url = preview.get("image_url")
        lines.append(f"Marketing-Text: {'vorhanden' if text else 'fehlt'}")
        lines.append(f"Hashtags: {', '.join(hashtags) if hashtags else 'fehlen'}")
        lines.append(f"Bild: {'vorhanden' if image_url else 'fehlt'}")

    missing = missing_fields(post)
    if missing:
        labels = ", ".join(FIELD_LABELS.get(field, field) for field in missing)
        lines.append(f"Noch offen: {labels}")
    else:
        lines.append("Noch offen: nichts")
    return "\n".join(lines)
