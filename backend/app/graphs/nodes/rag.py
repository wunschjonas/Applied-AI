from __future__ import annotations

from datetime import datetime

from app.graphs.dependencies import GraphDependencies, StepRecorder
from app.graphs.state import ManagerChatState


class RagNodes:
    def __init__(self, deps: GraphDependencies):
        self.deps = deps
        self.recorder = StepRecorder(deps)

    def rag_decision_node(self, state: ManagerChatState) -> ManagerChatState:
        started_at = datetime.utcnow()
        rag_needed = self.deps.rag_service.is_needed(state["user_message"])
        state["rag_needed"] = rag_needed
        status = "success" if rag_needed else "skipped"
        observation = (
            "RAG selected because the request mentions memory, sources, documents or context."
            if rag_needed
            else "RAG skipped because no retrieval keywords were detected."
        )

        self.recorder.step(
            state,
            "rag_decision_node",
            "Checked whether retrieval context is needed.",
            "decide_rag",
            observation,
            status,
        )
        self.recorder.log(
            state,
            agent="manager_agent",
            status=status,
            step="rag_decision",
            started_at=started_at,
            decision=observation,
        )
        return state

    def rag_retrieval_node(self, state: ManagerChatState) -> ManagerChatState:
        started_at = datetime.utcnow()
        try:
            rag_context = self.deps.rag_service.retrieve(state["user_message"], state.get("context"))
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

        self.recorder.step(
            state,
            "rag_retrieval_node",
            "RAG retrieval path executed.",
            "retrieve_rag_context",
            observation,
            status,
        )
        self.recorder.log(
            state,
            agent="manager_agent",
            status="success" if status == "success" else "skipped",
            step="rag_retrieval",
            started_at=started_at,
            tool_called="mcp_memory_search",
            output_summary=observation[:300],
        )
        return state
