# Phase 1 Agent Refactor Report

Stand: 2026-07-27

## Files Changed

```text
backend/.env.example
backend/app/agents/image_agent.py
backend/app/agents/manager_agent.py
backend/app/agents/text_agent.py
backend/app/api/routes_image_agent.py
backend/app/core/config.py
backend/app/graphs/manager_chat_graph.py
backend/app/main.py
backend/app/schemas/agent.py
backend/app/services/agent_service.py
backend/app/services/chat_service.py
backend/app/services/huggingface_service.py
backend/app/services/image_storage_service.py
backend/app/storage/json_store.py
docs/backend_route_tests.md
docs/backend_agent_architecture.md
docs/backend_agent_postman_walkthrough.md
docs/phase1_agent_refactor_report.md
backend/tests/test_phase1_agent_refactor.py
```

No frontend files were changed.

## Methods Removed

Historical Manager orchestration was removed from `ManagerAgent`:

```text
ManagerAgent.chat()
ManagerAgent._decide_route()
ManagerAgent._summarize_result()
ManagerAgent._make_image_wording_safe()
```

`backend/app/agents/manager_agent.py` now contains `AgentIntent`, `ManagerIntentClassifier` and a small compatibility `ManagerAgent` subclass.

## Graph Nodes

```text
init_state_node
classify_intent_node
create_plan_node
rag_decision_node
rag_retrieval_node
route_by_intent
text_agent_node
image_agent_node
clarification_node
validation_node
assemble_response_node
save_trace_node
```

## Conditional Edges

```text
rag_decision_node -> rag_retrieval_node | route_by_intent
route_by_intent -> text_agent_node | image_agent_node | clarification_node
text_agent_node -> image_agent_node | validation_node
validation_node -> text_agent_node | image_agent_node | assemble_response_node
```

## Retry Behavior

The graph tracks:

```text
text_retry_count
image_retry_count
validation_feedback
validation_result
```

Text and ImageAgent can each retry at most once. Image retry is limited to retryable/transient errors such as timeout, temporary provider failure, 503 or rate limiting. Missing token, permission denied and unsupported model errors do not retry.

## Selected Models

Text model default:

```text
Qwen/Qwen2.5-7B-Instruct
```

Image model default:

```text
black-forest-labs/FLUX.1-schnell
```

Both are configurable through environment variables.

## Provider Requirements

Image generation uses Hugging Face Inference Providers through `huggingface_hub.InferenceClient.text_to_image()`. The selected model must be available for text-to-image through the configured Hugging Face provider path. The token must have the required Inference Providers permission.

Hugging Face documentation currently documents text-to-image via `InferenceClient.text_to_image()` and lists recommended/provider-backed models such as `black-forest-labs/FLUX.1-Krea-dev`, `Qwen/Qwen-Image` and `ByteDance/Hyper-SD`. The Hugging Face model listing also shows `black-forest-labs/FLUX.1-schnell` as a text-to-image model with inference availability.

## New Image Route

```text
POST /api/agents/image/generate
```

Request reuses `ImagePromptRequest`:

```json
{
  "task": "Create an Instagram image about an AI marketing agent.",
  "platform": "instagram",
  "visual_style": "modern, clean, futuristic",
  "context": "Professional university project visual."
}
```

Response extends prompt fields with:

```text
image_url
image_filename
image_content_type
image_error
trace_id
```

`POST /api/agents/image/generate-prompt` remains prompt-only.

## Image Storage

Directory:

```text
backend/app/storage/generated_images/
```

Static URL mount:

```text
/generated-images/{uuid}.png
```

Filenames are UUID-based and never derived from user input. Raw image bytes are not stored in JSON and are not logged.

## Tests Added

`backend/tests/test_phase1_agent_refactor.py` adds fake-HF tests for:

```text
intent classification
graph routing
RAG path
text validation retry
image validation retry
prompt-only partial success
metadata persistence
traces.json initialization
safe filename generation
static image route
missing token readable error
```

Tests use fake Hugging Face responses and do not spend inference credits.

## Routes Verified

Route registration was updated to include:

```text
POST /api/agents/image/generate
```

Existing route groups and response fields were preserved.

## API Compatibility Statement

The existing Manager response fields remain unchanged:

```text
chat_id
assistant_message
used_agents
generated_artifacts
trace_id
```

Existing TextAgent, ImageAgent prompt-only, Manager, Posts, Health, Memory, Chat, Log and Trace routes remain in place.

`PostService.generate_preview()` remains compatible because text artifacts still live at `generated_artifacts.text` and image artifacts still live at `generated_artifacts.image`.

## Known Costs And Rate Limits

Text and image inference may consume Hugging Face credits or provider-specific paid usage. Image generation is usually more expensive than text generation and may hit rate limits sooner. Provider availability can vary by model, account permissions and current provider load.

## Current Persistence Limitation

JSON files and generated images are stored in the backend container filesystem. No database or Docker volume was added in Phase 1. Runtime data and generated images may be lost when containers are recreated.

## Known Limitations

```text
No database migration
No vector database
No real publishing
No image uploads
No image-to-image
No inpainting
No multiple image variants
No additional agent framework
```

The Manager workflow is agentic and observable, but intent classification remains deterministic and keyword-based.
