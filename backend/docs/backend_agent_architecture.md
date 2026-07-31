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

## Graph Module Layout

`ManagerChatGraph` only owns dependency setup, node wiring and `run()`. Nodes, routers and supporting rules live in dedicated modules:

```text
app/graphs/
  manager_chat_graph.py    node wiring + run()
  state.py                 ManagerChatState
  dependencies.py          GraphDependencies + StepRecorder
  routers.py               maybe_rag / intent / after_text / retry routers
  nodes/
    lifecycle.py           init_state_node, save_trace_node
    post_sync.py           collect_brief_node, context_question_node, persist_post_node
    planning.py            classify_intent_node, create_plan_node, route_by_intent_node
    rag.py                 rag_decision_node, rag_retrieval_node
    specialists.py         text_agent_node, image_agent_node, clarification_node
    response.py            validation_node, assemble_response_node
  support/
    delegation.py          per-agent task briefs, refinement briefs, platform/context resolution
    post_fields.py         brief field extraction, questions, awaiting_field bookkeeping
    validation.py          ArtifactValidator with text and image rules
    messages.py            German assistant response texts
```

Node groups are small classes that receive a `GraphDependencies` instance (chat, trace, RAG, HuggingFace factory, log, image storage, intent classifier, post repository). `StepRecorder` writes a structured trace step and the matching agent log entry, so nodes no longer repeat that glue.

`ManagerChatState` is still importable from `manager_chat_graph`. The constructor gained an optional `post_repository` argument; `run()` now also returns `post_updates` and `missing_fields`.

Graph flow:

```text
START
-> init_state_node
-> collect_brief_node
-> classify_intent_node
-> create_plan_node
-> rag_decision_node
-> optional rag_retrieval_node
-> route_by_intent
-> context_question_node, or text_agent_node and/or image_agent_node, or clarification_node
-> validation_node                (skipped after context_question_node)
-> optional one-time retry
-> assemble_response_node         (skipped after context_question_node)
-> persist_post_node
-> save_trace_node
-> END
```

The graph state tracks `chat_id`, `trace_id`, `post_id`, `user_message`, `context`, `intent`, `execution_plan`, `rag_needed`, `rag_context`, `generated_artifacts`, `used_agents`, `errors`, `warnings`, `status`, `validation_feedback`, `validation_result`, `text_retry_count`, `image_retry_count`, plus the brief keys `post`, `brief_updates`, `brief_missing`, `brief_blocking`, `explicit_generate` and `followup_question`.

## Chat-Driven Post Brief

A post starts with mostly empty fields. The manager fills them from the conversation instead of requiring a form.

`collect_brief_node` loads the post through `PostRepository` and extracts fields from the message using the deterministic rules in `support/post_fields.py`:

- `platform` and `tone_of_voice` come from word-boundary alias matching and may correct an existing value.
- `topic` and `target_audience` come from markers such as `zum Thema`, `über`, `about`, `Zielgruppe` and only fill empty fields.
- The field the manager asked for last is stored on the post as `awaiting_field`; a free-text reply answers exactly that field, but only when nothing else matched, so answering a different question does not corrupt it.

Extracted values are written to `posts.json` immediately. `awaiting_field` is internal and never leaves the API, because `PostService._to_response()` only passes through schema fields.

Routing then follows two rules:

- `topic` or `platform` missing and no explicit generate order (`erstelle`, `schreibe`, `generiere`, `create`, ...): `context_question_node` asks for the next open field and no specialist runs.
- Otherwise the specialists run. If optional fields are still open, `persist_post_node` appends one follow-up question to the answer, so the brief keeps filling up without ever blocking generation.

If the `post_id` has no stored post, briefing is skipped entirely and the graph behaves as before. This keeps the direct API and tests usable without a post.

`create_plan_node` builds the specialist briefs from the stored post fields, with a context sent along the request taking precedence.

## Post Preview Persistence

`persist_post_node` merges the produced artifacts into `post.preview` and sets the status to `preview_ready`:

```json
{
  "generated_text": "...",
  "hashtags": ["#Example"],
  "post_structure": { "manager_response": "...", "used_agents": ["TextAgent"] },
  "image_prompt_optional": "...",
  "image_url": "/generated-images/{post_id}.png",
  "image_filename": "{post_id}.png"
}
```

The merge is field-wise, so a text-only turn keeps an image from an earlier turn and vice versa. `PostService.generate_preview()` no longer assembles the preview itself; it reloads the post the graph has written.

Posts are read and written through `app/services/post_repository.py`. That repository holds no agent imports, which is what lets graph nodes touch posts without a circular import through `PostService -> AgentService -> ManagerChatGraph`.

## Refinement Through The Specialist Chats

`POST /api/agents/text/chat` and `POST /api/agents/image/chat` are refinement endpoints, not free-form chat. Both load the stored post and its preview, brief the agent with the current artifact plus the requested change, really regenerate, and write the result back:

```text
text/chat  -> TextAgent.generate()      -> preview.generated_text + preview.hashtags
image/chat -> ImageAgent.generate_image() -> {post_id}.png + preview.image_url
```

The image brief also carries the current marketing text, so a regenerated visual stays close to the copy. Both responses now include `generated_artifacts` and `trace_id`, which is what the frontend renders.

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

## Planning And Delegation

`create_plan_node` stores high-level, non-private planning metadata plus one task brief per required specialist:

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
  ],
  "assignments": {
    "text": {
      "task": "Teilauftrag des ManagerAgent: Erstelle den Marketing-Text.\nNutzeranfrage: ...\nPost-Brief aus dem Manager-Chat:\n- Thema des Posts: ...",
      "platform": "instagram",
      "tone": "professional",
      "target_audience": null
    },
    "image": {
      "task": "Teilauftrag des ManagerAgent: Erstelle das Bildmotiv.\nNutzeranfrage: ...\nPost-Brief aus dem Manager-Chat:\n- Thema des Posts: ...",
      "platform": "instagram",
      "visual_style": null
    }
  }
}
```

The specialists receive their own brief instead of the raw chat message. Briefs are built deterministically in `support/delegation.py`, so delegation costs no extra model call. Platform, tone and audience are passed as arguments; topic and additional context are added to the task text, because the agents have no argument for them.

For `text_and_image`, `image_agent_node` appends the marketing text that `TextAgent` just produced to the image brief, so the visual is derived from the actual copy. The marketing text is truncated to 800 characters to keep the brief readable.

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

`generate_image()` accepts an optional `post_id`, which decides the stored filename. The Manager graph always passes it; the direct endpoint only does when the request body contains `post_id`.

Successful image artifacts contain:

```json
{
  "image_prompt": "...",
  "negative_prompt_optional": "...",
  "suggested_style": "...",
  "image_url": "/generated-images/{post_id}.png",
  "image_filename": "{post_id}.png",
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
/generated-images/{post_id}.png
```

Images generated through the Manager graph are named after the post they belong to, so each post keeps exactly one current image and a retry overwrites it. `ImageStorageService.save_png()` takes an optional `filename_stem`; without one it falls back to a random UUID, which is what the direct `POST /api/agents/image/generate` endpoint uses when no `post_id` is supplied.

Filenames are never derived from free user input: post IDs are server-generated UUIDs, and `is_safe_filename()` still enforces the UUID-plus-`.png` pattern before anything is written. Raw image bytes and tokens are not logged.

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

The rules themselves live in `app/graphs/support/validation.py` as `ArtifactValidator`, so they can be read and changed without touching graph wiring.

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

## Frontend Contract

The Angular frontend keeps one shared artifact state in `src/app/facades/artifact.facade.ts`, fed from two sources:

```text
chat responses      -> ArtifactFacade.applyArtifacts(response.generated_artifacts)
stored post state   -> ArtifactFacade.applyPreview(post.preview)
```

`ArtifactSyncService.loadForPost()` reads `GET /api/posts/{id}` rather than the preview endpoint, because that endpoint answers 404 while a post has no preview yet.

Home, Text Agent, Image Agent and Preview all read the same facade, so an artifact produced by one agent is visible on every page. `applyArtifacts` merges per artifact type, mirroring the backend preview merge.

Image URLs from the backend are relative. `toAbsoluteApiUrl()` in `src/app/core/api.config.ts` prefixes the backend origin, and the facade appends a timestamp query so a regenerated `{post_id}.png` is not served from the browser cache.

`Home` additionally shows the open brief fields from `missing_fields` and reloads the post list when `post_updates` is non-empty.
