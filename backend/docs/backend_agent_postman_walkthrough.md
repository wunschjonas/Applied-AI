# Backend Agent Postman Walkthrough

This walkthrough explains how to test the agent backend manually with Postman.

## Start Assumptions

- Backend runs on `http://localhost:8080`
- You use Postman for the HTTP requests
- Backend is started with Docker Compose
- `HF_TOKEN` and `HF_MODEL_ID` are configured in `backend/.env`
- Default model: `Qwen/Qwen2.5-7B-Instruct`

Start the backend:

```bash
docker compose up --build
```

In a second terminal, watch backend logs:

```bash
docker compose logs -f backend
```

Then execute the Postman requests one by one. While testing, watch the logs for route calls, validation errors, HuggingFace errors and agent activity.

## Recommended Live Testing Flow

1. Start Docker Compose.
2. Open live logs with `docker compose logs -f backend`.
3. Run the health check.
4. Run the three Manager Agent chat tests:
   - text only
   - image only
   - text and image
5. Run the Manager clarification test.
6. Run the Manager RAG placeholder test.
7. Copy the returned `chat_id` and call the chat history endpoint.
8. Copy the returned `trace_id` and call the trace endpoint.
9. Run direct TextAgent and ImageAgent tests.

For every Manager Agent request, first inspect `trace_id` in the response, then call:

```text
GET http://localhost:8080/api/agents/traces/{trace_id}
```

The response trace is the primary way to inspect the workflow.

## A. Health Check

Method:

```text
GET
```

URL:

```text
http://localhost:8080/health
```

Body:

```text
No body
```

Expected status:

```text
200 OK
```

Expected response shape:

```json
{
  "status": "ok",
  "service": "applied-ai-marketing-agent",
  "version": "0.2.0"
}
```

What to look for in the response:

- `status` is `ok`
- backend is reachable

What to look for in the logs:

- request to `GET /health`
- no error stack trace

## B. Manager Agent Chat - Text Only

Method:

```text
POST
```

URL:

```text
http://localhost:8080/api/agents/manager/chat
```

Headers:

```text
Content-Type: application/json
```

Body:

```json
{
  "message": "Erstelle einen LinkedIn Post über KI-Agenten im Marketing für Gründer. Der Ton soll professionell und motivierend sein."
}
```

Expected status:

```text
200 OK
```

Expected response shape:

```json
{
  "chat_id": "uuid",
  "assistant_message": "string",
  "used_agents": ["TextAgent"],
  "generated_artifacts": {
    "text": {
      "generated_text": "string",
      "hashtags": ["#Example"]
    }
  },
  "trace_id": "uuid"
}
```

What to look for in the response:

- `chat_id` exists
- `assistant_message` is not empty
- `used_agents` contains `TextAgent`
- `generated_artifacts.text.generated_text` exists
- `trace_id` exists

What to look for in the logs:

- request to `POST /api/agents/manager/chat`
- no HuggingFace error
- no validation error

## C. Manager Agent Chat - Image Only

Method:

```text
POST
```

URL:

```text
http://localhost:8080/api/agents/manager/chat
```

Headers:

```text
Content-Type: application/json
```

Body:

```json
{
  "message": "Erstelle mir einen Bild für einen Instagram Post über einen futuristischen Marketing-Agenten. Nur das Bild!"
}
```

Expected status:

```text
200 OK
```

Expected response shape:

```json
{
  "chat_id": "uuid",
  "assistant_message": "string",
  "used_agents": ["ImageAgent"],
  "generated_artifacts": {
    "image": {
      "image_prompt": "string",
      "negative_prompt_optional": "string",
      "suggested_style": "string"
    }
  },
  "trace_id": "uuid"
}
```

What to look for in the response:

- `used_agents` contains `ImageAgent`
- `used_agents` does not contain `TextAgent`
- `generated_artifacts.image.image_prompt` exists
- `generated_artifacts.text` does not exist
- `trace_id` exists
- `assistant_message` says an image prompt was generated
- `assistant_message` does not claim that an actual image file was created

What to look for in the logs:

- request to `POST /api/agents/manager/chat`
- no HuggingFace model error
- no empty response error

After this request, call the trace endpoint with the returned `trace_id`. The trace should show LangGraph manager nodes and `ImageAgent` steps only. No `TextAgent` step should appear.

## D. Manager Agent Chat - Text And Image

Method:

```text
POST
```

URL:

```text
http://localhost:8080/api/agents/manager/chat
```

Headers:

```text
Content-Type: application/json
```

Body:

```json
{
  "message": "Erstelle einen Instagram Post inklusive Caption, Hashtags und Bildidee für unser Applied AI Marketing-Agent Projekt."
}
```

Expected status:

```text
200 OK
```

Expected response shape:

```json
{
  "chat_id": "uuid",
  "assistant_message": "string",
  "used_agents": ["TextAgent", "ImageAgent"],
  "generated_artifacts": {
    "text": {
      "generated_text": "string",
      "hashtags": ["#Example"]
    },
    "image": {
      "image_prompt": "string",
      "negative_prompt_optional": "string",
      "suggested_style": "string"
    }
  },
  "trace_id": "uuid"
}
```

What to look for in the response:

- `used_agents` contains `TextAgent`
- `used_agents` contains `ImageAgent`
- `generated_artifacts.text.generated_text` exists
- `generated_artifacts.image.image_prompt` exists
- `trace_id` exists
- `assistant_message` does not claim that an actual image file was created

What to look for in the logs:

- one Manager Agent request
- HuggingFace activity for text generation
- HuggingFace activity for image prompt generation
- no error stack trace

## E. Manager Agent Chat - Clarification

Method:

```text
POST
```

URL:

```text
http://localhost:8080/api/agents/manager/chat
```

Headers:

```text
Content-Type: application/json
```

Body:

```json
{
  "message": "Hilf mir bitte mit unserem Applied AI Projekt."
}
```

Expected status:

```text
200 OK
```

Expected response shape:

```json
{
  "chat_id": "uuid",
  "assistant_message": "string",
  "used_agents": [],
  "generated_artifacts": {},
  "trace_id": "uuid"
}
```

What to look for in the response:

- `used_agents` is empty
- `generated_artifacts` is empty
- `assistant_message` asks whether the user wants text, image prompt, or both
- `trace_id` exists

What to look for in the trace:

- `clarification_node` appears
- no `TextAgent` step appears
- no `ImageAgent` step appears
- no HuggingFace call is required

## F. Manager Agent Chat - RAG Placeholder

Method:

```text
POST
```

URL:

```text
http://localhost:8080/api/agents/manager/chat
```

Headers:

```text
Content-Type: application/json
```

Body:

```json
{
  "message": "Schreibe einen LinkedIn Post basierend auf unserem PDF und den Brand Guidelines."
}
```

Expected status:

```text
200 OK
```

Expected response shape:

```json
{
  "chat_id": "uuid",
  "assistant_message": "string",
  "used_agents": ["TextAgent"],
  "generated_artifacts": {
    "text": {
      "generated_text": "string",
      "hashtags": ["#Example"]
    }
  },
  "trace_id": "uuid"
}
```

What to look for in the response:

- `TextAgent` is used because the request asks for a LinkedIn post
- `trace_id` exists

What to look for in the trace:

- `rag_decision_node` appears
- `rag_retrieval_node` appears
- observation says `RAG requested, but retrieval is not implemented yet in this version.`
- graph continues instead of failing

## G. Get Chat History

Use the `chat_id` from a Manager Agent response.

Method:

```text
GET
```

URL:

```text
http://localhost:8080/api/agents/chats/{chat_id}
```

Example:

```text
http://localhost:8080/api/agents/chats/PASTE_CHAT_ID_HERE
```

Body:

```text
No body
```

Expected status:

```text
200 OK
```

Expected response shape:

```json
{
  "chat_id": "uuid",
  "created_at": "timestamp",
  "updated_at": "timestamp",
  "messages": [
    {
      "role": "user",
      "content": "string",
      "timestamp": "timestamp",
      "metadata": {}
    },
    {
      "role": "assistant",
      "content": "string",
      "timestamp": "timestamp",
      "metadata": {
        "trace_id": "uuid",
        "used_agents": ["TextAgent"],
        "generated_artifacts": {}
      }
    }
  ]
}
```

What to look for in the response:

- `chat_id` matches the one from the Manager Agent response
- `messages` is a list
- list contains user and assistant messages
- assistant message metadata contains `trace_id`

What to look for in the logs:

- request to `GET /api/agents/chats/{chat_id}`
- no `404 Chat not found`

## H. Get Trace

Use the `trace_id` from an agent response.

Method:

```text
GET
```

URL:

```text
http://localhost:8080/api/agents/traces/{trace_id}
```

Example:

```text
http://localhost:8080/api/agents/traces/PASTE_TRACE_ID_HERE
```

Body:

```text
No body
```

Expected status:

```text
200 OK
```

Expected response shape:

```json
{
  "trace_id": "uuid",
  "chat_id": "uuid-or-null",
  "created_at": "timestamp",
  "steps": [
    {
      "index": 1,
      "agent": "init_state_node",
      "decision": "Initialized Manager chat graph state.",
      "action": "init_state",
      "observation": "Chat and trace are ready.",
      "status": "success",
      "timestamp": "timestamp"
    }
  ],
  "metadata": {}
}
```

What to look for in the response:

- `trace_id` matches the latest response
- `steps` is a list
- every step contains:
  - `index`
  - `agent`
  - `decision`
  - `action`
  - `observation`
  - `status`
  - `timestamp`
- Manager requests should show routing decisions
- LangGraph node names should appear, for example `init_state_node`, `classify_intent_node`, `rag_decision_node`, `route_by_intent`, `validation_node`, `assemble_response_node`, `save_trace_node`
- text requests should show `TextAgent`
- image requests should show `ImageAgent`
- clarification requests should show `clarification_node`
- RAG placeholder requests should show `rag_retrieval_node`

This is the visible execution trace. It is not private chain-of-thought. It can be used for the TAO-style project requirement because it shows the executed workflow, selected agents, actions, observations and statuses.

What to look for in the logs:

- request to `GET /api/agents/traces/{trace_id}`
- no `404 Trace not found`

## I. Direct TextAgent Test

Method:

```text
POST
```

URL:

```text
http://localhost:8080/api/agents/text/generate
```

Headers:

```text
Content-Type: application/json
```

Body:

```json
{
  "task": "Schreibe einen LinkedIn Post über die Vorteile von AI Agents im Marketing.",
  "platform": "linkedin",
  "tone": "professionell und klar",
  "target_audience": "Gründer und Marketing Manager",
  "context": "Applied AI Semesterprojekt an der HTWG Konstanz"
}
```

Expected status:

```text
200 OK
```

Expected response shape:

```json
{
  "generated_text": "string",
  "hashtags": ["#Example"],
  "trace_id": "uuid"
}
```

What to look for in the response:

- `generated_text` is not empty
- `hashtags` is a list
- `trace_id` exists

What to look for in the logs:

- request to `POST /api/agents/text/generate`
- HuggingFace call succeeds
- no empty response parsing error

## J. Direct ImageAgent Test

Method:

```text
POST
```

URL:

```text
http://localhost:8080/api/agents/image/generate-prompt
```

Headers:

```text
Content-Type: application/json
```

Body:

```json
{
  "task": "Erstelle einen Bildprompt für einen Social Media Post über AI Agents im Marketing.",
  "platform": "instagram",
  "visual_style": "modern, clean, futuristic",
  "context": "Das Bild soll professionell wirken und für ein Hochschulprojekt nutzbar sein."
}
```

Expected status:

```text
200 OK
```

Expected response shape:

```json
{
  "image_prompt": "string",
  "negative_prompt_optional": "string",
  "suggested_style": "modern, clean, futuristic",
  "trace_id": "uuid"
}
```

What to look for in the response:

- `image_prompt` is not empty
- `negative_prompt_optional` exists
- `suggested_style` exists
- `trace_id` exists
- string `context` is accepted and does not cause `422 Unprocessable Entity`

What to look for in the logs:

- request to `POST /api/agents/image/generate-prompt`
- HuggingFace call succeeds
- no model or token error

## Live Beobachten

Open logs while testing:

```bash
docker compose logs -f backend
```

Use the logs to inspect:

- incoming route calls
- FastAPI validation errors
- HuggingFace token or model errors
- unexpected stack traces

Optional improvement during development:

```python
logger.info("TextAgent started")
logger.info("ManagerAgent selected TextAgent and ImageAgent")
logger.info("HuggingFace response received")
```

The response trace is still the primary way to inspect the workflow. For each Manager request:

1. Send `POST /api/agents/manager/chat`
2. Copy `trace_id`
3. Send `GET /api/agents/traces/{trace_id}`
4. Inspect the structured steps

## Debugging

If you get `404 Not Found`:

- Check the route path in Postman.
- Check that `app.include_router(agents_router)` is present in `app/main.py`.
- Check that the backend container was rebuilt after code changes.

If you get `500` with `HF_TOKEN` missing:

- Check `backend/.env`.
- Confirm `HF_TOKEN` is set.
- Confirm Docker Compose loads the backend environment.
- Restart the backend container after changing `.env`.

If you get `500` with a model error:

- Check `HF_MODEL_ID`.
- Use the default model first: `Qwen/Qwen2.5-7B-Instruct`.
- Confirm the HuggingFace token has access to the model.

If you get an empty response:

- Check HuggingFace response parsing in `services/huggingface_service.py`.
- Check logs for `HuggingFace returned an empty response`.
- Retry with a shorter prompt to rule out model-side issues.

If trace retrieval returns `404 Trace not found`:

- Use the `trace_id` from the latest agent response.
- Do not use `chat_id` in the trace endpoint.

If chat retrieval returns `404 Chat not found`:

- Use the `chat_id` from a Manager Agent response.
- Direct TextAgent and ImageAgent calls do not create chat history.

If direct ImageAgent returns `422 Unprocessable Entity` for `context`:

- Confirm the schema allows `context` as `string`, `object`, or `null`.
- The direct image test above intentionally sends `context` as a string.
- Rebuild the backend container after schema changes.

## Minimal Acceptance Criteria

The backend is considered working if:

- `/health` returns `200 OK`
- Manager text-only request uses `TextAgent`
- Manager image-only request uses `ImageAgent`
- Manager image-only request with `Nur das Bild!` does not use `TextAgent`
- Manager combined request uses `TextAgent` and `ImageAgent`
- Manager clarification request does not call `TextAgent`, `ImageAgent`, or HuggingFace
- Manager RAG placeholder request returns a trace with `rag_retrieval_node`
- every agent run returns a `trace_id`
- trace endpoint returns multiple structured steps
- HuggingFace errors are readable and not empty detail messages
