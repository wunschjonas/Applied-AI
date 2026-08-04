"""Manager ReAct tool schemas and dispatch for marketing multi-agent planning."""

from __future__ import annotations

import re
from typing import Any, Callable

from app.graphs.support import post_fields
from app.services.rag_service import filter_rag_context


def _fn(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


MEMORY_SEARCH_TOOL = _fn(
    "memory_search",
    (
        "Search stored brand facts, uploaded documents, and project memory. "
        "Use for on-topic brand facts that help the CURRENT post. "
        "Query must stay on the current Steckbrief topic."
    ),
    {
        "query": {"type": "string", "description": "On-topic search query."},
        "n_results": {"type": "integer", "description": "Max hits.", "default": 3},
    },
    ["query"],
)

MEMORY_LIST_TOOL = _fn(
    "memory_list",
    (
        "List a short overview of what is stored in memory/RAG. "
        "Use when the user asks what is stored, or when memory_search returned nothing useful."
    ),
    {
        "limit": {"type": "integer", "description": "Max entries to list.", "default": 10},
    },
    [],
)

MEMORY_STORE_TOOL = _fn(
    "memory_store",
    (
        "Store a durable brand fact or user-provided note into project memory. "
        "Call ONLY when the user explicitly asks to remember/save something. "
        "If the user says 'store this/that fact' / 'speicher den Fakt' without repeating it, "
        "put the PREVIOUS user message (the actual fact) into content — never store the "
        "store-command itself (e.g. not 'Fakt im Rag'). "
        "Prefer topical tags (topic, year, entity) over generic labels. "
        "Do not store every chat turn."
    ),
    {
        "content": {
            "type": "string",
            "description": (
                "The fact/note to store. Prefer the concrete fact text, not the "
                "store instruction. If the user only asked to store 'this', use the prior user message."
            ),
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional tags.",
        },
    },
    ["content"],
)

WEB_SEARCH_TOOL = _fn(
    "web_search",
    (
        "Search the public web for current facts, trends, or events not in project memory. "
        "Use for timely/world knowledge. Prefer memory_* for internal brand facts."
    ),
    {
        "query": {"type": "string", "description": "Web search query."},
        "max_results": {"type": "integer", "description": "Max snippets.", "default": 3},
    },
    ["query"],
)

GET_POST_DATA_TOOL = _fn(
    "get_post_data",
    (
        "Read the current marketing post Steckbrief and preview snapshot from storage. "
        "Use before generation or when you need to know what is already set."
    ),
    {},
    [],
)

CHECK_POST_DATA_COMPLETENESS_TOOL = _fn(
    "check_post_data_completeness",
    (
        "Check whether required Steckbrief fields are filled before text/image generation. "
        "Call this before generating marketing text or images. "
        "If incomplete, do not invent missing fields — the system will ask the user."
    ),
    {},
    [],
)

MANAGER_TOOLS: list[dict[str, Any]] = [
    MEMORY_SEARCH_TOOL,
    MEMORY_LIST_TOOL,
    MEMORY_STORE_TOOL,
    WEB_SEARCH_TOOL,
    GET_POST_DATA_TOOL,
    CHECK_POST_DATA_COMPLETENESS_TOOL,
]

MANAGER_TOOL_NAMES = frozenset(
    t["function"]["name"] for t in MANAGER_TOOLS
)

_WEB_QUERY_PREFIXES = (
    r"^\s*suche?\s+im\s+(?:internet|web)\s*[:\-]?\s*",
    r"^\s*recherchiere?\s+(?:im\s+(?:internet|web)\s*)?[:\-]?\s*",
    r"^\s*(?:please\s+)?search\s+(?:the\s+)?(?:web|internet)\s*(?:for\s*)?[:\-]?\s*",
)
_PRONOUN_ONLY = frozenset(
    {"wer", "was", "wie", "wo", "wann", "warum", "wieso", "weshalb", "welche", "welcher", "welches", "who", "what", "when", "where", "why"}
)


def sanitize_web_query(query: str, user_message: str | None = None) -> str:
    """Build a topical web query; never return a lone interrogative pronoun."""

    def _strip_prefixes(text: str) -> str:
        cleaned = (text or "").strip()
        for pattern in _WEB_QUERY_PREFIXES:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
        return cleaned

    q = _strip_prefixes(query)
    msg = _strip_prefixes(user_message or "")
    tokens = [t for t in re.split(r"\s+", q.lower()) if t]
    weak = (
        not q
        or len(q) < 8
        or (len(tokens) == 1 and tokens[0] in _PRONOUN_ONLY)
        or (len(tokens) <= 2 and tokens[0] in _PRONOUN_ONLY and not any(ch.isdigit() for ch in q))
    )
    if weak and msg:
        # Drop leading pronoun but keep the topical remainder from the full question.
        topical = re.sub(
            r"^\s*(?:wer|was|wie|wo|wann|warum|wieso|weshalb|welche[rs]?|who|what)\s+",
            "",
            msg,
            flags=re.IGNORECASE,
        ).strip(" \t,;:!?-")
        q = topical or msg
    return (q or query or "current events")[:200]


_STORE_COMMAND_RE = re.compile(
    r"(?i)^\s*(?:"
    r"(?:bitte\s+)?"
    r"(?:merk(?:e)?\s+dir|speicher(?:e)?|speichere|remember|store|save)"
    r".*|"
    r".*(?:im\s+(?:rag|gedächtnis|gedaechtnis)|in\s+(?:die\s+)?(?:memory|wissensbasis))"
    r".*"
    r")\s*$"
)
_INLINE_FACT_RE = re.compile(
    r"(?is)^\s*(?:merk(?:e)?\s+dir|speicher(?:e)?|remember|store|save)"
    r"(?:\s+(?:bitte|dir|das|dir\s+bitte))?"
    r"(?:\s*(?:folgende[sn]?|diesen?\s+fakt|den\s+fakt|this|that))?"
    r"\s*[:\-–]\s*(.+)$"
)
_THIN_STORE_CONTENT_RE = re.compile(
    r"(?i)^\s*(?:den\s+)?fakt(?:\s+im\s+(?:rag|gedächtnis|gedaechtnis))?|"
    r"diese[sn]?\s+fakt|that\s+fact|this\s+fact|note|notiz\s*$"
)


def looks_like_store_command(text: str) -> bool:
    """True when the message is mainly an instruction to save something."""
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    inline = _INLINE_FACT_RE.match(cleaned)
    if inline and len(inline.group(1).strip()) >= 12:
        return False
    lowered = cleaned.lower()
    has_verb = any(
        token in lowered
        for token in ("merk dir", "merke dir", "speicher", "remember", "store ", "save ")
    )
    if not has_verb:
        return False
    # Short command, or command without a long inline fact after a colon.
    if len(cleaned) <= 80:
        return True
    return bool(_STORE_COMMAND_RE.match(cleaned)) or ":" not in cleaned


def last_user_chat_message(chat: dict[str, Any] | None) -> str | None:
    """Most recent USER message already stored in the chat (prior turns)."""
    if not chat:
        return None
    messages = chat.get("messages") or []
    for item in reversed(messages):
        if str(item.get("role") or "").upper() == "USER":
            content = str(item.get("content") or "").strip()
            if content:
                return content
    return None


def resolve_memory_store_content(
    raw_content: str,
    *,
    user_message: str | None = None,
    chat: dict[str, Any] | None = None,
) -> str:
    """Prefer the real fact over store-command text / thin placeholders."""
    content = (raw_content or "").strip()
    user_msg = (user_message or "").strip()
    prior = last_user_chat_message(chat)

    inline = _INLINE_FACT_RE.match(user_msg)
    if inline and len(inline.group(1).strip()) >= 12:
        return inline.group(1).strip()[:2000]

    inline_content = _INLINE_FACT_RE.match(content)
    if inline_content and len(inline_content.group(1).strip()) >= 12:
        return inline_content.group(1).strip()[:2000]

    thin = (
        not content
        or len(content) < 24
        or bool(_THIN_STORE_CONTENT_RE.match(content))
        or looks_like_store_command(content)
    )
    if thin and prior and len(prior) >= 20 and not looks_like_store_command(prior):
        return prior[:2000]

    if looks_like_store_command(user_msg) and prior and len(prior) >= 20 and not looks_like_store_command(prior):
        if thin or content.casefold() in user_msg.casefold() or len(content) < len(prior) * 0.4:
            return prior[:2000]

    return content[:2000]


def suggest_memory_tags(content: str, llm_tags: list[str] | None = None) -> list[str]:
    """Build topical tags from content; keep useful LLM tags, drop empty placeholders."""
    stop = {
        "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "eines",
        "und", "oder", "aber", "mit", "ohne", "für", "fuer", "von", "vom", "zum",
        "zur", "im", "in", "am", "an", "auf", "aus", "bei", "als", "auch", "noch",
        "sich", "nicht", "nur", "sehr", "wurde", "wurden", "hat", "haben", "ist",
        "sind", "war", "waren", "the", "and", "for", "with", "from", "that", "this",
        "manager_store", "test", "fakt", "note", "notiz",
    }
    tags: list[str] = []
    for raw in llm_tags or []:
        t = str(raw).strip().lower().replace(" ", "_")[:40]
        if t and t not in stop and t not in tags:
            tags.append(t)

    lowered = (content or "").casefold()
    topic_rules = (
        (("wm", "weltmeister", "world cup", "fifa"), "fussball_wm"),
        (("fußball", "fussball", "football", "soccer"), "fussball"),
        (("spanien", "spain"), "spanien"),
        (("argentinien", "argentina"), "argentinien"),
        (("deutschland", "germany"), "deutschland"),
        (("marke", "brand", "ci "), "brand"),
        (("linkedin",), "linkedin"),
        (("instagram",), "instagram"),
    )
    for needles, tag in topic_rules:
        if any(n in lowered for n in needles) and tag not in tags:
            tags.append(tag)

    for token in re.findall(r"[A-Za-zÄÖÜäöüß0-9]{4,}", content or ""):
        t = token.casefold()
        if t in stop or t.isdigit():
            continue
        if t not in tags:
            tags.append(t)
        if len(tags) >= 6:
            break

    if not tags:
        tags.append("manager_store")
    return tags[:6]


class ManagerToolDispatcher:
    """Execute manager tools and return (observation, status, side_effects)."""

    def __init__(
        self,
        *,
        rag_service: Any,
        post_repository: Any,
        web_search: Callable[..., str] | None = None,
    ):
        self.rag = rag_service
        self.posts = post_repository
        self.web_search = web_search

    def dispatch(
        self,
        name: str,
        arguments: dict[str, Any],
        state: dict[str, Any],
    ) -> tuple[str, str, dict[str, Any]]:
        """Return observation, status ('success'|'warning'|'error'), and state side effects."""
        effects: dict[str, Any] = {"tool_name": name}
        try:
            if name == "memory_search":
                return self._memory_search(arguments, state, effects)
            if name == "memory_list":
                return self._memory_list(arguments, state, effects)
            if name == "memory_store":
                return self._memory_store(arguments, state, effects)
            if name == "web_search":
                return self._web_search(arguments, state, effects)
            if name == "get_post_data":
                return self._get_post_data(state, effects)
            if name == "check_post_data_completeness":
                return self._check_post_data(state, effects)
            return f"Unsupported tool '{name}' ignored.", "warning", effects
        except Exception as exc:
            effects["tool_error"] = f"{type(exc).__name__}: {exc}"
            return f"Tool {name} fehlgeschlagen: {type(exc).__name__}: {exc}", "error", effects

    def _memory_search(
        self,
        arguments: dict[str, Any],
        state: dict[str, Any],
        effects: dict[str, Any],
    ) -> tuple[str, str, dict[str, Any]]:
        query = str(arguments.get("query") or "").strip()
        if not query:
            post = state.get("post") or {}
            query = str(post.get("topic") or state.get("user_message") or "brand facts")[:120]
        try:
            n_results = int(arguments.get("n_results") or 3)
        except (TypeError, ValueError):
            n_results = 3
        n_results = max(1, min(n_results, 8))
        effects["query"] = query

        if hasattr(self.rag, "search"):
            raw = self.rag.search(query, n_results=n_results)
        else:
            raw = self.rag.retrieve(query, state.get("context"))

        topic = ((state.get("post") or {}).get("topic") or "").strip() or None
        filtered = filter_rag_context(raw, topic=topic, user_message=state.get("user_message"))
        if filtered:
            existing = state.get("rag_context")
            merged = f"{existing}\n{filtered}".strip() if existing else filtered
            filtered_merged = (
                filter_rag_context(merged, topic=topic, user_message=state.get("user_message")) or None
            )
            effects["rag_context"] = filtered_merged
            effects["rag_needed"] = bool(filtered_merged)
            lines = [ln for ln in (filtered_merged or "").splitlines() if ln.strip()]
            effects["rag_hit_count"] = len(lines)
            return (
                f"Retrieved {len(lines)} on-topic memory item(s). Summary: {(filtered_merged or '')[:240]}",
                "success",
                effects,
            )
        if raw:
            effects["rag_hit_count"] = 0
            return "memory_search hits were off-topic and discarded.", "warning", effects
        effects["rag_hit_count"] = 0
        return "memory_search returned no results.", "warning", effects

    def _memory_list(
        self,
        arguments: dict[str, Any],
        state: dict[str, Any],
        effects: dict[str, Any],
    ) -> tuple[str, str, dict[str, Any]]:
        try:
            limit = int(arguments.get("limit") or 10)
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 20))
        entries = self.rag.list_all() if hasattr(self.rag, "list_all") else []
        if not entries:
            return "Memory is empty — no stored entries.", "warning", effects

        topic = ((state.get("post") or {}).get("topic") or "").strip()
        joined = "\n".join(entries[:limit])
        filtered = filter_rag_context(
            joined,
            topic=topic or None,
            user_message=state.get("user_message"),
        )
        preview = filtered or "\n".join(f"- {e[:160]}" for e in entries[: min(5, limit)])
        if filtered:
            effects["rag_context"] = filtered
            effects["rag_needed"] = True
            effects["rag_hit_count"] = len([ln for ln in filtered.splitlines() if ln.strip()])
        effects["listed_count"] = len(entries)
        return (
            f"memory_list: {len(entries)} entr(y/ies) total. Preview:\n{preview[:500]}",
            "success",
            effects,
        )

    def _memory_store(
        self,
        arguments: dict[str, Any],
        state: dict[str, Any],
        effects: dict[str, Any],
    ) -> tuple[str, str, dict[str, Any]]:
        content = resolve_memory_store_content(
            str(arguments.get("content") or ""),
            user_message=state.get("user_message"),
            chat=state.get("chat"),
        )
        if len(content) < 8:
            return (
                "memory_store refused: no durable fact found "
                "(neither tool content nor previous user message).",
                "warning",
                effects,
            )
        tags = suggest_memory_tags(content, arguments.get("tags") if isinstance(arguments.get("tags"), list) else None)
        self.rag.store(content, tags=tags)
        effects["stored_preview"] = content[:240]
        effects["stored_tags"] = tags
        return f"Stored memory note ({len(content)} chars), tags={tags}.", "success", effects

    def _web_search(
        self,
        arguments: dict[str, Any],
        state: dict[str, Any],
        effects: dict[str, Any],
    ) -> tuple[str, str, dict[str, Any]]:
        raw_query = str(arguments.get("query") or "").strip()
        query = sanitize_web_query(raw_query, state.get("user_message"))
        if not query:
            return "web_search requires a query.", "warning", effects
        effects["query"] = query
        try:
            max_results = int(arguments.get("max_results") or 3)
        except (TypeError, ValueError):
            max_results = 3
        if self.web_search is None:
            effects["tool_error"] = "web_search unavailable (disabled or not configured)"
            return (
                "web_search unavailable (disabled or not configured). Try memory_search instead.",
                "error",
                effects,
            )
        try:
            text = self.web_search(query, max_results=max_results)
        except Exception as exc:
            effects["tool_error"] = f"{type(exc).__name__}: {exc}"
            return (
                f"web_search failed: {type(exc).__name__}: {exc}. Try memory_search instead.",
                "error",
                effects,
            )
        if not text:
            effects["web_hit_count"] = 0
            return "web_search returned no results.", "warning", effects
        effects["web_context"] = text
        effects["web_hit_count"] = text.count("\n") + 1
        return f"web_search results:\n{text[:600]}", "success", effects

    def _get_post_data(
        self,
        state: dict[str, Any],
        effects: dict[str, Any],
    ) -> tuple[str, str, dict[str, Any]]:
        post = state.get("post")
        post_id = state.get("post_id")
        if not post and post_id and self.posts is not None:
            post = self.posts.get(post_id)
        if not post:
            return "No post found for this chat.", "warning", effects
        summary = post_fields.post_status_summary(post)
        effects["post_data_summary"] = summary[:300]
        return f"Current post Steckbrief/preview:\n{summary}", "success", effects

    def _check_post_data(
        self,
        state: dict[str, Any],
        effects: dict[str, Any],
    ) -> tuple[str, str, dict[str, Any]]:
        post = state.get("post") or {}
        missing = post_fields.missing_required_fields(post) if post else ["topic", "platform", "target_audience", "tone_of_voice"]
        effects["post_data_checked"] = True
        effects["post_data_missing"] = missing
        effects["post_data_complete"] = not bool(missing)
        if missing:
            return (
                f"Steckbrief incomplete. missing={missing}. Ask the user for these fields before generating.",
                "warning",
                effects,
            )
        return "Steckbrief complete. All required fields are set — generation may proceed.", "success", effects
