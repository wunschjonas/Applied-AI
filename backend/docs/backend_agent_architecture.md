# Backend Agent Architecture

This backend keeps FastAPI as the API layer and uses LangGraph as the only orchestration mechanism for the Manager Agent workflow.

## Stable Route Groups

Manager:

```text
POST /api/agents/manager/chat
GET /api/agents/manager/chats/{chat_id}
GET /api/agents/manager/traces/{trace_id}
GET /api/agents/manager/logs
```

Text:

```text
POST /api/agents/text/generate
POST /api/agents/text/chat
GET /api/agents/text/chats/{chat_id}
GET /api/agents/text/logs
```

Image:

```text
POST /api/agents/image/generate-prompt
POST /api/agents/image/generate
POST /api/agents/image/chat
GET /api/agents/image/chats/{chat_id}
GET /api/agents/image/logs
```

Posts, health and memory routes remain unchanged.

## Manager Workflow

The productive Manager endpoint calls:

```text
routes_manager_agent.py
-> AgentService.manager_chat()
-> ManagerChatGraph.run()
```

Graph flow:

```text
START
-> init_state_node
-> classify_intent_node
-> create_plan_node
-> rag_decision_node
-> optional rag_retrieval_node
-> route_by_intent
-> text_agent_node and/or image_agent_node, or clarification_node
-> validation_node
-> optional one-time retry
-> assemble_response_node
-> save_trace_node
-> END
```

The graph state tracks `chat_id`, `trace_id`, `post_id`, `user_message`, `context`, `intent`, `execution_plan`, `rag_needed`, `rag_context`, `generated_artifacts`, `used_agents`, `errors`, `warnings`, `status`, `validation_feedback`, `validation_result`, `text_retry_count` and `image_retry_count`.

## Intent Classification

`backend/app/agents/manager_agent.py` now contains only the isolated `AgentIntent` data class and `ManagerIntentClassifier`.

It classifies:

```text
text_only
image_only
text_and_image
clarification_needed
```

Explicit overrides such as `Nur das Bild!`, `nur text`, `only image` and `text only` are handled before keyword routing.

## Planning

`create_plan_node` stores high-level, non-private planning metadata:

```json
{
  "required_agents": ["TextAgent", "ImageAgent"],
  "needs_rag_check": true,
  "expected_artifacts": ["text", "image"],
  "validation_requirements": [
    "text_not_empty",
    "hashtags_present",
    "image_file_exists",
    "image_url_present"
  ]
}
```

This plan is written to the structured trace.

## RAG / MCP Memory

`rag_decision_node` uses `RAGService.is_needed()`.

`rag_retrieval_node` uses the existing MCP Memory integration:

```text
RAGService.retrieve()
-> streamablehttp_client(MCP_MEMORY_URL)
-> ClientSession.call_tool("memory_search", ...)
```

If retrieval returns no content or fails, the workflow continues with a warning and no hardcoded fake retrieval result.

## TextAgent

`TextAgent.generate()` uses `HuggingFaceService.generate_text()` through the existing compatibility alias `generate()`.

Trace stages include:

```text
build_text_prompt
call_text_model
parse_text_response
return_text_artifact
```

The text artifact remains:

```json
{
  "generated_text": "...",
  "hashtags": ["#Example"]
}
```

## ImageAgent

`POST /api/agents/image/generate-prompt` remains prompt-only for backward compatibility.

`POST /api/agents/image/generate` and the Manager graph use `ImageAgent.generate_image()`, which runs two stages:

1. Generate a structured image prompt using the text model.
2. Generate an actual image via `huggingface_hub.InferenceClient.text_to_image()`.

Successful image artifacts contain:

```json
{
  "image_prompt": "...",
  "negative_prompt_optional": "...",
  "suggested_style": "...",
  "image_url": "/generated-images/{filename}",
  "image_filename": "{uuid}.png",
  "image_content_type": "image/png"
}
```

Partial success keeps the prompt and style, but sets image URL and filename to `null` and includes `image_error`.

Trace stages include:

```text
generate_image_prompt
call_text_to_image_model
store_generated_image
return_image_artifact
```

## HuggingFace Configuration

Text model:

```env
HF_MODEL_ID=Qwen/Qwen2.5-7B-Instruct
```

Image model:

```env
HF_IMAGE_MODEL_ID=black-forest-labs/FLUX.1-schnell
```

The same `HF_TOKEN` is used for text and image inference. The token must have the required Hugging Face Inference Providers permissions. Image generation may consume paid credits and can be subject to provider availability, rate limits and model-specific permissions.

The default image model is configurable and can be changed without editing `ImageAgent`.

## Image Storage

Generated images are stored locally under:

```text
backend/app/storage/generated_images/
```

FastAPI mounts this directory at:

```text
/generated-images
```

Returned image URLs are relative backend URLs:

```text
/generated-images/{uuid}.png
```

Filenames are UUID-based and never derived from user input. Raw image bytes and tokens are not logged.

Current limitation: generated image files and JSON runtime data may be lost when containers are recreated because no Docker volume is configured for backend storage.

## Validation And Retry

`validation_node` returns one of:

```text
valid
retry_text
retry_image
partial_success
failed
```

Text validation checks non-empty text, minimum length, `hashtags` field and platform-sensitive hashtags.

Image validation checks prompt, style, content type, image filename, existing local file and image URL.

The graph allows at most one retry per specialist:

```text
text_retry_count <= 1
image_retry_count <= 1
```

Image retry is only used for retryable/transient image errors. Missing token, permission errors and unsupported model errors do not retry.

## Observability

Observability remains agent-specific:

```text
manager_agent -> manager chat, manager logs, LangGraph trace
text_agent    -> text chat, text logs, direct text trace
image_agent   -> image chat, image logs, direct image trace
```

Trace steps are structured execution records, not private chain-of-thought. They include node/agent name, decision, action, observation, status and timestamp.
