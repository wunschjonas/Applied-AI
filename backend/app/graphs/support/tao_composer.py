"""Compose short, presentation-friendly TAO traces from workflow facts (German).

Thought / Action / Observation are derived from runtime events — not fixed full sentences
passed in by callers. No LLM calls; no chain-of-thought dumps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


INTENT_LABELS: dict[str, str] = {
    "text_only": "nur Text",
    "image_only": "nur Bild",
    "text_and_image": "Text und Bild",
    "memory_inquiry": "Memory-/RAG-Frage",
    "memory_store": "Memory speichern",
    "web_inquiry": "Web-Recherche",
    "post_status_inquiry": "Post-Status-Frage",
    "clarification_needed": "Klärung nötig",
    "unclassified": "noch unklar",
}


@dataclass
class TaoEvent:
    """Structured workflow facts for one TAO step."""

    phase: str
    node: str
    agent: str | None = None
    status: str = "success"
    intent: str | None = None
    facts: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.facts.get(key, default)


@dataclass(frozen=True)
class TaoTriple:
    thought: str
    action: str
    observation: str


def compose(event: TaoEvent) -> TaoTriple:
    """Build Thought / Action / Observation from an event."""
    handler = _PHASE_HANDLERS.get(event.phase, _compose_generic)
    triple = handler(event)
    return TaoTriple(
        thought=_clip(triple.thought),
        action=_clip(triple.action, 160),
        observation=_clip(triple.observation, 320),
    )


def _clip(text: str, limit: int = 220) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _intent_de(intent: str | None) -> str:
    if not intent:
        return "unbekannt"
    return INTENT_LABELS.get(intent, intent)


def _join_agents(agents: Any) -> str:
    if not agents:
        return "keine"
    if isinstance(agents, (list, tuple)):
        return ", ".join(str(a) for a in agents) or "keine"
    return str(agents)


def _short_summary(text: Any, limit: int = 120) -> str:
    if text is None:
        return ""
    return _clip(str(text), limit)


# --- phase handlers ---------------------------------------------------------


def _compose_init(event: TaoEvent) -> TaoTriple:
    platform = event.get("platform") or "nicht gesetzt"
    return TaoTriple(
        thought="Neuen Manager-Lauf starten und Trace anlegen.",
        action="Graph-Zustand initialisieren",
        observation=(
            f"Chat {event.get('chat_id', '?')}, Trace {event.get('trace_id', '?')}, "
            f"Plattform {platform}."
        ),
    )


def _compose_collect_post_data(event: TaoEvent) -> TaoTriple:
    if event.status == "skipped" and event.get("post_missing"):
        return TaoTriple(
            thought="Kein gespeicherter Post vorhanden — Steckbrief entfällt.",
            action="Post-Steckbrief lesen",
            observation=f"post_id={event.get('post_id')} nicht in posts.json.",
        )
    updates = event.get("updates") or {}
    missing = event.get("missing") or []
    summary = event.get("post_data_summary") or ""
    updated = ", ".join(updates.keys()) if isinstance(updates, dict) and updates else "nichts"
    return TaoTriple(
        thought="Steckbrief-Felder aus der Nutzernachricht übernehmen.",
        action="Post-Steckbrief aktualisieren",
        observation=(
            f"Aktualisiert: {updated}. Offen: {', '.join(missing) or 'keine'}. "
            f"{_short_summary(summary, 100)}"
        ).strip(),
    )


def _compose_classify_intent(event: TaoEvent) -> TaoTriple:
    intent = _intent_de(event.intent)
    decision = _short_summary(event.get("decision"), 100)
    detail = _short_summary(event.get("detail"), 140)
    return TaoTriple(
        thought=decision or f"Anfrage als „{intent}“ einordnen.",
        action="Intent klassifizieren",
        observation=detail or f"Intent: {intent}.",
    )


def _compose_create_plan(event: TaoEvent) -> TaoTriple:
    agents = _join_agents(event.get("required_agents"))
    expected = event.get("expected_artifacts") or []
    artifacts = ", ".join(expected) if isinstance(expected, (list, tuple)) else str(expected or "—")
    needs_rag = "ja" if event.get("needs_rag_check") else "nein"
    return TaoTriple(
        thought=f"Ablauf für Intent „{_intent_de(event.intent)}“ festlegen.",
        action="Ausführungsplan erstellen",
        observation=f"Agenten: {agents}. Erwartete Artefakte: {artifacts}. RAG-Check: {needs_rag}.",
    )


def _compose_route(event: TaoEvent) -> TaoTriple:
    intent = _intent_de(event.intent)
    target = event.get("route_target") or event.get("next_node") or "unbekannt"
    return TaoTriple(
        thought=f"Weiterleitung nach Intent „{intent}“.",
        action="Nach Intent routen",
        observation=f"Nächster Schritt: {target}.",
    )


def _compose_manager_tool(event: TaoEvent) -> TaoTriple:
    tool = event.get("tool_name") or "tool"
    mode = event.get("rag_mode") or "llm"
    query = _short_summary(event.get("query"), 80)
    err = event.get("tool_error")

    if event.get("skipped") or mode == "skip":
        return TaoTriple(
            thought="Keine weiteren Tools nötig — mit aktuellem Kontext weiter.",
            action="Tools überspringen",
            observation=_short_summary(event.get("detail"), 200)
            or f"Bisherige Tools: {_join_agents(event.get('tools_called'))}.",
        )

    if err:
        return TaoTriple(
            thought=f"Tool {tool} ist fehlgeschlagen — alternativ versuchen.",
            action=f"{tool} (Fehler)",
            observation=_short_summary(err, 200),
        )

    if tool == "check_post_data_completeness":
        missing = event.get("post_data_missing") or []
        if event.get("post_data_complete") is False or missing:
            return TaoTriple(
                thought="Vor der Generierung prüfen, ob der Steckbrief vollständig ist.",
                action="check_post_data_completeness",
                observation=f"Unvollständig, fehlend: {', '.join(missing) or 'unbekannt'}.",
            )
        return TaoTriple(
            thought="Vor der Generierung Steckbrief-Vollständigkeit prüfen.",
            action="check_post_data_completeness",
            observation="Steckbrief vollständig — Generierung kann starten.",
        )

    if tool == "get_post_data":
        return TaoTriple(
        thought="Aktuellen Steckbrief/Preview einsehen.",
        action="get_post_data",
        observation=_short_summary(event.get("rag_summary") or event.get("post_data_summary"), 200)
            or "Steckbrief gelesen.",
        )

    if tool == "memory_list":
        return TaoTriple(
            thought="Überblick über gespeicherte Memory-Einträge holen.",
            action="memory_list",
            observation=_short_summary(event.get("rag_summary"), 220) or "Memory-Liste geladen.",
        )

    if tool == "memory_store":
        return TaoTriple(
            thought="Dauerhafte Notiz in der Wissensbasis speichern.",
            action="memory_store",
            observation=_short_summary(event.get("rag_summary"), 200) or "Eintrag gespeichert.",
        )

    if tool == "web_search":
        hits = event.get("web_hit_count")
        return TaoTriple(
            thought=f"Aktuelle Infos im Web zu „{query or 'Thema'}“ suchen.",
            action=f"web_search ({query})" if query else "web_search",
            observation=_short_summary(event.get("rag_summary"), 220)
            or (f"{hits} Treffer." if hits is not None else "Web-Suche ausgeführt."),
        )

    if tool == "memory_search" or mode in {"forced", "fallback", "llm"}:
        hits = event.get("rag_hit_count")
        if mode == "forced":
            thought = f"Memory-Fallback — Wissensbasis zu „{query or 'Thema'}“ abfragen."
        elif mode == "fallback":
            thought = "Keyword-/Fallback-Abruf aus dem Memory."
        else:
            thought = f"Interne Fakten zu „{query or 'Thema'}“ suchen."
        return TaoTriple(
            thought=thought,
            action=f"memory_search ({query})" if query else "memory_search",
            observation=_short_summary(event.get("rag_summary"), 220)
            or (f"{hits} Treffer." if hits is not None else "Memory-Suche ausgeführt."),
        )

    return TaoTriple(
        thought=f"Tool {tool} ausführen.",
        action=tool,
        observation=_short_summary(event.get("rag_summary") or event.get("detail"), 220) or f"Status {event.status}.",
    )


def _compose_post_data_safety(event: TaoEvent) -> TaoTriple:
    missing = event.get("post_data_missing") or []
    return TaoTriple(
        thought="Safety-Net: Completeness-Tool wurde übersprungen, Steckbrief ist unvollständig.",
        action="post_data_safety_block",
        observation=_short_summary(event.get("detail"), 200)
        or f"Generierung blockiert. Fehlend: {', '.join(missing) or 'Pflichtfelder'}.",
    )


def _compose_rag_search(event: TaoEvent) -> TaoTriple:
    # Backward-compatible alias → manager_tool semantics
    if not event.get("tool_name") and event.get("rag_mode") in {"skip", "forced", "fallback", "llm"}:
        event.facts.setdefault("tool_name", "memory_search" if event.get("rag_mode") != "skip" else "")
    return _compose_manager_tool(event)


def _compose_rag_done(event: TaoEvent) -> TaoTriple:
    hits = event.get("rag_hit_count")
    used = "mit" if event.get("rag_needed") or (hits and hits > 0) else "ohne"
    return TaoTriple(
        thought="Retrieval-Runde abschließen.",
        action="RAG-ReAct beenden",
        observation=f"Weiter {used} Memory-Kontext"
        + (f" ({hits} Treffer)." if hits is not None else "."),
    )


def _compose_ask_context(event: TaoEvent) -> TaoTriple:
    field = event.get("field") or "Feld"
    missing = event.get("missing") or []
    return TaoTriple(
        thought=f"Vor der Erzeugung fehlt noch „{field}“.",
        action="Steckbrief-Frage stellen",
        observation=f"Noch offen: {', '.join(missing) or field}. Kein Spezialist gestartet.",
    )


def _compose_clarification(event: TaoEvent) -> TaoTriple:
    missing = event.get("missing") or []
    if missing:
        return TaoTriple(
            thought=f"Steckbrief unvollständig — nach „{missing[0]}“ fragen.",
            action="Klärung anfordern",
            observation="Kein Spezialist und kein HuggingFace-Aufruf.",
        )
    return TaoTriple(
        thought="Absicht unklar — nach Text, Bild oder beidem fragen.",
        action="Klärung anfordern",
        observation="Kein Spezialist und kein HuggingFace-Aufruf.",
    )


def _compose_delegate_text(event: TaoEvent) -> TaoTriple:
    retry = event.get("retry_count") or 0
    chars = event.get("text_chars")
    tags = event.get("hashtag_count")
    if event.status == "error":
        return TaoTriple(
            thought="TextAgent konnte nicht liefern.",
            action="TextAgent aufrufen",
            observation=_short_summary(event.get("error"), 200) or "Fehler bei der Texterzeugung.",
        )
    obs_parts = ["Text-Artefakt im Graph-State."]
    if chars is not None:
        obs_parts.append(f"{chars} Zeichen")
    if tags is not None:
        obs_parts.append(f"{tags} Hashtags")
    if retry:
        obs_parts.append(f"Retry {retry}")
    return TaoTriple(
        thought="Marketing-Text über den TextAgent erzeugen.",
        action="TextAgent aufrufen",
        observation="; ".join(obs_parts) + ".",
    )


def _compose_delegate_image(event: TaoEvent) -> TaoTriple:
    retry = event.get("retry_count") or 0
    mode = event.get("image_mode") or "text_to_image"
    filename = event.get("image_filename")
    if event.status == "error":
        return TaoTriple(
            thought="ImageAgent konnte nicht liefern.",
            action="ImageAgent aufrufen",
            observation=_short_summary(event.get("error"), 200) or "Fehler bei der Bilderzeugung.",
        )
    if event.status in {"partial_success", "warning"} and not filename:
        return TaoTriple(
            thought="Bildprompt da, Datei fehlt noch.",
            action="ImageAgent aufrufen",
            observation=_short_summary(event.get("detail"), 200) or "Nur Prompt, kein Bildfile.",
        )
    obs = f"Modus {mode}"
    if filename:
        obs += f", Datei {filename}"
    if retry:
        obs += f", Retry {retry}"
    return TaoTriple(
        thought="Visual über den ImageAgent erzeugen.",
        action="ImageAgent aufrufen",
        observation=obs + ".",
    )


def _compose_memory_answer(event: TaoEvent) -> TaoTriple:
    source = event.get("source") or "memory_search"
    chars = event.get("context_chars") or 0
    if event.status in {"warning", "skipped"} and not chars:
        return TaoTriple(
            thought="Nutzer fragt nach gespeichertem Wissen.",
            action="Memory-Antwort formulieren",
            observation="Keine passenden Memory-Einträge.",
        )
    return TaoTriple(
        thought="Gefundene Memory-Treffer als Antwort aufbereiten.",
        action="Memory-Antwort formulieren",
        observation=f"Quelle {source}, {chars} Zeichen Kontext.",
    )


def _compose_memory_store_ack(event: TaoEvent) -> TaoTriple:
    preview = event.get("stored_preview") or ""
    tags = event.get("stored_tags") or []
    return TaoTriple(
        thought="Speichern bestätigen, ohne als Memory-Suche zu antworten.",
        action="Memory-Speichern bestätigen",
        observation=(
            f"Gespeichert: {_short_summary(preview, 160)}"
            + (f" Tags={tags}." if tags else ".")
        ),
    )


def _compose_web_answer(event: TaoEvent) -> TaoTriple:
    chars = event.get("context_chars") or 0
    if event.status in {"warning", "skipped"} and not chars:
        return TaoTriple(
            thought="Web-Recherche ohne brauchbare Treffer beantworten.",
            action="Web-Antwort formulieren",
            observation="Keine Web-Treffer — ohne Steckbrief-Nachfrage antworten.",
        )
    return TaoTriple(
        thought="Web-Suchtreffer als Chat-Antwort zeigen (ohne Steckbrief-Nachfrage).",
        action="Web-Antwort formulieren",
        observation=f"{chars} Zeichen Suchkontext an Nutzer.",
    )


def _compose_post_status(event: TaoEvent) -> TaoTriple:
    return TaoTriple(
        thought="Aktuellen Post-Stand aus posts.json zusammenfassen.",
        action="Post-Status beantworten",
        observation=f"post_id={event.get('post_id') or '?'}.",
    )


def _compose_validate(event: TaoEvent) -> TaoTriple:
    result = event.get("validation_result") or event.status
    feedback = event.get("feedback_keys") or []
    text_r = event.get("text_retry_count")
    image_r = event.get("image_retry_count")
    fb = ", ".join(feedback) if isinstance(feedback, (list, tuple)) else str(feedback or "keine")
    if result in {"retry_text", "retry_image"}:
        return TaoTriple(
            thought=f"Validierung verlangt Retry ({result}) — Artefakt noch nicht akzeptiert.",
            action=f"Validation-Retry vorbereiten ({result})",
            observation=(
                f"Feedback: {fb}. Zähler Text={text_r if text_r is not None else 0}, "
                f"Bild={image_r if image_r is not None else 0}."
            ),
        )
    return TaoTriple(
        thought=f"Artefakte prüfen (Ergebnis: {result}).",
        action="Ergebnisse validieren",
        observation=(
            f"Feedback: {fb}. Retries Text={text_r if text_r is not None else 0}, "
            f"Bild={image_r if image_r is not None else 0}."
        ),
    )


def _compose_retry(event: TaoEvent) -> TaoTriple:
    kind = event.get("artifact_type") or "artefakt"
    agent = event.get("agent_label") or kind
    detail = _short_summary(event.get("feedback") or event.get("detail"), 160)
    return TaoTriple(
        thought=f"Validation-Retry: {agent} erneut ausführen wegen fehlgeschlagenem Check.",
        action=f"Validation-Retry {kind}",
        observation=detail or "Validierungsfeedback an Specialist weitergeben.",
    )


def _compose_assemble(event: TaoEvent) -> TaoTriple:
    intent = _intent_de(event.intent)
    detail = _short_summary(event.get("detail"), 160)
    return TaoTriple(
        thought=f"Antwort für Intent „{intent}“ aus den Artefakten bauen.",
        action="Antwort zusammensetzen",
        observation=detail or f"Status {event.status}.",
    )


def _compose_persist_preview(event: TaoEvent) -> TaoTriple:
    fields = event.get("preview_fields") or []
    field_list = ", ".join(fields) if isinstance(fields, (list, tuple)) else str(fields)
    return TaoTriple(
        thought="Erzeugte Inhalte in der Post-Vorschau speichern.",
        action="Preview persistieren",
        observation=f"Aktualisiert: {field_list or 'keine Felder'}.",
    )


def _compose_followup(event: TaoEvent) -> TaoTriple:
    field = event.get("field") or "Feld"
    missing = event.get("missing") or []
    return TaoTriple(
        thought=f"Offenes Steckbrief-Feld „{field}“ nachziehen.",
        action="Follow-up anhängen",
        observation=f"Noch offen: {', '.join(missing) or field}.",
    )


def _compose_save_trace(event: TaoEvent) -> TaoTriple:
    agents = _join_agents(event.get("used_agents"))
    return TaoTriple(
        thought="Lauf abschließen und Trace speichern.",
        action="Chat, Trace und Logs persistieren",
        observation=(
            f"Chat {event.get('chat_id', '?')}, Trace {event.get('trace_id', '?')}, "
            f"Agenten: {agents}."
        ),
    )


def _compose_text_build_prompt(event: TaoEvent) -> TaoTriple:
    platform = event.get("platform") or "unbekannt"
    tone = event.get("tone") or "unbekannt"
    return TaoTriple(
        thought="Textauftrag in ein Modell-Prompt übersetzen.",
        action="Text-Prompt bauen",
        observation=f"Plattform {platform}, Tonalität {tone}.",
    )


def _compose_text_call_model(event: TaoEvent) -> TaoTriple:
    model = event.get("model_id") or "HuggingFace-Textmodell"
    return TaoTriple(
        thought="Textmodell für Marketing-Copy aufrufen.",
        action="Textmodell aufrufen",
        observation=f"Modell {model}.",
    )


def _compose_text_parse(event: TaoEvent) -> TaoTriple:
    chars = event.get("text_chars")
    return TaoTriple(
        thought="Modellantwort als Text übernehmen.",
        action="Textantwort parsen",
        observation=f"{chars if chars is not None else '?'} Zeichen empfangen.",
    )


def _compose_text_return(event: TaoEvent) -> TaoTriple:
    chars = event.get("text_chars")
    tags = event.get("hashtag_count")
    return TaoTriple(
        thought="Fertigen Marketing-Text als Artefakt zurückgeben.",
        action="Text-Artefakt liefern",
        observation=f"{chars if chars is not None else '?'} Zeichen, {tags if tags is not None else 0} Hashtags.",
    )


def _compose_image_prompt_start(event: TaoEvent) -> TaoTriple:
    platform = event.get("platform") or "unbekannt"
    style = event.get("visual_style") or "Modellwahl"
    return TaoTriple(
        thought="Bildprompt für das Visual vorbereiten.",
        action="Bildprompt erzeugen",
        observation=f"Plattform {platform}, Stil {style}.",
    )


def _compose_image_prompt_done(event: TaoEvent) -> TaoTriple:
    chars = event.get("prompt_chars")
    return TaoTriple(
        thought="Bildprompt vom Sprachmodell erhalten.",
        action="Bildprompt-Artefakt liefern",
        observation=f"Prompt mit {chars if chars is not None else '?'} Zeichen.",
    )


def _compose_image_call(event: TaoEvent) -> TaoTriple:
    mode = event.get("image_mode") or "text_to_image"
    model = event.get("model_id") or "HuggingFace-Bildmodell"
    strength = event.get("strength")
    source = event.get("img2img_source")
    if mode == "image_to_image":
        obs = f"img2img-Modell {model}"
        if strength is not None:
            obs += f", Strength {strength}"
        if source:
            obs += f", Quelle {source}"
        return TaoTriple(
            thought="Referenz-/Post-Bild per Image-to-Image nutzen.",
            action="image_to_image aufrufen",
            observation=obs + ".",
        )
    if mode == "text_to_image_fallback":
        return TaoTriple(
            thought="Fallback: neues Bild nur aus dem Prompt erzeugen.",
            action="text_to_image (Fallback)",
            observation=f"Modell {model}.",
        )
    return TaoTriple(
        thought="Bild aus dem Prompt erzeugen.",
        action="text_to_image aufrufen",
        observation=f"Modell {model}.",
    )


def _compose_image_fallback(event: TaoEvent) -> TaoTriple:
    return TaoTriple(
        thought="Image-to-Image gescheitert — auf Text-to-Image wechseln.",
        action="Fallback text_to_image",
        observation=_short_summary(event.get("error"), 200) or "img2img fehlgeschlagen.",
    )


def _compose_image_store(event: TaoEvent) -> TaoTriple:
    return TaoTriple(
        thought="Bildbytes lokal als PNG ablegen.",
        action="Bild speichern",
        observation="Speichere generiertes Bild als lokale PNG-Datei.",
    )


def _compose_image_return(event: TaoEvent) -> TaoTriple:
    filename = event.get("image_filename")
    mode = event.get("image_mode") or "text_to_image"
    if event.status in {"partial_success", "error"} and not filename:
        return TaoTriple(
            thought="Prompt vorhanden, Bilddatei fehlt.",
            action="Bild-Artefakt liefern",
            observation=_short_summary(event.get("error"), 200) or "Bildgenerierung fehlgeschlagen.",
        )
    url = event.get("image_url") or ""
    source = event.get("img2img_source") or "none"
    return TaoTriple(
        thought="Bildartefakt ist bereit.",
        action="Bild-Artefakt liefern",
        observation=f"Gespeichert {filename or '?'} ({mode}, Quelle {source})"
        + (f" → {url}." if url else "."),
    )


def _compose_direct_error(event: TaoEvent) -> TaoTriple:
    kind = event.get("artifact_type") or "Artefakt"
    return TaoTriple(
        thought=f"{kind}-Erzeugung fehlgeschlagen.",
        action="Fehler melden",
        observation=_short_summary(event.get("error"), 200) or "Unbekannter Fehler.",
    )


def _compose_generic(event: TaoEvent) -> TaoTriple:
    intent = f" (Intent {_intent_de(event.intent)})" if event.intent else ""
    detail = _short_summary(event.get("detail"), 160)
    facts_bits = []
    for key in ("query", "platform", "model_id", "field", "validation_result"):
        if event.get(key) is not None:
            facts_bits.append(f"{key}={event.get(key)}")
    fact_str = "; ".join(facts_bits)
    return TaoTriple(
        thought=f"Schritt „{event.phase}“ im Node {event.node}{intent}.",
        action=event.phase.replace("_", " "),
        observation=detail or fact_str or f"Status {event.status}.",
    )


_PHASE_HANDLERS = {
    "init_state": _compose_init,
    "collect_post_data": _compose_collect_post_data,
    "classify_intent": _compose_classify_intent,
    "create_plan": _compose_create_plan,
    "route_by_intent": _compose_route,
    "rag_search": _compose_rag_search,
    "manager_tool": _compose_manager_tool,
    "post_data_safety": _compose_post_data_safety,
    "rag_done": _compose_rag_done,
    "ask_context": _compose_ask_context,
    "clarification": _compose_clarification,
    "delegate_text": _compose_delegate_text,
    "delegate_image": _compose_delegate_image,
    "memory_answer": _compose_memory_answer,
    "memory_store_ack": _compose_memory_store_ack,
    "web_answer": _compose_web_answer,
    "post_status": _compose_post_status,
    "validate": _compose_validate,
    "retry": _compose_retry,
    "assemble": _compose_assemble,
    "persist_preview": _compose_persist_preview,
    "followup": _compose_followup,
    "save_trace": _compose_save_trace,
    "text_build_prompt": _compose_text_build_prompt,
    "text_call_model": _compose_text_call_model,
    "text_parse": _compose_text_parse,
    "text_return": _compose_text_return,
    "image_prompt_start": _compose_image_prompt_start,
    "image_prompt_done": _compose_image_prompt_done,
    "image_call": _compose_image_call,
    "image_fallback": _compose_image_fallback,
    "image_store": _compose_image_store,
    "image_return": _compose_image_return,
    "direct_error": _compose_direct_error,
}
