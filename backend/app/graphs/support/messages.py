from __future__ import annotations

from app.graphs.support.post_fields import platform_display

CLARIFICATION_REQUEST = (
    "Soll ich Marketing-Text, einen Bildprompt mit Bildgenerierung oder beides erstellen? "
    "Nenne gern auch Plattform, Zielgruppe und Tonalitaet."
)
BRIEF_COMPLETE_GENERATING = (
    "Danke, damit habe ich alle Informationen die ich brauche. "
    "Ich beginne mit dem Generieren von Text und Bild."
)
TEXT_SUCCESS = (
    "Der Text ist fertig. Schau ihn dir im Text-Agent oder in der Vorschau an."
)
IMAGE_SUCCESS = (
    "Das Bild ist fertig. Schau es dir im Image-Agent oder in der Vorschau an."
)
IMAGE_PROMPT_ONLY = (
    "Der Bildprompt steht, die eigentliche Bildgenerierung ist jedoch fehlgeschlagen. "
    "Details findest du im Image-Agent."
)
COMBINED_SUCCESS = (
    "Text und Bild sind fertig. Schau sie dir im Text-Agent, Image-Agent oder "
    "in der Vorschau an."
)
GENERATION_DONE_PARTIAL = (
    "Die Generierung ist teilweise fertig. Pruefe Text-Agent, Image-Agent und die Vorschau."
)
WORKFLOW_FAILED = "Der Agenten-Workflow ist fehlgeschlagen. Details stehen im Trace."
WORKFLOW_UNCLEAR = "Der Agenten-Workflow konnte die Anfrage nicht eindeutig verarbeiten."
NO_ARTIFACTS = "Der Agenten-Workflow konnte keine vollstaendigen Artefakte erzeugen. Details stehen im Trace."

# Situations for compose_manager_reply after specialist generation (no marketing copy).
SITUATION_TEXT_DONE = (
    "Generation finished successfully (text only). Confirm briefly that the marketing text "
    "is ready. Point the user to the Text-Agent page and/or the Preview page to review it. "
    "Do NOT invent, quote, paraphrase, or paste any marketing copy. Do NOT ask workshop "
    "questions about the text content. Use ich/mir, never wir/uns."
)
SITUATION_IMAGE_DONE = (
    "Generation finished successfully (image only). Confirm briefly that the image is ready. "
    "Point the user to the Image-Agent page and/or the Preview page. "
    "Do NOT invent or describe the image motif in detail. Do NOT paste the image prompt. "
    "Use ich/mir, never wir/uns."
)
SITUATION_IMAGE_PROMPT_ONLY = (
    "Only the image prompt was created; image generation failed. Say so briefly and point "
    "to the Image-Agent. Do not invent marketing copy. Use ich/mir."
)
SITUATION_COMBINED_DONE = (
    "Generation finished successfully (text and image). Confirm briefly that both are ready. "
    "Point the user to the Text-Agent, Image-Agent, and/or Preview pages to review the results. "
    "Do NOT invent, quote, paraphrase, or paste any marketing copy or image description. "
    "Do NOT ask 'was denkst du?' about the copy. Use ich/mir, never wir/uns."
)
SITUATION_PARTIAL_DONE = (
    "Generation finished only partially. Say briefly what is ready vs missing if known from "
    "the artifact summary, and point to Text-Agent, Image-Agent, and Preview. "
    "Do NOT invent or paste marketing copy. Use ich/mir."
)

TEXT_REFINED = "Ich habe den Marketing-Text neu erstellt und in der Post-Vorschau gespeichert."
IMAGE_REFINED = "Ich habe das Bild neu generiert und in der Post-Vorschau aktualisiert."
IMAGE_REFINE_PROMPT_ONLY = "Der neue Bildprompt steht, die Bildgenerierung ist jedoch fehlgeschlagen."

TEXT_GENERATED = (
    "Ich habe mit den Infos aus dem Post einen Text erstellt. "
    "Wie findest du ihn? Was möchtest du ändern?"
)
IMAGE_GENERATED = (
    "Ich habe mit den Infos aus dem Post ein Bild erstellt. "
    "Wie findest du es? Was möchtest du ändern?"
)
IMAGE_GENERATED_PROMPT_ONLY = (
    "Der Bildprompt steht, die eigentliche Bildgenerierung ist jedoch fehlgeschlagen. "
    "Soll ich es noch einmal versuchen?"
)

POST_DATA_QUESTION_INTRO = "Damit der Post passt, brauche ich noch etwas Kontext."
POST_DATA_SAVED_PREFIX = "Notiert:"
POST_DATA_FOLLOWUP_PREFIX = "Damit ich den Post weiter schaerfen kann:"

FIELD_LABELS = {
    "topic": "Thema",
    "platform": "Plattform",
    "target_audience": "Zielgruppe",
    "tone_of_voice": "Tonalitaet",
    "text_context": "Textkontext",
    "text_length": "Textlaenge",
    "image_context": "Bildmotiv",
    "image_style": "Bildstil",
}


def saved_fields_sentence(updates: dict[str, object]) -> str:
    if not updates:
        return ""
    parts = []
    for field, value in updates.items():
        display = platform_display(str(value)) if field == "platform" else value
        parts.append(f"{FIELD_LABELS.get(field, field)} = {display}")
    return f"{POST_DATA_SAVED_PREFIX} {', '.join(parts)}."


def context_question(updates: dict[str, object], question: str) -> str:
    intro = saved_fields_sentence(updates) or POST_DATA_QUESTION_INTRO
    return f"{intro} {question}"


def followup_question(question: str) -> str:
    return f"{POST_DATA_FOLLOWUP_PREFIX} {question}"


def partial_message(text_ok: bool, image_ok: bool, image_prompt_only: bool) -> str:
    if text_ok or image_ok or image_prompt_only:
        return GENERATION_DONE_PARTIAL
    return NO_ARTIFACTS
