from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from app.agents.manager_agent import ManagerIntentClassifier
from app.graphs.dependencies import GraphDependencies
from app.graphs.nodes.lifecycle import LifecycleNodes
from app.graphs.nodes.planning import PlanningNodes
from app.graphs.nodes.post_sync import PostSyncNodes
from app.graphs.nodes.rag import RagNodes
from app.graphs.nodes.response import ResponseNodes
from app.graphs.nodes.specialists import SpecialistNodes
from app.graphs.routers import GraphRouters
from app.graphs.state import ManagerChatState
from app.metrics import inc_manager_chat_request
from app.services.chat_service import ChatService
from app.services.huggingface_service import HuggingFaceService
from app.services.image_storage_service import ImageStorageService
from app.services.log_service import LogService
from app.services.post_repository import PostRepository
from app.services.rag_service import RAGService
from app.services.trace_service import TraceService

__all__ = ["ManagerChatGraph", "ManagerChatState"]


class ManagerChatGraph:
    def __init__(
        self,
        chat_service: ChatService,
        trace_service: TraceService,
        rag_service: RAGService,
        hf_factory: Callable[[], HuggingFaceService],
        log_service: LogService | None = None,
        image_storage: ImageStorageService | None = None,
        post_repository: PostRepository | None = None,
    ):
        self.chat_service = chat_service
        self.trace_service = trace_service
        self.rag_service = rag_service
        self.hf_factory = hf_factory
        self.log_service = log_service or LogService()
        self.image_storage = image_storage or ImageStorageService()
        self.post_repository = post_repository or PostRepository()
        self.intent_classifier = ManagerIntentClassifier(hf_factory=self.hf_factory)

        self.deps = GraphDependencies(
            chat_service=self.chat_service,
            trace_service=self.trace_service,
            rag_service=self.rag_service,
            hf_factory=self.hf_factory,
            log_service=self.log_service,
            image_storage=self.image_storage,
            intent_classifier=self.intent_classifier,
            post_repository=self.post_repository,
        )
        self.lifecycle_nodes = LifecycleNodes(self.deps)
        self.post_sync_nodes = PostSyncNodes(self.deps)
        self.planning_nodes = PlanningNodes(self.deps)
        self.rag_nodes = RagNodes(self.deps)
        self.specialist_nodes = SpecialistNodes(self.deps)
        self.response_nodes = ResponseNodes(self.deps)
        self.routers = GraphRouters(self.deps)
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
        inc_manager_chat_request(final_state.get("status") or "success")
        return self._result_dict(final_state)

    def generate(
        self,
        post_id: str,
        *,
        intent: str = "text_and_image",
    ) -> dict[str, Any]:
        """Run specialists for a complete Steckbrief (follow-up after generation_ack)."""
        final_state = self.graph.invoke(
            {
                "post_id": post_id,
                "chat_id": f"{post_id}::manager_agent",
                "user_message": "Generiere Text und Bild aus dem Steckbrief.",
                "force_generation": True,
                "forced_intent": intent,
            }
        )
        inc_manager_chat_request(final_state.get("status") or "success")
        return self._result_dict(final_state)

    def _result_dict(self, final_state: dict[str, Any]) -> dict[str, Any]:
        return {
            "chat_id": final_state["chat_id"],
            "assistant_message": final_state["assistant_message"],
            "used_agents": final_state["used_agents"],
            "generated_artifacts": final_state["generated_artifacts"],
            "trace_id": final_state["trace_id"],
            "post_updates": final_state.get("post_data_updates") or {},
            "missing_fields": final_state.get("post_data_missing") or [],
            "generation_pending": bool(final_state.get("generation_pending")),
        }

    def _build_graph(self):
        graph = StateGraph(ManagerChatState)
        graph.add_node("init_state_node", self.lifecycle_nodes.init_state_node)
        graph.add_node("collect_post_data_node", self.post_sync_nodes.collect_post_data_node)
        graph.add_node("classify_intent_node", self.planning_nodes.classify_intent_node)
        graph.add_node("create_plan_node", self.planning_nodes.create_plan_node)
        graph.add_node("rag_react_node", self.rag_nodes.rag_react_node)
        graph.add_node("route_by_intent", self.planning_nodes.route_by_intent_node)
        graph.add_node("text_agent_node", self.specialist_nodes.text_agent_node)
        graph.add_node("image_agent_node", self.specialist_nodes.image_agent_node)
        graph.add_node("clarification_node", self.specialist_nodes.clarification_node)
        graph.add_node("memory_answer_node", self.specialist_nodes.memory_answer_node)
        graph.add_node("memory_store_ack_node", self.specialist_nodes.memory_store_ack_node)
        graph.add_node("web_answer_node", self.specialist_nodes.web_answer_node)
        graph.add_node("post_status_node", self.specialist_nodes.post_status_node)
        graph.add_node("context_question_node", self.post_sync_nodes.context_question_node)
        graph.add_node("generation_ack_node", self.post_sync_nodes.generation_ack_node)
        graph.add_node("validation_node", self.response_nodes.validation_node)
        graph.add_node("assemble_response_node", self.response_nodes.assemble_response_node)
        graph.add_node("persist_post_node", self.post_sync_nodes.persist_post_node)
        graph.add_node("save_trace_node", self.lifecycle_nodes.save_trace_node)

        graph.add_edge(START, "init_state_node")
        graph.add_edge("init_state_node", "collect_post_data_node")
        graph.add_edge("collect_post_data_node", "classify_intent_node")
        graph.add_edge("classify_intent_node", "create_plan_node")
        graph.add_edge("create_plan_node", "rag_react_node")
        graph.add_edge("rag_react_node", "route_by_intent")
        graph.add_conditional_edges(
            "route_by_intent",
            self.routers.intent_router,
            {
                "text_agent_node": "text_agent_node",
                "image_agent_node": "image_agent_node",
                "clarification_node": "clarification_node",
                "memory_answer_node": "memory_answer_node",
                "memory_store_ack_node": "memory_store_ack_node",
                "web_answer_node": "web_answer_node",
                "post_status_node": "post_status_node",
                "context_question_node": "context_question_node",
                "generation_ack_node": "generation_ack_node",
            },
        )
        graph.add_conditional_edges(
            "text_agent_node",
            self.routers.after_text_router,
            {"image_agent_node": "image_agent_node", "validation_node": "validation_node"},
        )
        graph.add_edge("image_agent_node", "validation_node")
        graph.add_edge("clarification_node", "validation_node")
        graph.add_edge("memory_answer_node", "validation_node")
        graph.add_edge("memory_store_ack_node", "validation_node")
        graph.add_edge("web_answer_node", "validation_node")
        graph.add_edge("post_status_node", "validation_node")
        graph.add_conditional_edges(
            "validation_node",
            self.routers.retry_router,
            {
                "text_agent_node": "text_agent_node",
                "image_agent_node": "image_agent_node",
                "assemble_response_node": "assemble_response_node",
            },
        )
        # Ack and context questions are final chat answers; specialists run via /generate.
        graph.add_edge("context_question_node", "persist_post_node")
        graph.add_edge("generation_ack_node", "persist_post_node")
        graph.add_edge("assemble_response_node", "persist_post_node")
        graph.add_edge("persist_post_node", "save_trace_node")
        graph.add_edge("save_trace_node", END)
        return graph.compile()
