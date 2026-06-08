# Backend Agent Architecture

This backend keeps FastAPI as the API layer and uses LangGraph as the central orchestration layer for the Manager Agent workflow.

The goal is a clear Applied AI multi-agent backend:

- Manager chat endpoint powered by a LangGraph `StateGraph`
- Situation-dependent routing to TextAgent, ImageAgent, both, or clarification
- Visible structured execution trace
- HuggingFace generation through one service
- RAG prepared as a placeholder for later extension

## Why LangGraph Is Used

LangGraph makes the Manager workflow explicit. Instead of hiding orchestration inside one method, the backend models the workflow as named graph nodes with conditional edges.

That helps the project show:

- multi-step TAO-style execution
- real decisions
- different paths for different inputs
- readable error handling
- visible trace/log output for the frontend and project review

## ManagerChatGraph

The central graph lives in:

```text
app/graphs/manager_chat_graph.py
```

`POST /api/agents/manager/chat` calls this graph through `AgentService.manager_chat(...)`.

The graph state contains:

- `chat_id`
- `trace_id`
- `user_message`
- `context`
- `intent`
- `rag_needed`
- `rag_context`
- `used_agents`
- `generated_artifacts`
- `assistant_message`
- `trace_steps`
- `errors`
- `status`

## Graph Nodes

`init_state_node`

Creates or loads the chat, creates a trace, normalizes the message/context and initializes graph state.

`classify_intent_node`

Classifies the message as:

- `text_only`
- `image_only`
- `text_and_image`
- `clarification_needed`

Explicit overrides are handled first. For example, `Nur das Bild!` routes to `image_only` even if the message also says `Instagram Post`.

`rag_decision_node`

Checks whether the message mentions documents, PDFs, brand guidelines, knowledge base, sources or context. Sets `rag_needed`.

`rag_retrieval_node`

Placeholder only. If RAG is requested, it records:

```text
RAG requested, but retrieval is not implemented yet in this version.
```

`route_by_intent`

Chooses the graph path based on intent.

`text_agent_node`

Calls `TextAgent` only for `text_only` or `text_and_image`. Stores `generated_text` and `hashtags`.

`image_agent_node`

Calls `ImageAgent` only for `image_only` or `text_and_image`. Stores `image_prompt`, `negative_prompt_optional` and `suggested_style`.

Important: this node generates only an image prompt. It does not create an actual image file.

`clarification_node`

Asks whether the user wants marketing text, an image prompt or both. No HuggingFace call is made.

`validation_node`

Checks that the required artifacts exist for the selected intent.

`assemble_response_node`

Creates the final assistant message. Image responses clearly say that an image prompt was generated and no real image file is generated in this version.

`save_trace_node`

Saves chat messages and adds the final trace step.

## Conditional Routing

Graph flow:

```text
START
 -> init_state_node
 -> classify_intent_node
 -> rag_decision_node
 -> maybe RAG
 -> route_by_intent
 -> text_agent_node and/or image_agent_node, or clarification_node
 -> validation_node
 -> assemble_response_node
 -> save_trace_node
 -> END
```

For `text_and_image`, the graph runs:

```text
text_agent_node -> image_agent_node -> validation_node
```

For `image_only`, the graph runs:

```text
image_agent_node -> validation_node
```

No `TextAgent` step appears in an image-only trace.

## Agents

`TextAgent`

Generates marketing text such as posts, captions, descriptions, hashtags and CTAs through HuggingFace.

`ImageAgent`

Generates a production-ready image prompt through HuggingFace. Actual image generation is future work.

`BaseAgent`

Contains shared trace-writing behavior for direct agent calls and graph node calls.

`ManagerAgent`

Keeps the deterministic intent classification logic used by the LangGraph node. It is no longer the central orchestrator for `/api/agents/manager/chat`; LangGraph is.

## API Endpoints

`POST /api/agents/manager/chat`

Powered by LangGraph.

Input:

```json
{
  "message": "Create an Instagram caption and image prompt for a new AI course.",
  "chat_id": null,
  "context": {
    "tone": "friendly",
    "target_audience": "students"
  }
}
```

Output:

```json
{
  "chat_id": "uuid",
  "assistant_message": "string",
  "used_agents": ["TextAgent", "ImageAgent"],
  "generated_artifacts": {},
  "trace_id": "uuid"
}
```

Other endpoints:

- `GET /api/agents/chats/{chat_id}`
- `GET /api/agents/traces/{trace_id}`
- `POST /api/agents/text/generate`
- `POST /api/agents/image/generate-prompt`
- `GET /health`

Direct TextAgent and ImageAgent endpoints stay outside LangGraph.

## Trace Concept

The visible trace is not private chain-of-thought. It is a structured execution trace for the frontend and project review.

Each trace step contains:

- `index`
- `agent`
- `decision`
- `action`
- `observation`
- `status`
- `timestamp`

The trace is generated from real graph execution. It differs for:

- text-only request
- image-only request
- text and image request
- RAG-requested request
- clarification request
- HuggingFace error

## HuggingFace

The backend reads:

- `HF_TOKEN`
- `HF_MODEL_ID`

Default model:

```text
Qwen/Qwen2.5-7B-Instruct
```

HuggingFace is only initialized inside agent nodes that need model generation. Clarification requests do not call HuggingFace.

## RAG Placeholder

RAG is represented by `RAGService` and graph nodes:

- `rag_decision_node`
- `rag_retrieval_node`

Full retrieval is not implemented yet. The placeholder keeps the graph ready for later document retrieval without adding database or vector-store complexity now.

## Applied AI Requirements

This architecture supports grading requirements by providing:

- LangGraph-based multi-step agent workflow
- TAO-style visible trace
- deterministic but real situation-dependent routing
- TextAgent and ImageAgent delegation
- HuggingFace integration
- readable error handling
- RAG placeholder for future extension
