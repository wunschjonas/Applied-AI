from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.image_agent import ImageAgent
from app.agents.manager_agent import AgentIntent, ManagerIntentClassifier
from app.agents.text_agent import TextAgent
from app.services.chat_service import ChatService
from app.services.huggingface_service import HuggingFaceService
from app.services.image_storage_service import ImageStorageService
from app.services.log_service import LogService
from app.services.rag_service import RAGService
from app.services.trace_service import TraceService


class ManagerChatState(TypedDict, total=False):
    post_id: str
    chat_id: str | None
    trace_id: str
    trace: dict[str, Any]
    chat: dict[str, Any]
    user_message: str
    context: str | dict[str, Any] | None
    intent: str
    rag_needed: bool
    rag_context: str | None
    used_agents: list[str]
    generated_artifacts: dict[str, Any]
    assistant_message: str
    trace_steps: list[dict[str, Any]]
    errors: list[str]
    warnings: list[str]
    status: str
    platform: str | None
    text_retry_count: int
    image_retry_count: int
    validation_feedback: dict[str, Any]
    validation_result: str
    execution_plan: dict[str, Any]


class ManagerChatGraph:
    def __init__(
        self,
        chat_service: ChatService,
        trace_service: TraceService,
        rag_service: RAGService,
        hf_factory: Callable[[], HuggingFaceService],
        log_service: LogService | None = None,
        image_storage: ImageStorageService | None = None,
    ):
        self.chat_service = chat_service
        self.trace_service = trace_service
        self.rag_service = rag_service
        self.hf_factory = hf_factory
        self.log_service = log_service or LogService()
        self.image_storage = image_storage or ImageStorageService()
        self.intent_classifier = ManagerIntentClassifier()
        self.graph = self._build_graph()

    def run(
        self,
        message: str,
        post_id: str,
        context: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        final_state = self.graph.invoke(
            {
                "post_id": post_id,
                "chat_id": f"{post_id}::manager_agent",
                "user_message": message.strip(),
                "context": context,
            }
        )
        return {
            "chat_id": final_state["chat_id"],
            "assistant_message": final_state["assistant_message"],
            "used_agents": final_state["used_agents"],
            "generated_artifacts": final_state["generated_artifacts"],
            "trace_id": final_state["trace_id"],
        }

    def _build_graph(self):
        graph = StateGraph(ManagerChatState)
        graph.add_node("init_state_node", self.init_state_node)
        graph.add_node("classify_intent_node", self.classify_intent_node)
        graph.add_node("create_plan_node", self.create_plan_node)
        graph.add_node("rag_decision_node", self.rag_decision_node)
        graph.add_node("rag_retrieval_node", self.rag_retrieval_node)
        graph.add_node("route_by_intent", self.route_by_intent_node)
        graph.add_node("text_agent_node", self.text_agent_node)
        graph.add_node("image_agent_node", self.image_agent_node)
        graph.add_node("clarification_node", self.clarification_node)
        graph.add_node("validation_node", self.validation_node)
        graph.add_node("assemble_response_node", self.assemble_response_node)
        graph.add_node("save_trace_node", self.save_trace_node)

        graph.add_edge(START, "init_state_node")
        graph.add_edge("init_state_node", "classify_intent_node")
        graph.add_edge("classify_intent_node", "create_plan_node")
        graph.add_edge("create_plan_node", "rag_decision_node")
        graph.add_conditional_edges(
            "rag_decision_node",
            self.maybe_rag_router,
            {"rag_retrieval_node": "rag_retrieval_node", "route_by_intent": "route_by_intent"},
        )
        graph.add_edge("rag_retrieval_node", "route_by_intent")
        graph.add_conditional_edges(
            "route_by_intent",
            self.intent_router,
            {
                "text_agent_node": "text_agent_node",
                "image_agent_node": "image_agent_node",
                "clarification_node": "clarification_node",
            },
        )
        graph.add_conditional_edges(
            "text_agent_node",
            self.after_text_router,
            {"image_agent_node": "image_agent_node", "validation_node": "validation_node"},
        )
        graph.add_edge("image_agent_node", "validation_node")
        graph.add_edge("clarification_node", "validation_node")
        graph.add_conditional_edges(
            "validation_node",
            self.retry_router,
            {
                "text_agent_node": "text_agent_node",
                "image_agent_node": "image_agent_node",
                "assemble_response_node": "assemble_response_node",
            },
        )
        graph.add_edge("assemble_response_node", "save_trace_node")
        graph.add_edge("save_trace_node", END)
        return graph.compile()

    def init_state_node(self, state: ManagerChatState) -> ManagerChatState:
        post_id = state["post_id"]
        chat = self.chat_service.get_or_create_chat(post_id, agent="manager_agent")
        trace = self.trace_service.create_trace(
            chat_id=chat["id"],
            metadata={"entrypoint": "manager_chat_langgraph", "graph": "ManagerChatGraph", "post_id": post_id},
        )
        normalized_context = state.get("context")
        normalized_message = state["user_message"].strip()
        new_state: ManagerChatState = {
            **state,
            "post_id": post_id,
            "chat": chat,
            "chat_id": chat["id"],
            "trace": trace,
            "trace_id": trace["trace_id"],
            "user_message": normalized_message,
            "context": normalized_context,
            "intent": "unclassified",
            "rag_needed": False,
            "rag_context": None,
            "used_agents": [],
            "generated_artifacts": {},
            "assistant_message": "",
            "trace_steps": [],
            "errors": [],
            "warnings": [],
            "status": "running",
            "platform": self._context_value(normalized_context, "platform") or self._platform_from_message(normalized_message),
            "text_retry_count": 0,
            "image_retry_count": 0,
            "validation_feedback": {},
            "validation_result": "pending",
            "execution_plan": {},
        }
        self._add_step(
            new_state,
            "init_state_node",
            "Initialized Manager chat graph state.",
            "init_state",
            f"chat_id={chat['id']}; trace_id={trace['trace_id']}; platform={new_state['platform'] or 'unspecified'}.",
        )
        return new_state

    def classify_intent_node(self, state: ManagerChatState) -> ManagerChatState:
        t0 = datetime.utcnow()
        intent = self._classify(state["user_message"])
        state["intent"] = intent.label
        status = "needs_input" if intent.needs_clarification else "success"
        self._add_step(state, "classify_intent_node", intent.decision, "classify_intent", intent.observation, status)
        self.log_service.add_log(
            agent="manager_agent",
            action="manager_chat",
            input_summary=state["user_message"][:300],
            status=status,
            duration_ms=self._ms(t0),
            run_id=state.get("trace_id"),
            step="classify_intent",
            decision=f"{intent.label} - {intent.observation}",
            output_summary=f"Intent: {intent.label}",
        )
        return state

    def create_plan_node(self, state: ManagerChatState) -> ManagerChatState:
        intent = state["intent"]
        required_agents: list[str] = []
        expected_artifacts: list[str] = []
        validation_requirements: list[str] = []

        if intent in {"text_only", "text_and_image"}:
            required_agents.append("TextAgent")
            expected_artifacts.append("text")
            validation_requirements.extend(["text_not_empty", "hashtags_present"])
            if state.get("platform"):
                validation_requirements.append("platform_considered")
        if intent in {"image_only", "text_and_image"}:
            required_agents.append("ImageAgent")
            expected_artifacts.append("image")
            validation_requirements.extend(
                ["image_prompt_not_empty", "suggested_style_present", "image_file_exists", "image_url_present"]
            )
        if intent == "clarification_needed":
            expected_artifacts.append("clarification_message")
            validation_requirements.append("assistant_message_present")

        plan = {
            "required_agents": required_agents,
            "needs_rag_check": True,
            "expected_artifacts": expected_artifacts,
            "validation_requirements": validation_requirements,
        }
        state["execution_plan"] = plan
        self._add_step(state, "create_plan_node", "Created high-level execution plan.", "create_plan", str(plan))
        return state

    def rag_decision_node(self, state: ManagerChatState) -> ManagerChatState:
        t0 = datetime.utcnow()
        rag_needed = self.rag_service.is_needed(state["user_message"])
        state["rag_needed"] = rag_needed
        status = "success" if rag_needed else "skipped"
        observation = (
            "RAG selected because the request mentions memory, sources, documents or context."
            if rag_needed
            else "RAG skipped because no retrieval keywords were detected."
        )
        self._add_step(state, "rag_decision_node", "Checked whether retrieval context is needed.", "decide_rag", observation, status)
        self.log_service.add_log(
            agent="manager_agent",
            action="manager_chat",
            input_summary=state["user_message"][:300],
            status=status,
            duration_ms=self._ms(t0),
            run_id=state.get("trace_id"),
            step="rag_decision",
            decision=observation,
        )
        return state

    def rag_retrieval_node(self, state: ManagerChatState) -> ManagerChatState:
        t0 = datetime.utcnow()
        try:
            rag_context = self.rag_service.retrieve(state["user_message"], state.get("context"))
            state["rag_context"] = rag_context or None
            if rag_context:
                lines = [line for line in rag_context.splitlines() if line.strip()]
                observation = f"Retrieved {len(lines)} memory item(s). Summary: {rag_context[:240]}"
                status = "success"
            else:
                observation = "RAG retrieval attempted, but no memory context was available."
                status = "warning"
                state["warnings"].append(observation)
        except Exception as exc:
            observation = f"RAG retrieval failed safely: {type(exc).__name__}: {exc}"
            status = "warning"
            state["rag_context"] = None
            state["warnings"].append(observation)

        self._add_step(state, "rag_retrieval_node", "RAG retrieval path executed.", "retrieve_rag_context", observation, status)
        self.log_service.add_log(
            agent="manager_agent",
            action="manager_chat",
            input_summary=state["user_message"][:300],
            status="success" if status == "success" else "skipped",
            duration_ms=self._ms(t0),
            run_id=state.get("trace_id"),
            step="rag_retrieval",
            tool_called="mcp_memory_search",
            output_summary=observation[:300],
        )
        return state

    def route_by_intent_node(self, state: ManagerChatState) -> ManagerChatState:
        observation = {
            "text_only": "Route to TextAgent.",
            "image_only": "Route to ImageAgent.",
            "text_and_image": "Route to TextAgent first, then ImageAgent.",
            "clarification_needed": "Route to clarification response.",
        }.get(state["intent"], "Unknown intent.")
        self._add_step(state, "route_by_intent", f"Routing selected for intent={state['intent']}.", "route_by_intent", observation)
        return state

    def text_agent_node(self, state: ManagerChatState) -> ManagerChatState:
        t0 = datetime.utcnow()
        feedback = state.get("validation_feedback", {}).get("text")
        try:
            result = TextAgent(self.hf_factory(), self.trace_service).generate(
                task=state["user_message"],
                trace=state["trace"],
                platform=state.get("platform"),
                tone=self._context_value(state.get("context"), "tone", "professional"),
                target_audience=self._context_value(state.get("context"), "target_audience"),
                context=state.get("context"),
                rag_context=state.get("rag_context"),
                validation_feedback=feedback,
            )
            state["generated_artifacts"]["text"] = result
            self._remember_agent(state, "TextAgent")
            self._save_specialist_chat(state, "text_agent", state["user_message"], "Text artifact generated.", "text")
            self._add_step(state, "text_agent_node", "TextAgent completed successfully.", "call_text_agent", "Text artifact stored in graph state.")
            self.log_service.add_log(
                agent="text_agent",
                action="manager_chat",
                input_summary=state["user_message"][:300],
                status="success",
                duration_ms=self._ms(t0),
                run_id=state.get("trace_id"),
                step="generate_text",
                tool_called="huggingface_generate_text",
                decision=f"graph_node=text_agent_node; retry_count={state['text_retry_count']}",
                output_summary=f"{len(result.get('generated_text', ''))} chars, {len(result.get('hashtags', []))} hashtags",
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            state["errors"].append(error)
            state["status"] = "error"
            self._add_step(state, "text_agent_node", "TextAgent failed.", "call_text_agent", error, "error")
            self.log_service.add_log(
                agent="text_agent",
                action="manager_chat",
                input_summary=state["user_message"][:300],
                status="error",
                duration_ms=self._ms(t0),
                run_id=state.get("trace_id"),
                step="generate_text",
                tool_called="huggingface_generate_text",
                decision=f"graph_node=text_agent_node; retry_count={state['text_retry_count']}",
                output_summary=error[:300],
            )
        return state

    def image_agent_node(self, state: ManagerChatState) -> ManagerChatState:
        t0 = datetime.utcnow()
        feedback = state.get("validation_feedback", {}).get("image")
        try:
            result = ImageAgent(self.hf_factory(), self.trace_service, image_storage=self.image_storage).generate_image(
                task=state["user_message"],
                trace=state["trace"],
                platform=state.get("platform"),
                visual_style=self._context_value(state.get("context"), "visual_style"),
                context=state.get("context"),
                rag_context=state.get("rag_context"),
                validation_feedback=feedback,
            )
            state["generated_artifacts"]["image"] = result
            self._remember_agent(state, "ImageAgent")
            status = "partial_success" if result.get("partial_success") else "success"
            self._save_specialist_chat(state, "image_agent", state["user_message"], "Image artifact generated.", "image")
            self._add_step(
                state,
                "image_agent_node",
                "ImageAgent completed with image artifact." if status == "success" else "ImageAgent returned prompt-only partial success.",
                "call_image_agent",
                self._image_summary(result),
                status,
            )
            self.log_service.add_log(
                agent="image_agent",
                action="manager_chat",
                input_summary=state["user_message"][:300],
                status="success" if status == "success" else "error",
                duration_ms=self._ms(t0),
                run_id=state.get("trace_id"),
                step="generate_image",
                tool_called="huggingface_text_to_image",
                decision=f"graph_node=image_agent_node; retry_count={state['image_retry_count']}",
                output_summary=self._image_summary(result)[:300],
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            state["errors"].append(error)
            state["status"] = "error"
            self._add_step(state, "image_agent_node", "ImageAgent failed.", "call_image_agent", error, "error")
            self.log_service.add_log(
                agent="image_agent",
                action="manager_chat",
                input_summary=state["user_message"][:300],
                status="error",
                duration_ms=self._ms(t0),
                run_id=state.get("trace_id"),
                step="generate_image",
                tool_called="huggingface_text_to_image",
                decision=f"graph_node=image_agent_node; retry_count={state['image_retry_count']}",
                output_summary=error[:300],
            )
        return state

    def clarification_node(self, state: ManagerChatState) -> ManagerChatState:
        t0 = datetime.utcnow()
        state["assistant_message"] = (
            "Soll ich Marketing-Text, einen Bildprompt mit Bildgenerierung oder beides erstellen? "
            "Nenne gern auch Plattform, Zielgruppe und Tonalitaet."
        )
        state["status"] = "needs_input"
        self._add_step(state, "clarification_node", "The request is unclear.", "ask_clarification", "No specialist agent or HuggingFace call was made.", "needs_input")
        self.log_service.add_log(
            agent="manager_agent",
            action="manager_chat",
            input_summary=state["user_message"][:300],
            status="skipped",
            duration_ms=self._ms(t0),
            run_id=state.get("trace_id"),
            step="ask_clarification",
            decision="Intent unclear - asked user for text/image/both + platform/audience/tone",
        )
        return state

    def validation_node(self, state: ManagerChatState) -> ManagerChatState:
        feedback: dict[str, Any] = {}
        artifacts = state["generated_artifacts"]
        intent = state["intent"]

        if intent in {"text_only", "text_and_image"}:
            text_feedback = self._validate_text(artifacts.get("text"), state.get("platform"))
            if text_feedback:
                feedback["text"] = "; ".join(text_feedback)

        if intent in {"image_only", "text_and_image"}:
            image_feedback = self._validate_image(artifacts.get("image"))
            if image_feedback:
                feedback["image"] = "; ".join(image_feedback)

        if intent == "clarification_needed" and not state.get("assistant_message"):
            feedback["manager"] = "assistant_message missing"

        state["validation_feedback"] = feedback
        result = self._validation_result(state, feedback)
        state["validation_result"] = result

        if result == "valid":
            state["status"] = "success"
        elif result == "partial_success":
            state["status"] = "partial_success"
        elif result == "failed":
            state["status"] = "error"
        elif result in {"retry_text", "retry_image"}:
            state["status"] = "retrying"

        self._add_step(
            state,
            "validation_node",
            f"Validation result: {result}.",
            "validate_results",
            str({"feedback": feedback, "text_retry_count": state["text_retry_count"], "image_retry_count": state["image_retry_count"]}),
            "success" if result == "valid" else result,
        )
        return state

    def assemble_response_node(self, state: ManagerChatState) -> ManagerChatState:
        artifacts = state["generated_artifacts"]
        intent = state["intent"]
        image = artifacts.get("image") or {}
        text_ok = bool((artifacts.get("text") or {}).get("generated_text"))
        image_ok = self._image_file_available(image)
        image_prompt_only = bool(image.get("image_prompt")) and not image_ok

        if intent == "clarification_needed":
            observation = "Clarification response kept."
        elif state["status"] == "error":
            if text_ok or image_prompt_only or image_ok:
                state["status"] = "partial_success"
                state["assistant_message"] = self._partial_message(text_ok, image_ok, image_prompt_only)
                observation = "Partial response assembled after validation failure."
            else:
                state["assistant_message"] = "Der Agenten-Workflow ist fehlgeschlagen. Details stehen im Trace."
                observation = "Failure response assembled."
        elif intent == "text_only":
            state["assistant_message"] = "Der TextAgent hat Marketing-Text erstellt."
            observation = "Text-only success response assembled."
        elif intent == "image_only":
            if image_ok:
                state["assistant_message"] = "Der ImageAgent hat einen Bildprompt erstellt und daraus ein Bild generiert."
                observation = "Image-only success response assembled."
            else:
                state["status"] = "partial_success"
                state["assistant_message"] = "Der Bildprompt wurde erstellt, die eigentliche Bildgenerierung ist jedoch fehlgeschlagen."
                observation = "Image prompt-only partial success response assembled."
        elif intent == "text_and_image":
            if text_ok and image_ok:
                state["assistant_message"] = "Der TextAgent hat Marketing-Text erstellt und der ImageAgent hat daraus ein Bild generiert."
                observation = "Combined success response assembled."
            else:
                state["status"] = "partial_success"
                state["assistant_message"] = self._partial_message(text_ok, image_ok, image_prompt_only)
                observation = "Combined partial response assembled."
        else:
            state["assistant_message"] = "Der Agenten-Workflow konnte die Anfrage nicht eindeutig verarbeiten."
            observation = "Fallback response assembled."

        self._add_step(
            state,
            "assemble_response_node",
            "Final chat response assembled from actual graph artifacts.",
            "assemble_response",
            observation,
            state.get("status", "success"),
        )
        return state

    def save_trace_node(self, state: ManagerChatState) -> ManagerChatState:
        image = (state["generated_artifacts"].get("image") or {})
        metadata = {
            "trace_id": state["trace_id"],
            "used_agents": state["used_agents"],
            "graph_node": "save_trace_node",
            "artifact_types": list(state["generated_artifacts"].keys()),
            "status": state["status"],
            "image_filename": image.get("image_filename"),
            "image_url": image.get("image_url"),
            "retry_count": {"text": state["text_retry_count"], "image": state["image_retry_count"]},
        }
        self.chat_service.add_message(state["chat"], "USER", state["user_message"], {"context": state.get("context") or {}, "trace_id": state["trace_id"]})
        self.chat_service.add_message(state["chat"], "AGENT", state["assistant_message"], metadata)
        state["trace"]["metadata"].update(metadata)
        self.trace_service.store.save(state["trace"])
        self._add_step(
            state,
            "save_trace_node",
            "Chat messages, trace metadata and specialist logs are saved.",
            "persist_chat_trace_and_logs",
            f"Saved chat {state['chat_id']} with trace {state['trace_id']}.",
            state.get("status", "success"),
        )
        return state

    def maybe_rag_router(self, state: ManagerChatState) -> str:
        return "rag_retrieval_node" if state.get("rag_needed") else "route_by_intent"

    def intent_router(self, state: ManagerChatState) -> str:
        if state["intent"] == "text_only":
            return "text_agent_node"
        if state["intent"] == "image_only":
            return "image_agent_node"
        if state["intent"] == "text_and_image":
            return "text_agent_node"
        return "clarification_node"

    def after_text_router(self, state: ManagerChatState) -> str:
        return "image_agent_node" if state["intent"] == "text_and_image" else "validation_node"

    def retry_router(self, state: ManagerChatState) -> str:
        result = state.get("validation_result")
        if result == "retry_text" and state["text_retry_count"] == 0:
            state["text_retry_count"] += 1
            self._add_step(state, "validation_node", "Retrying TextAgent once.", "retry_text", str(state.get("validation_feedback", {}).get("text")), "retry_text")
            self.log_service.add_log(
                agent="text_agent",
                action="manager_chat_retry",
                input_summary=state["user_message"][:300],
                status="skipped",
                duration_ms=0,
                run_id=state.get("trace_id"),
                step="retry_text",
                decision=str(state.get("validation_feedback", {}).get("text")),
            )
            return "text_agent_node"
        if result == "retry_image" and state["image_retry_count"] == 0:
            state["image_retry_count"] += 1
            self._add_step(state, "validation_node", "Retrying ImageAgent once.", "retry_image", str(state.get("validation_feedback", {}).get("image")), "retry_image")
            self.log_service.add_log(
                agent="image_agent",
                action="manager_chat_retry",
                input_summary=state["user_message"][:300],
                status="skipped",
                duration_ms=0,
                run_id=state.get("trace_id"),
                step="retry_image",
                decision=str(state.get("validation_feedback", {}).get("image")),
            )
            return "image_agent_node"
        return "assemble_response_node"

    def _add_step(
        self,
        state: ManagerChatState,
        agent: str,
        decision: str,
        action: str,
        observation: str,
        status_value: str = "success",
    ) -> None:
        step = self.trace_service.add_step(state["trace"], agent, decision, action, observation, status_value)
        state["trace_steps"].append(step)

    def _classify(self, message: str) -> AgentIntent:
        return self.intent_classifier.classify_intent(message)

    def _validate_text(self, artifact: dict[str, Any] | None, platform: str | None) -> list[str]:
        issues = []
        if not artifact:
            return ["text artifact missing"]
        generated_text = artifact.get("generated_text")
        if not generated_text or not str(generated_text).strip():
            issues.append("generated_text missing")
        elif len(str(generated_text).strip()) < 40:
            issues.append("generated_text too short")
        if "hashtags" not in artifact:
            issues.append("hashtags field missing")
        if platform and platform.lower() in {"linkedin", "instagram", "x"} and not artifact.get("hashtags"):
            issues.append(f"hashtags missing for {platform}")
        return issues

    def _validate_image(self, artifact: dict[str, Any] | None) -> list[str]:
        issues = []
        if not artifact:
            return ["image artifact missing"]
        prompt = artifact.get("image_prompt")
        if not prompt or not str(prompt).strip():
            issues.append("image_prompt missing")
        elif len(str(prompt).strip()) < 30:
            issues.append("image_prompt too short")
        if not artifact.get("suggested_style"):
            issues.append("suggested_style missing")
        if artifact.get("partial_success") or artifact.get("image_error"):
            issues.append(f"image generation failed: {artifact.get('image_error', 'unknown error')}")
        if not artifact.get("image_url"):
            issues.append("image_url missing")
        if not artifact.get("image_filename"):
            issues.append("image_filename missing")
        if artifact.get("image_content_type") not in {"image/png"}:
            issues.append("unsupported image_content_type")
        if artifact.get("image_filename") and not self._image_file_available(artifact):
            issues.append("generated image file missing")
        return issues

    def _validation_result(self, state: ManagerChatState, feedback: dict[str, Any]) -> str:
        if not feedback:
            return "valid"
        image_artifact = state["generated_artifacts"].get("image") or {}
        if "text" in feedback and state["text_retry_count"] == 0:
            return "retry_text"
        if "image" in feedback and state["image_retry_count"] == 0 and image_artifact.get("retryable", True):
            return "retry_image"
        if image_artifact.get("image_prompt") and not self._image_file_available(image_artifact):
            return "partial_success"
        return "failed"

    def _image_file_available(self, artifact: dict[str, Any]) -> bool:
        return bool(artifact.get("image_url") and self.image_storage.exists(artifact.get("image_filename")))

    def _save_specialist_chat(self, state: ManagerChatState, agent: str, user_message: str, assistant_message: str, artifact_type: str) -> None:
        chat = self.chat_service.get_or_create_chat(state["post_id"], agent=agent)
        metadata = {"trace_id": state["trace_id"], "graph_node": f"{artifact_type}_agent_node", "artifact_type": artifact_type}
        self.chat_service.add_message(chat, "USER", user_message, metadata)
        self.chat_service.add_message(chat, "AGENT", assistant_message, metadata)

    def _remember_agent(self, state: ManagerChatState, agent: str) -> None:
        if agent not in state["used_agents"]:
            state["used_agents"].append(agent)

    def _image_summary(self, artifact: dict[str, Any]) -> str:
        if artifact.get("image_url"):
            return f"Image prompt and file ready: {artifact.get('image_filename')} -> {artifact.get('image_url')}"
        return f"Prompt ready but image unavailable: {artifact.get('image_error', 'unknown error')}"

    def _partial_message(self, text_ok: bool, image_ok: bool, image_prompt_only: bool) -> str:
        parts = []
        if text_ok:
            parts.append("Der TextAgent hat Marketing-Text erstellt.")
        if image_ok:
            parts.append("Der ImageAgent hat einen Bildprompt erstellt und daraus ein Bild generiert.")
        elif image_prompt_only:
            parts.append("Der Bildprompt wurde erstellt, die eigentliche Bildgenerierung ist jedoch fehlgeschlagen.")
        if not parts:
            return "Der Agenten-Workflow konnte keine vollstaendigen Artefakte erzeugen. Details stehen im Trace."
        return " ".join(parts)

    def _platform_from_message(self, message: str) -> str | None:
        normalized = message.lower()
        for platform in ("linkedin", "instagram", "x", "blog", "tiktok", "facebook"):
            if platform in normalized:
                return platform
        return None

    def _context_value(
        self,
        context: str | dict[str, Any] | None,
        key: str,
        default: str | None = None,
    ) -> str | None:
        if isinstance(context, dict):
            return context.get(key, default)
        return default

    def _ms(self, start: datetime) -> int:
        return int((datetime.utcnow() - start).total_seconds() * 1000)
