from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.image_agent import ImageAgent
from app.agents.manager_agent import AgentIntent, ManagerAgent
from app.agents.text_agent import TextAgent
from app.services.chat_service import ChatService
from app.services.huggingface_service import HuggingFaceService
from app.services.rag_service import RAGService
from app.services.trace_service import TraceService


class ManagerChatState(TypedDict, total=False):
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
    status: str
    platform: str | None


class ManagerChatGraph:
    def __init__(
        self,
        chat_service: ChatService,
        trace_service: TraceService,
        rag_service: RAGService,
        hf_factory: Callable[[], HuggingFaceService],
    ):
        self.chat_service = chat_service
        self.trace_service = trace_service
        self.rag_service = rag_service
        self.hf_factory = hf_factory
        self.graph = self._build_graph()

    def run(
        self,
        message: str,
        chat_id: str | None = None,
        context: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        final_state = self.graph.invoke(
            {
                "chat_id": chat_id,
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
        graph.add_edge("classify_intent_node", "rag_decision_node")
        graph.add_conditional_edges(
            "rag_decision_node",
            self.maybe_rag_router,
            {
                "rag_retrieval_node": "rag_retrieval_node",
                "route_by_intent": "route_by_intent",
            },
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
            {
                "image_agent_node": "image_agent_node",
                "validation_node": "validation_node",
            },
        )
        graph.add_edge("image_agent_node", "validation_node")
        graph.add_edge("clarification_node", "validation_node")
        graph.add_edge("validation_node", "assemble_response_node")
        graph.add_edge("assemble_response_node", "save_trace_node")
        graph.add_edge("save_trace_node", END)
        return graph.compile()

    def init_state_node(self, state: ManagerChatState) -> ManagerChatState:
        chat = self.chat_service.get_or_create_chat(state.get("chat_id"), agent="manager_agent")
        trace = self.trace_service.create_trace(
            chat_id=chat["chat_id"],
            metadata={"entrypoint": "manager_chat_langgraph", "graph": "ManagerChatGraph"},
        )
        new_state: ManagerChatState = {
            **state,
            "chat": chat,
            "chat_id": chat["chat_id"],
            "trace": trace,
            "trace_id": trace["trace_id"],
            "user_message": state["user_message"].strip(),
            "context": state.get("context"),
            "intent": "unclassified",
            "rag_needed": False,
            "rag_context": None,
            "used_agents": [],
            "generated_artifacts": {},
            "assistant_message": "",
            "trace_steps": [],
            "errors": [],
            "status": "running",
            "platform": self._platform_from_message(state["user_message"]),
        }
        self._add_step(
            new_state,
            "init_state_node",
            "Initialized Manager chat graph state.",
            "init_state",
            f"Chat {chat['chat_id']} and trace {trace['trace_id']} are ready.",
        )
        return new_state

    def classify_intent_node(self, state: ManagerChatState) -> ManagerChatState:
        intent = self._classify(state["user_message"])
        state["intent"] = intent.label
        self._add_step(
            state,
            "classify_intent_node",
            intent.decision,
            "classify_intent",
            intent.observation,
            "needs_input" if intent.needs_clarification else "success",
        )
        return state

    def rag_decision_node(self, state: ManagerChatState) -> ManagerChatState:
        rag_needed = self.rag_service.is_needed(state["user_message"])
        state["rag_needed"] = rag_needed
        self._add_step(
            state,
            "rag_decision_node",
            "Checked whether retrieval context is needed.",
            "decide_rag",
            "RAG placeholder selected." if rag_needed else "RAG not needed for this request.",
            "skipped" if not rag_needed else "success",
        )
        return state

    def rag_retrieval_node(self, state: ManagerChatState) -> ManagerChatState:
        state["rag_context"] = self.rag_service.retrieve(state["user_message"], state.get("context"))
        self._add_step(
            state,
            "rag_retrieval_node",
            "RAG was requested by the user message.",
            "retrieve_rag_context",
            state["rag_context"],
            "skipped",
        )
        return state

    def route_by_intent_node(self, state: ManagerChatState) -> ManagerChatState:
        observation = {
            "text_only": "Route to TextAgent.",
            "image_only": "Route to ImageAgent.",
            "text_and_image": "Route to TextAgent first, then ImageAgent.",
            "clarification_needed": "Route to clarification response.",
        }.get(state["intent"], "Unknown intent.")
        self._add_step(
            state,
            "route_by_intent",
            f"Routing selected for intent={state['intent']}.",
            "route_by_intent",
            observation,
        )
        return state

    def text_agent_node(self, state: ManagerChatState) -> ManagerChatState:
        try:
            result = TextAgent(self.hf_factory(), self.trace_service).generate(
                task=state["user_message"],
                trace=state["trace"],
                platform=state.get("platform"),
                tone=self._context_value(state.get("context"), "tone", "professional"),
                target_audience=self._context_value(state.get("context"), "target_audience"),
                context=state.get("context"),
            )
            state["generated_artifacts"]["text"] = result
            state["used_agents"].append("TextAgent")
            self._add_step(
                state,
                "text_agent_node",
                "TextAgent completed successfully.",
                "call_text_agent",
                "Text artifact stored in graph state.",
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            state["errors"].append(error)
            state["status"] = "error"
            self._add_step(state, "text_agent_node", "TextAgent failed.", "call_text_agent", error, "error")
        return state

    def image_agent_node(self, state: ManagerChatState) -> ManagerChatState:
        try:
            result = ImageAgent(self.hf_factory(), self.trace_service).generate_prompt(
                task=state["user_message"],
                trace=state["trace"],
                platform=state.get("platform"),
                visual_style=self._context_value(state.get("context"), "visual_style"),
                context=state.get("context"),
            )
            state["generated_artifacts"]["image"] = result
            state["used_agents"].append("ImageAgent")
            self._add_step(
                state,
                "image_agent_node",
                "ImageAgent completed successfully.",
                "call_image_agent",
                "Image prompt artifact stored in graph state. No image file was generated.",
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            state["errors"].append(error)
            state["status"] = "error"
            self._add_step(state, "image_agent_node", "ImageAgent failed.", "call_image_agent", error, "error")
        return state

    def clarification_node(self, state: ManagerChatState) -> ManagerChatState:
        state["assistant_message"] = (
            "Soll ich Marketing-Text, einen Bildprompt oder beides erstellen? "
            "Nenne gern auch Plattform, Zielgruppe und Tonalitaet."
        )
        state["status"] = "needs_input"
        self._add_step(
            state,
            "clarification_node",
            "The request is unclear.",
            "ask_clarification",
            "No HuggingFace call was made.",
            "needs_input",
        )
        return state

    def validation_node(self, state: ManagerChatState) -> ManagerChatState:
        missing = []
        artifacts = state["generated_artifacts"]
        if state["intent"] == "text_only" and "text" not in artifacts:
            missing.append("text")
        elif state["intent"] == "image_only" and "image" not in artifacts:
            missing.append("image")
        elif state["intent"] == "text_and_image":
            if "text" not in artifacts:
                missing.append("text")
            if "image" not in artifacts:
                missing.append("image")
        elif state["intent"] == "clarification_needed" and not state.get("assistant_message"):
            missing.append("assistant_message")

        if missing:
            state["status"] = "error"
            message = f"Missing required graph output: {', '.join(missing)}."
            state["errors"].append(message)
            state["assistant_message"] = f"Agent workflow failed: {message}"
            self._add_step(state, "validation_node", "Required outputs are missing.", "validate_outputs", message, "error")
        else:
            self._add_step(
                state,
                "validation_node",
                "Required outputs are present.",
                "validate_outputs",
                f"Validation passed for intent={state['intent']}.",
                state.get("status", "success") if state.get("status") in {"needs_input", "error"} else "success",
            )
        return state

    def assemble_response_node(self, state: ManagerChatState) -> ManagerChatState:
        if state["status"] == "error":
            observation = "Error response kept from validation."
        elif state["intent"] == "clarification_needed":
            observation = "Clarification response kept."
        elif state["intent"] == "image_only":
            state["assistant_message"] = (
                "Der ImageAgent hat einen Bildprompt erstellt. "
                "Ein echtes Bild wird in dieser Version noch nicht generiert."
            )
            observation = "Image prompt response assembled."
        elif state["intent"] == "text_only":
            state["assistant_message"] = "Der TextAgent hat Marketing-Text erstellt."
            observation = "Text response assembled."
        else:
            state["assistant_message"] = (
                "Der TextAgent hat Marketing-Text erstellt und der ImageAgent hat einen Bildprompt erstellt. "
                "Ein echtes Bild wird in dieser Version noch nicht generiert."
            )
            observation = "Combined text and image prompt response assembled."

        self._add_step(
            state,
            "assemble_response_node",
            "Final chat response assembled from graph state.",
            "assemble_response",
            observation,
            state.get("status", "success") if state.get("status") in {"needs_input", "error"} else "success",
        )
        return state

    def save_trace_node(self, state: ManagerChatState) -> ManagerChatState:
        self.chat_service.add_message(state["chat"], "USER", state["user_message"], {"context": state.get("context") or {}})
        self.chat_service.add_message(
            state["chat"],
            "AGENT",
            state["assistant_message"],
            {
                "trace_id": state["trace_id"],
                "used_agents": state["used_agents"],
                "generated_artifacts": state["generated_artifacts"],
                "status": state["status"],
            },
        )
        self._add_step(
            state,
            "save_trace_node",
            "Chat messages and trace are saved.",
            "save_chat_and_trace",
            f"Saved chat {state['chat_id']} with trace {state['trace_id']}.",
            state.get("status", "success") if state.get("status") in {"needs_input", "error"} else "success",
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
        classifier = ManagerAgent.__new__(ManagerAgent)
        return classifier.classify_intent(message)

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
