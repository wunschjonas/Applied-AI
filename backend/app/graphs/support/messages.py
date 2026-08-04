from __future__ import annotations

CLARIFICATION_REQUEST = (
    "Soll ich Marketing-Text, einen Bildprompt mit Bildgenerierung oder beides erstellen? "
    "Nenne gern auch Plattform, Zielgruppe und Tonalitaet."
)
TEXT_SUCCESS = "Der TextAgent hat Marketing-Text erstellt."
IMAGE_SUCCESS = "Der ImageAgent hat einen Bildprompt erstellt und daraus ein Bild generiert."
IMAGE_PROMPT_ONLY = "Der Bildprompt wurde erstellt, die eigentliche Bildgenerierung ist jedoch fehlgeschlagen."
COMBINED_SUCCESS = "Der TextAgent hat Marketing-Text erstellt und der ImageAgent hat daraus ein Bild generiert."
WORKFLOW_FAILED = "Der Agenten-Workflow ist fehlgeschlagen. Details stehen im Trace."
WORKFLOW_UNCLEAR = "Der Agenten-Workflow konnte die Anfrage nicht eindeutig verarbeiten."
NO_ARTIFACTS = "Der Agenten-Workflow konnte keine vollstaendigen Artefakte erzeugen. Details stehen im Trace."

TEXT_REFINED = "Ich habe den Marketing-Text neu erstellt und in der Post-Vorschau gespeichert."
IMAGE_REFINED = "Ich habe das Bild neu generiert und in der Post-Vorschau aktualisiert."
IMAGE_REFINE_PROMPT_ONLY = "Der neue Bildprompt steht, die Bildgenerierung ist jedoch fehlgeschlagen."

POST_DATA_QUESTION_INTRO = "Damit der Post passt, brauche ich noch etwas Kontext."
POST_DATA_SAVED_PREFIX = "Notiert:"
POST_DATA_FOLLOWUP_PREFIX = "Damit ich den Post weiter schaerfen kann:"

FIELD_LABELS = {
    "topic": "Thema",
    "platform": "Plattform",
    "target_audience": "Zielgruppe",
    "tone_of_voice": "Tonalitaet",
    "additional_context": "Zusatzkontext",
    "image_context": "Bildmotiv",
}


def saved_fields_sentence(updates: dict[str, object]) -> str:
    if not updates:
        return ""
    parts = [f"{FIELD_LABELS.get(field, field)} = {value}" for field, value in updates.items()]
    return f"{POST_DATA_SAVED_PREFIX} {', '.join(parts)}."


def context_question(updates: dict[str, object], question: str) -> str:
    intro = saved_fields_sentence(updates) or POST_DATA_QUESTION_INTRO
    return f"{intro} {question}"


def followup_question(question: str) -> str:
    return f"{POST_DATA_FOLLOWUP_PREFIX} {question}"


def partial_message(text_ok: bool, image_ok: bool, image_prompt_only: bool) -> str:
    parts = []
    if text_ok:
        parts.append(TEXT_SUCCESS)
    if image_ok:
        parts.append(IMAGE_SUCCESS)
    elif image_prompt_only:
        parts.append(IMAGE_PROMPT_ONLY)
    if not parts:
        return NO_ARTIFACTS
    return " ".join(parts)
