from __future__ import annotations

from typing import Any

from app.graphs.support.post_fields import extract_platform

TEXT_INTENTS = frozenset({"text_only", "text_and_image"})
IMAGE_INTENTS = frozenset({"image_only", "text_and_image"})

TEXT_BRIEF_HEADLINE = "Teilauftrag des ManagerAgent: Erstelle den Marketing-Text."
IMAGE_BRIEF_HEADLINE = "Teilauftrag des ManagerAgent: Erstelle das Bildmotiv."
MARKETING_TEXT_LABEL = "Bereits erstellter Marketing-Text, zu dem das Bild passen muss:"
POST_BRIEF_LABEL = "Post-Brief aus dem Manager-Chat:"

TEXT_REFINE_HEADLINE = "Verfeinerungsauftrag: Passe den bestehenden Marketing-Text an."
IMAGE_REFINE_HEADLINE = "Verfeinerungsauftrag: Passe das bestehende Bildmotiv an."
CURRENT_TEXT_LABEL = "Aktueller Marketing-Text:"
CURRENT_PROMPT_LABEL = "Aktueller Bildprompt:"
CHANGE_REQUEST_LABEL = "Aenderungswunsch des Nutzers:"

# The marketing text is only briefing context, so a long copy must not crowd out the brief itself.
MARKETING_TEXT_BRIEF_LIMIT = 800


def context_value(
    context: str | dict[str, Any] | None,
    key: str,
    default: str | None = None,
) -> str | None:
    if isinstance(context, dict):
        return context.get(key, default)
    return default


def resolve_platform(context: str | dict[str, Any] | None, message: str) -> str | None:
    return context_value(context, "platform") or extract_platform(message)


def build_execution_plan(
    intent: str,
    message: str,
    context: str | dict[str, Any] | None,
    platform: str | None,
) -> dict[str, Any]:
    required_agents: list[str] = []
    expected_artifacts: list[str] = []
    validation_requirements: list[str] = []

    if intent in TEXT_INTENTS:
        required_agents.append("TextAgent")
        expected_artifacts.append("text")
        validation_requirements.extend(["text_not_empty", "hashtags_present"])
        if platform:
            validation_requirements.append("platform_considered")
    if intent in IMAGE_INTENTS:
        required_agents.append("ImageAgent")
        expected_artifacts.append("image")
        validation_requirements.extend(
            ["image_prompt_not_empty", "suggested_style_present", "image_file_exists", "image_url_present"]
        )
    if intent == "clarification_needed":
        expected_artifacts.append("clarification_message")
        validation_requirements.append("assistant_message_present")

    return {
        "required_agents": required_agents,
        "needs_rag_check": True,
        "expected_artifacts": expected_artifacts,
        "validation_requirements": validation_requirements,
        "assignments": build_assignments(intent, message, context, platform),
    }


def build_brief_section(context: str | dict[str, Any] | None) -> str:
    """Topic and extra context from the post, which the agents cannot infer from their own arguments."""
    lines = []
    topic = context_value(context, "topic")
    if topic:
        lines.append(f"- Thema des Posts: {topic}")
    additional_context = context_value(context, "additional_context")
    if additional_context:
        lines.append(f"- Zusatzkontext: {additional_context}")
    if not lines:
        return ""
    return "\n" + POST_BRIEF_LABEL + "\n" + "\n".join(lines)


def build_assignments(
    intent: str,
    message: str,
    context: str | dict[str, Any] | None,
    platform: str | None,
) -> dict[str, dict[str, Any]]:
    assignments: dict[str, dict[str, Any]] = {}
    brief_section = build_brief_section(context)

    if intent in TEXT_INTENTS:
        assignments["text"] = {
            "task": f"{TEXT_BRIEF_HEADLINE}\nNutzeranfrage: {message}{brief_section}",
            "platform": platform,
            "tone": context_value(context, "tone", "professional"),
            "target_audience": context_value(context, "target_audience"),
        }

    if intent in IMAGE_INTENTS:
        assignments["image"] = {
            "task": f"{IMAGE_BRIEF_HEADLINE}\nNutzeranfrage: {message}{brief_section}",
            "platform": platform,
            "visual_style": context_value(context, "visual_style"),
        }

    return assignments


def build_text_refine_task(message: str, current_text: str | None) -> str:
    """Brief for the direct TextAgent chat: change the stored copy instead of starting over."""
    if not current_text or not current_text.strip():
        return f"{TEXT_BRIEF_HEADLINE}\nNutzeranfrage: {message}"
    excerpt = current_text.strip()[:MARKETING_TEXT_BRIEF_LIMIT]
    return (
        f"{TEXT_REFINE_HEADLINE}\n"
        f"{CURRENT_TEXT_LABEL}\n{excerpt}\n"
        f"{CHANGE_REQUEST_LABEL} {message}"
    )


def build_image_refine_task(
    message: str,
    current_prompt: str | None,
    marketing_text: str | None = None,
) -> str:
    """Brief for the direct ImageAgent chat: adjust the stored motif and stay close to the copy."""
    if current_prompt and current_prompt.strip():
        task = (
            f"{IMAGE_REFINE_HEADLINE}\n"
            f"{CURRENT_PROMPT_LABEL}\n{current_prompt.strip()[:MARKETING_TEXT_BRIEF_LIMIT]}\n"
            f"{CHANGE_REQUEST_LABEL} {message}"
        )
    else:
        task = f"{IMAGE_BRIEF_HEADLINE}\nNutzeranfrage: {message}"
    return image_task_with_marketing_text(task, marketing_text)


def image_task_with_marketing_text(task: str, marketing_text: str | None) -> str:
    if not marketing_text or not marketing_text.strip():
        return task
    excerpt = marketing_text.strip()[:MARKETING_TEXT_BRIEF_LIMIT]
    return f"{task}\n{MARKETING_TEXT_LABEL}\n{excerpt}"
