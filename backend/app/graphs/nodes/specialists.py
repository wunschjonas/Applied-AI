from __future__ import annotations

from datetime import datetime
from typing import Any

from app.agents.image_agent import ImageAgent
from app.agents.text_agent import TextAgent
from app.graphs.dependencies import GraphDependencies, StepRecorder
from app.graphs.state import ManagerChatState
from app.graphs.support import post_data_llm, messages, post_fields
from app.graphs.support.delegation import context_value, image_task_with_marketing_text
from app.graphs.support.tao_composer import TaoEvent
from app.metrics import inc_manager_specialist
from app.services.rag_service import filter_rag_context


class SpecialistNodes:
    def __init__(self, deps: GraphDependencies):
        self.deps = deps
        self.recorder = StepRecorder(deps)

    def text_agent_node(self, state: ManagerChatState) -> ManagerChatState:
        started_at = datetime.utcnow()
        assignment = self._assignment(state, "text")
        context = state.get("context")
        try:
            result = TextAgent(self.deps.hf_factory(), self.deps.trace_service).generate(
                task=assignment.get("task") or state["user_message"],
                trace=state["trace"],
                platform=assignment.get("platform", state.get("platform")),
                tone=assignment.get("tone", context_value(context, "tone", "professional")),
                target_audience=assignment.get("target_audience", context_value(context, "target_audience")),
                text_context=assignment.get("text_context", context_value(context, "text_context")),
                text_length=assignment.get("text_length", context_value(context, "text_length")),
                context=context,
                rag_context=self._combined_knowledge(state),
                validation_feedback=state.get("validation_feedback", {}).get("text"),
            )
        except Exception as exc:
            self._record_failure(state, "text", started_at, state["text_retry_count"], exc)
            return state

        state["generated_artifacts"]["text"] = result
        self._remember_agent(state, "TextAgent")
        self._save_specialist_chat(state, "text_agent", "Text artifact generated.", "text")
        inc_manager_specialist("text", "success")
        event = TaoEvent(
            phase="delegate_text",
            node="text_agent_node",
            agent="text_agent_node",
            intent=state.get("intent"),
            facts={
                "retry_count": state["text_retry_count"],
                "text_chars": len(result.get("generated_text", "")),
                "hashtag_count": len(result.get("hashtags", [])),
            },
        )
        self.recorder.record(state, event)
        self.recorder.log(
            state,
            agent="text_agent",
            status="success",
            step="text",
            started_at=started_at,
            tool_called="huggingface_generate_text",
            event=event,
            output_summary=(
                f"{len(result.get('generated_text', ''))} chars, "
                f"{len(result.get('hashtags', []))} hashtags"
            ),
        )
        return state

    def image_agent_node(self, state: ManagerChatState) -> ManagerChatState:
        started_at = datetime.utcnow()
        assignment = self._assignment(state, "image")
        context = state.get("context")
        marketing_text = (state["generated_artifacts"].get("text") or {}).get("generated_text")
        task = image_task_with_marketing_text(
            assignment.get("task") or state["user_message"],
            marketing_text,
        )
        image_context: dict[str, Any] = {}
        if isinstance(context, dict):
            image_context.update({k: v for k, v in context.items() if v})
        elif state.get("post") and isinstance(state["post"], dict):
            image_context.update({k: v for k, v in state["post"].items() if v})
        tone = (
            assignment.get("tone")
            or context_value(context, "tone")
            or (state.get("post") or {}).get("tone_of_voice")
        )
        if tone:
            image_context["tone"] = tone
        try:
            result = ImageAgent(
                self.deps.hf_factory(),
                self.deps.trace_service,
                image_storage=self.deps.image_storage,
            ).generate_image(
                task=task,
                trace=state["trace"],
                platform=assignment.get("platform", state.get("platform")),
                visual_style=assignment.get("visual_style", context_value(context, "visual_style")),
                context=image_context or None,
                rag_context=self._combined_knowledge(state),
                validation_feedback=state.get("validation_feedback", {}).get("image"),
                post_id=state["post_id"],
                post_repository=self.deps.post_repository,
            )
        except Exception as exc:
            self._record_failure(state, "image", started_at, state["image_retry_count"], exc)
            return state

        state["generated_artifacts"]["image"] = result
        self._remember_agent(state, "ImageAgent")
        status = "partial_success" if result.get("partial_success") else "success"
        inc_manager_specialist("image", status)
        event = TaoEvent(
            phase="delegate_image",
            node="image_agent_node",
            agent="image_agent_node",
            status=status,
            intent=state.get("intent"),
            facts={
                "retry_count": state["image_retry_count"],
                "image_mode": result.get("generation_mode") or "text_to_image",
                "image_filename": result.get("image_filename"),
                "tools_called": result.get("tools_called"),
                "detail": self._image_summary(result),
            },
        )
        self._save_specialist_chat(state, "image_agent", "Image artifact generated.", "image")
        self.recorder.record(state, event)
        self.recorder.log(
            state,
            agent="image_agent",
            status="success" if status == "success" else "error",
            step="image",
            started_at=started_at,
            tool_called="huggingface_text_to_image",
            event=event,
            output_summary=self._image_summary(result),
        )
        return state

    def clarification_node(self, state: ManagerChatState) -> ManagerChatState:
        started_at = datetime.utcnow()
        post = state.get("post")
        missing = post_fields.missing_fields(post) if post else []
        if missing:
            field = missing[0]
            question = post_fields.FIELD_QUESTIONS[field]
            fallback = messages.context_question(state.get("post_data_updates") or {}, question)
            situation = (
                "Steckbrief fields are still open. Ask only for the next missing Steckbrief field. "
                "Do not ask whether to generate text or image yet."
            )
            state["followup_question"] = question
            self.deps.post_repository.update_fields(
                state["post_id"], {post_fields.AWAITING_FIELD_KEY: field}
            )
        else:
            fallback = messages.CLARIFICATION_REQUEST
            situation = (
                "Intent is unclear. Ask whether the user wants text, image, or both."
            )

        state["assistant_message"] = post_data_llm.compose_manager_reply(
            hf=post_data_llm.try_hf(self.deps.hf_factory),
            fallback=fallback,
            situation=situation,
            user_message=state["user_message"],
            post=post,
            post_data_updates=state.get("post_data_updates"),
            next_question=fallback if missing else None,
        )
        state["status"] = "needs_input"

        event = TaoEvent(
            phase="clarification",
            node="clarification_node",
            agent="clarification_node",
            status="needs_input",
            intent=state.get("intent"),
            facts={"missing": missing},
        )
        self.recorder.record(state, event)
        self.recorder.log(
            state,
            agent="manager_agent",
            status="needs_input",
            step="frage",
            started_at=started_at,
            event=event,
        )
        return state

    def memory_answer_node(self, state: ManagerChatState) -> ManagerChatState:
        """Answer questions about stored RAG/memory content without generating a post."""
        started_at = datetime.utcnow()
        context = (state.get("rag_context") or "").strip()
        source = "memory_search"

        if not context:
            entries = self.deps.rag_service.list_all()
            if entries:
                topic = ((state.get("post") or {}).get("topic") or "").strip()
                joined = "\n".join(entries[:20])
                filtered = filter_rag_context(
                    joined,
                    topic=topic or None,
                    user_message=state.get("user_message"),
                )
                if filtered:
                    context = filtered
                    source = "memory_list"
                else:
                    context = ""
            else:
                context = ""

        if context:
            fallback = (
                "Im Gedächtnis habe ich dazu Folgendes gefunden:\n"
                f"{context}"
            )
            situation = (
                "Summarize the retrieved memory/RAG entries for the user in German. "
                "Answer specifically about the topic they asked. "
                "Be concrete about what is stored. Do not invent missing facts. "
                "Do not ask for Steckbrief fields, platform, audience, or tone. "
                "Do not push text/image generation unless the user asks."
            )
            status = "success"
        else:
            fallback = (
                "Im Gedächtnis habe ich gerade keine passenden Eintraege gefunden. "
                "Lade bitte auf der Rag-Seite ein PDF/Bild hoch oder speichere einen Fakt, "
                "dann kann ich danach suchen."
            )
            situation = (
                "Tell the user that memory/RAG has no matching entries for their topic and "
                "suggest uploading or storing a fact on the Rag page. "
                "Do not ask for Steckbrief fields."
            )
            status = "warning"

        state["assistant_message"] = post_data_llm.compose_manager_reply(
            hf=post_data_llm.try_hf(self.deps.hf_factory),
            fallback=fallback,
            situation=situation,
            user_message=state["user_message"],
            post=state.get("post"),
            artifact_summary=f"rag_source={source}; rag_chars={len(context)}; rag_context={context[:800]}",
        )
        state["status"] = status
        state["generated_artifacts"]["memory_answer"] = {
            "source": source,
            "context_preview": context[:500],
        }

        event = TaoEvent(
            phase="memory_answer",
            node="memory_answer_node",
            agent="memory_answer_node",
            status=status,
            intent=state.get("intent"),
            facts={"source": source, "context_chars": len(context)},
        )
        self.recorder.record(state, event)
        self.recorder.log(
            state,
            agent="manager_agent",
            status="success" if status == "success" else "skipped",
            step="memory",
            started_at=started_at,
            tool_called="memory_search" if source == "memory_search" else "memory_list",
            event=event,
            output_summary=state["assistant_message"][:2000],
        )
        return state

    def memory_store_ack_node(self, state: ManagerChatState) -> ManagerChatState:
        """Confirm a successful memory_store — do not run empty memory Q&A."""
        started_at = datetime.utcnow()
        preview = (state.get("stored_preview") or "").strip()
        tags = state.get("stored_tags") or []
        if preview:
            tag_text = f" Tags: {', '.join(tags)}." if tags else ""
            fallback = (
                "Alles klar — ich habe den Fakt im RAG gespeichert.\n\n"
                f"Gespeichert: {preview}"
                f"{tag_text}"
            )
            situation = (
                "Confirm in German that you successfully stored the user's fact in RAG/memory. "
                "Quote or briefly paraphrase the stored preview. Mention tags only briefly if useful. "
                "Do not claim that nothing was found. Do not ask for Steckbrief fields."
            )
            status = "success"
        else:
            fallback = (
                "Ich konnte gerade keinen klaren Fakt zum Speichern erkennen. "
                "Schick mir bitte den Fakt noch einmal als eigenen Text oder formuliere "
                "„Merk dir: …“ mit dem Inhalt."
            )
            situation = (
                "Tell the user in German that storing failed because no durable fact was found. "
                "Ask them to resend the fact clearly. Do not ask for Steckbrief fields."
            )
            status = "warning"

        state["assistant_message"] = post_data_llm.compose_manager_reply(
            hf=post_data_llm.try_hf(self.deps.hf_factory),
            fallback=fallback,
            situation=situation,
            user_message=state["user_message"],
            post=state.get("post"),
            artifact_summary=f"stored_preview={preview[:500]}; tags={tags}",
        )
        state["status"] = status
        state["generated_artifacts"]["memory_store_ack"] = {
            "stored_preview": preview,
            "tags": tags,
        }

        event = TaoEvent(
            phase="memory_store_ack",
            node="memory_store_ack_node",
            agent="memory_store_ack_node",
            status=status,
            intent=state.get("intent"),
            facts={"stored_preview": preview[:200], "stored_tags": tags},
        )
        self.recorder.record(state, event)
        self.recorder.log(
            state,
            agent="manager_agent",
            status="success" if status == "success" else "skipped",
            step="memory_store",
            started_at=started_at,
            tool_called="memory_store",
            event=event,
            output_summary=state["assistant_message"][:2000],
        )
        return state

    def web_answer_node(self, state: ManagerChatState) -> ManagerChatState:
        """Present a short summary of web_search results — no brief prompts."""
        started_at = datetime.utcnow()
        context = (state.get("web_context") or "").strip()

        if context:
            state["assistant_message"] = post_data_llm.compose_web_summary(
                hf=post_data_llm.try_hf(self.deps.hf_factory),
                user_message=state["user_message"],
                web_context=context,
            )
            status = "success"
        else:
            state["assistant_message"] = post_data_llm.compose_web_summary(
                hf=None,
                user_message=state["user_message"],
                web_context="",
            )
            status = "warning"

        state["status"] = status
        state["generated_artifacts"]["web_answer"] = {
            "context_preview": context[:500],
            "hit": bool(context),
            "summarized": True,
        }

        event = TaoEvent(
            phase="web_answer",
            node="web_answer_node",
            agent="web_answer_node",
            status=status,
            intent=state.get("intent"),
            facts={"context_chars": len(context), "has_results": bool(context)},
        )
        self.recorder.record(state, event)
        self.recorder.log(
            state,
            agent="manager_agent",
            status="success" if status == "success" else "skipped",
            step="web",
            started_at=started_at,
            tool_called="web_search",
            event=event,
            output_summary=state["assistant_message"][:2000],
        )
        return state

    def post_status_node(self, state: ManagerChatState) -> ManagerChatState:
        """Summarize the current post entry from posts.json without RAG or specialists."""
        started_at = datetime.utcnow()
        post = state.get("post") or {}
        summary = post_fields.post_status_summary(post) if post else "Fuer diesen Post liegen noch keine Daten vor."
        fallback = (
            "Hier der aktuelle Stand des Posts:\n"
            f"{summary}"
        )
        state["assistant_message"] = post_data_llm.compose_manager_reply(
            hf=post_data_llm.try_hf(self.deps.hf_factory),
            fallback=fallback,
            situation=(
                "Summarize the current marketing post Steckbrief and preview status in German. "
                "Use only the provided post snapshot. Do not invent fields. "
                "Do not ask to generate text or image unless the user asks."
            ),
            user_message=state["user_message"],
            post=post,
            artifact_summary=summary[:800],
        )
        state["status"] = "success"
        state["generated_artifacts"]["post_status_answer"] = {
            "summary": summary,
        }

        event = TaoEvent(
            phase="post_status",
            node="post_status_node",
            agent="post_status_node",
            intent=state.get("intent"),
            facts={"post_id": state.get("post_id")},
        )
        self.recorder.record(state, event)
        self.recorder.log(
            state,
            agent="manager_agent",
            status="success",
            step="post_status",
            started_at=started_at,
            event=event,
            output_summary=state["assistant_message"][:2000],
        )
        return state

    def _assignment(self, state: ManagerChatState, artifact_type: str) -> dict[str, Any]:
        assignments = state.get("execution_plan", {}).get("assignments", {})
        return assignments.get(artifact_type) or {}

    @staticmethod
    def _combined_knowledge(state: ManagerChatState) -> str | None:
        parts = [p for p in (state.get("rag_context"), state.get("web_context")) if p]
        return "\n\n".join(parts) if parts else None

    def _record_failure(
        self,
        state: ManagerChatState,
        artifact_type: str,
        started_at: datetime,
        retry_count: int,
        exc: Exception,
    ) -> None:
        error = f"{type(exc).__name__}: {exc}"
        state["errors"].append(error)
        state["status"] = "error"
        is_text = artifact_type == "text"
        node = f"{artifact_type}_agent_node"
        phase = "delegate_text" if is_text else "delegate_image"
        inc_manager_specialist(artifact_type, "error")

        event = TaoEvent(
            phase=phase,
            node=node,
            agent=node,
            status="error",
            intent=state.get("intent"),
            facts={"retry_count": retry_count, "error": error},
        )
        self.recorder.record(state, event)
        self.recorder.log(
            state,
            agent=f"{artifact_type}_agent",
            status="error",
            step=f"{artifact_type}",
            started_at=started_at,
            tool_called="huggingface_generate_text" if is_text else "huggingface_text_to_image",
            event=event,
            output_summary=error,
        )

    def _save_specialist_chat(
        self,
        state: ManagerChatState,
        agent: str,
        assistant_message: str,
        artifact_type: str,
    ) -> None:
        chat = self.deps.chat_service.get_or_create_chat(state["post_id"], agent=agent)
        self.deps.chat_service.add_message(chat, "USER", state["user_message"])
        self.deps.chat_service.add_message(chat, "AGENT", assistant_message)

    def _remember_agent(self, state: ManagerChatState, agent: str) -> None:
        if agent not in state["used_agents"]:
            state["used_agents"].append(agent)

    def _image_summary(self, artifact: dict[str, Any]) -> str:
        if artifact.get("image_url"):
            return f"Image prompt and file ready: {artifact.get('image_filename')} -> {artifact.get('image_url')}"
        return f"Prompt ready but image unavailable: {artifact.get('image_error', 'unknown error')}"
