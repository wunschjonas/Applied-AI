# Frontend / Backend Alignment Review

This review compares the current LangGraph backend with the planned frontend workflow:

- Home: chat-centric workflow, current image preview, current text preview, publish action
- Image page: image editing chat, image uploads
- Text page: text editing chat
- Logs page: trace visualization
- RAG page: document management

The backend is in a good position because `/api/agents/manager/chat` is already graph-powered and returns `chat_id`, `generated_artifacts`, `used_agents` and `trace_id`. The main risk is that the current API is still mostly "single request -> generated artifacts", while the planned frontend is more like "ongoing workspace/session -> editable artifacts -> logs -> publish".

## Current Backend Strengths

- `ManagerChatGraph` already models a multi-step workflow with LangGraph nodes.
- Manager routing supports text-only, image-only, combined, clarification and RAG-placeholder paths.
- Every manager run returns a `trace_id`.
- Trace steps are structured enough for a Logs page.
- Direct TextAgent and ImageAgent endpoints are useful for page-specific tools.
- `chat_id` supports continuing a chat history.
- `context` can already carry flexible frontend state.

## Main Architectural Mismatches

### 1. No Durable "Project" Or "Workspace" Concept

Planned frontend:

- Home shows current text preview.
- Home shows current image preview.
- Image page edits the current image.
- Text page edits the current text.
- Publish action publishes the current combined state.

Current backend:

- Stores chats and traces.
- Returns generated artifacts inside a single response.
- Does not store a durable "current artifact set" for a campaign/project/workspace.

Risk:

The frontend will need to infer current text/image previews from chat messages or response metadata. That becomes fragile as soon as users edit text on the Text page, edit image prompts on the Image page, then return Home.

Minimal backend change recommended:

- Add an `artifact_session_id` or `project_id`.
- Store current artifacts separately from chat messages.
- Suggested storage:

```text
storage/data/artifact_sessions.json
```

Suggested artifact session shape:

```json
{
  "id": "uuid",
  "chat_id": "uuid",
  "current_text": {
    "generated_text": "string",
    "hashtags": ["#Example"],
    "updated_at": "timestamp"
  },
  "current_image": {
    "image_prompt": "string",
    "negative_prompt_optional": "string",
    "suggested_style": "string",
    "image_file_url": null,
    "updated_at": "timestamp"
  },
  "publish_status": "draft",
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

Keep this simple JSON storage for now. No database migration is needed yet.

### 2. Manager Response Does Not Return Stable Preview Fields

Planned frontend Home:

- Needs "current text preview".
- Needs "current image preview".
- Needs a publish button that can use the current generated state.

Current backend:

- Returns `generated_artifacts` with optional `text` and `image`.
- Does not return normalized preview fields.
- For image, backend only returns an image prompt, not an actual image preview.

Risk:

Frontend components need conditional parsing like `generated_artifacts.text.generated_text` and `generated_artifacts.image.image_prompt`, and will need to keep their own state.

Minimal backend change recommended:

- Keep `generated_artifacts`, but add stable top-level preview summary fields to manager responses:

```json
{
  "current_text_preview": "string-or-null",
  "current_image_prompt": "string-or-null",
  "current_image_url": null,
  "artifact_session_id": "uuid"
}
```

This avoids rewriting the graph and makes the Home page simpler.

### 3. No Page-Specific Chat Type

Planned frontend:

- Home has Manager chat.
- Image page has image editing chat.
- Text page has text editing chat.

Current backend:

- One chat history model with no `scope` or `agent_type`.
- Direct TextAgent/ImageAgent calls do not create chat history.

Risk:

The frontend cannot cleanly separate Home chat from Image page editing chat and Text page editing chat.

Minimal backend change recommended:

- Add `scope` to chat records and messages.
- Suggested scopes:

```text
manager
text
image
rag
publish
```

- Add optional `scope` to chat request schemas.
- Direct TextAgent/ImageAgent endpoints can remain as generation endpoints, but future page-chat endpoints should use scope:

```text
POST /api/agents/text/chat
POST /api/agents/image/chat
```

Do not implement these yet unless the frontend needs true chat on those pages. For now, reserve the schema concept.

### 4. Image Page Needs Uploads, But Backend Has No Upload Model

Planned Image page:

- image editing chat
- image uploads

Current backend:

- ImageAgent generates image prompts only.
- No upload endpoint.
- No file metadata storage.

Risk:

The frontend will have nowhere to send uploaded images or associate them with the image chat/session.

Minimal backend change recommended:

- Add a future `ImageAsset` model and route group, but keep implementation lightweight.
- Suggested future endpoints:

```text
POST /api/assets/images/upload
GET /api/assets/images/{image_id}
GET /api/assets/images?artifact_session_id=...
```

- Store metadata in:

```text
storage/data/image_assets.json
```

Suggested metadata:

```json
{
  "id": "uuid",
  "artifact_session_id": "uuid",
  "filename": "string",
  "content_type": "image/png",
  "storage_path": "string",
  "source": "upload",
  "created_at": "timestamp"
}
```

No real image generation should be added yet.

### 5. Text Page Needs Editing Semantics

Planned Text page:

- text editing chat
- likely iterative changes such as shorter, more formal, add hashtags, translate, rewrite CTA

Current backend:

- Direct TextAgent generates new text from a task.
- It does not know the current text unless the frontend sends it inside `context`.

Risk:

Text edits may regenerate from scratch instead of modifying the current artifact.

Minimal backend change recommended:

- Define `current_text` and `edit_instruction` in context convention.
- Later, add a dedicated request shape:

```json
{
  "artifact_session_id": "uuid",
  "current_text": "string",
  "edit_instruction": "Make it shorter and more motivational.",
  "platform": "linkedin",
  "tone": "professional"
}
```

- Add `TextAgent` prompt support for edit mode later.

For now, the frontend can pass current text in `context`, but the backend should document this convention before UI work starts.

### 6. Logs Page Needs Trace Listing, Not Only Trace Detail

Planned Logs page:

- trace visualization
- likely a list of recent traces, then detail view

Current backend:

- `GET /api/agents/traces/{trace_id}` exists.
- No endpoint to list traces.

Risk:

The frontend needs a `trace_id` before it can show anything. Logs page cannot show recent graph runs by itself.

Minimal backend change recommended:

- Add trace listing endpoint:

```text
GET /api/agents/traces
GET /api/agents/traces?chat_id=...
```

Return compact summaries:

```json
[
  {
    "trace_id": "uuid",
    "chat_id": "uuid",
    "created_at": "timestamp",
    "status": "success",
    "step_count": 10,
    "entrypoint": "manager_chat_langgraph"
  }
]
```

This is a small addition to `TraceService`, not a graph rewrite.

### 7. RAG Page Needs Document Management, But RAG Is Placeholder Only

Planned RAG page:

- document management

Current backend:

- `RAGService` only decides whether RAG is needed and returns a placeholder.
- No document upload/list/delete endpoints.
- No `documents.json`.

Risk:

The RAG page cannot be built except as a placeholder.

Minimal backend change recommended:

- Add document metadata storage before building the RAG UI:

```text
storage/data/documents.json
```

- Suggested future endpoints:

```text
POST /api/rag/documents/upload
GET /api/rag/documents
GET /api/rag/documents/{document_id}
DELETE /api/rag/documents/{document_id}
```

- Store only metadata and raw file path first. Chunking and embeddings can come later.

Suggested document shape:

```json
{
  "id": "uuid",
  "filename": "brand_guidelines.pdf",
  "content_type": "application/pdf",
  "storage_path": "string",
  "status": "uploaded",
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

### 8. Publish Action Has No Backend Contract

Planned Home:

- publish action

Current backend:

- Existing legacy post/campaign routes may exist, but the new agent architecture does not define publish.
- Manager artifacts are not tied to a publishable entity.

Risk:

Publish will either become a frontend-only fake action or require a rushed backend rewrite.

Minimal backend change recommended:

- Add a simple publish status to the artifact session:

```text
draft
ready
published
publish_failed
```

- Later add:

```text
POST /api/artifact-sessions/{artifact_session_id}/publish
```

Initial implementation can mark as `published` and record timestamp. Real external publishing can stay future work.

## Recommended Minimal Backend Changes Before Frontend Build

Do these before building the frontend UI:

1. Add `artifact_session_id` concept.
2. Persist current text/image artifacts outside chat messages.
3. Return stable preview fields from Manager chat:
   - `artifact_session_id`
   - `current_text_preview`
   - `current_image_prompt`
   - `current_image_url`
4. Add trace listing endpoint for Logs page.
5. Add chat `scope` field or at least reserve it in schemas.
6. Document context conventions for text/image editing.

Do these when the corresponding frontend page is started:

1. Image page: add image upload metadata and file handling.
2. RAG page: add document metadata and upload/list/delete endpoints.
3. Publish button: add artifact-session publish status endpoint.
4. Text page: add text edit endpoint or text chat endpoint.
5. Image page: add image edit endpoint or image chat endpoint.

## What Should Not Be Changed Yet

- Do not add real image generation yet.
- Do not add vector database or embeddings yet.
- Do not replace JSON storage with a database yet.
- Do not remove direct TextAgent/ImageAgent endpoints.
- Do not merge all page workflows into the Manager graph too early.

## Suggested API Shape For Frontend Stability

Near-term additions:

```text
GET /api/agents/traces
GET /api/agents/traces?chat_id=...
GET /api/artifact-sessions/{artifact_session_id}
PATCH /api/artifact-sessions/{artifact_session_id}
POST /api/artifact-sessions/{artifact_session_id}/publish
```

Later page-specific additions:

```text
POST /api/agents/text/chat
POST /api/agents/image/chat
POST /api/assets/images/upload
GET /api/assets/images?artifact_session_id=...
POST /api/rag/documents/upload
GET /api/rag/documents
DELETE /api/rag/documents/{document_id}
```

## Frontend Mapping

Home:

- Use `POST /api/agents/manager/chat`.
- Use `artifact_session_id` to load current artifacts.
- Show `current_text_preview`.
- Show `current_image_prompt` or future `current_image_url`.
- Use publish endpoint later.

Image page:

- Use `artifact_session_id`.
- Show/edit `current_image.image_prompt`.
- Upload image assets later.
- Use image chat endpoint later if iterative editing is needed.

Text page:

- Use `artifact_session_id`.
- Show/edit `current_text.generated_text`.
- Use text chat/edit endpoint later.

Logs page:

- Use `GET /api/agents/traces`.
- Use `GET /api/agents/traces/{trace_id}` for visualization.

RAG page:

- Use document endpoints once added.
- Until then, show RAG placeholder status.

## Bottom Line

The LangGraph architecture is strong enough for the planned frontend, but the backend needs a small persistent "artifact session" layer before frontend work begins. Without that, the UI will have to treat chat responses as the source of truth for previews, uploads, edits and publishing, which will become brittle quickly.

The smallest safe next step is not another agent feature. It is a stable artifact/session contract between the frontend and backend.
