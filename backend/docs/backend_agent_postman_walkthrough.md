# Backend Agent Postman Walkthrough

Base URL:

```text
http://localhost:8080
```

Start with Docker Compose:

```bash
docker compose up --build
```

Required local configuration in `backend/.env`:

```env
HF_TOKEN=hf_...
HF_MODEL_ID=Qwen/Qwen2.5-7B-Instruct
HF_IMAGE_MODEL_ID=black-forest-labs/FLUX.1-schnell
```

Image generation uses Hugging Face Inference Providers through `huggingface_hub.InferenceClient.text_to_image()`. Your token must have the required provider permission and image generation can consume credits, incur provider costs, hit rate limits or fail when the selected model/provider is unavailable.

## Quick Smoke Tests

### Health

```text
GET http://localhost:8080/health
```

Expected:

```json
{
  "status": "ok",
  "service": "applied-ai-marketing-agent",
  "version": "0.2.0"
}
```

### Manager Text Only

```text
POST http://localhost:8080/api/agents/manager/chat
```

```json
{
  "post_id": "test-text-post-001",
  "message": "Schreibe einen LinkedIn Post ueber KI-Agenten im Marketing.",
  "context": {
    "platform": "linkedin",
    "tone": "professionell"
  }
}
```

Expected:

```text
used_agents contains only TextAgent
generated_artifacts.text exists
generated_artifacts.image does not exist
trace_id exists
```

### Manager Image Only

```text
POST http://localhost:8080/api/agents/manager/chat
```

```json
{
  "post_id": "test-image-post-001",
  "message": "Erstelle ein futuristisches Instagram-Bild ueber einen AI Marketing-Agenten. Nur das Bild!",
  "context": {
    "platform": "instagram",
    "visual_style": "modern, clean, futuristic"
  }
}
```

Expected on full success:

```text
used_agents contains only ImageAgent
generated_artifacts.image.image_prompt exists
generated_artifacts.image.image_url exists
generated_artifacts.image.image_filename exists
generated_artifacts.text does not exist
trace includes generate_image_prompt, call_text_to_image_model, store_generated_image and return_image_artifact
```

Expected on partial success:

```text
image_prompt exists
image_error is readable
image_url is null
assistant_message says image generation failed
```

### Manager Combined

```text
POST http://localhost:8080/api/agents/manager/chat
```

```json
{
  "post_id": "test-combined-post-001",
  "message": "Erstelle eine Instagram Caption mit Hashtags und ein passendes Bild fuer unser Applied AI Marketing-Agent Projekt.",
  "context": {
    "platform": "instagram",
    "tone": "professionell und motivierend",
    "visual_style": "modern, clean, futuristic"
  }
}
```

Expected:

```text
used_agents contains TextAgent and ImageAgent
generated_artifacts.text exists
generated_artifacts.image exists
trace_id exists
```

### Manager Clarification

```text
POST http://localhost:8080/api/agents/manager/chat
```

```json
{
  "post_id": "test-clarification-post-001",
  "message": "Hilf mir bitte mit unserem Projekt.",
  "context": null
}
```

Expected:

```text
used_agents is []
generated_artifacts is {}
assistant_message asks for text, image or both
```

### Manager RAG / MCP Memory Path

```text
POST http://localhost:8080/api/agents/manager/chat
```

```json
{
  "post_id": "test-rag-post-001",
  "message": "Schreibe einen LinkedIn Post basierend auf unserem PDF und den Brand Guidelines.",
  "context": {
    "platform": "linkedin"
  }
}
```

Expected:

```text
rag_decision_node and rag_retrieval_node appear in the trace
workflow continues even when no memory context is returned
```

### Direct Image Prompt

```text
POST http://localhost:8080/api/agents/image/generate-prompt
```

```json
{
  "task": "Create an Instagram image prompt about an AI marketing agent.",
  "platform": "instagram",
  "visual_style": "modern, clean, futuristic",
  "context": "Professional university project visual."
}
```

Expected:

```text
prompt-only response with image_prompt, negative_prompt_optional, suggested_style and trace_id
no image_url field required by this route
```

### Direct Real Image Generation

```text
POST http://localhost:8080/api/agents/image/generate
```

```json
{
  "task": "Create an Instagram image about an AI marketing agent.",
  "platform": "instagram",
  "visual_style": "modern, clean, futuristic",
  "context": "Professional university project visual."
}
```

Expected:

```text
image_prompt
negative_prompt_optional
suggested_style
image_url
image_filename
image_content_type
trace_id
```

Open the generated image:

```text
http://localhost:8080/generated-images/{filename}
```

## Inspect Trace, Chats And Logs

Manager trace:

```text
GET http://localhost:8080/api/agents/manager/traces/{trace_id}
```

Manager chat:

```text
GET http://localhost:8080/api/agents/manager/chats/{post_id}::manager_agent
```

Text chat:

```text
GET http://localhost:8080/api/agents/text/chats/{post_id}::text_agent
```

Image chat:

```text
GET http://localhost:8080/api/agents/image/chats/{post_id}::image_agent
```

Logs:

```text
GET http://localhost:8080/api/agents/manager/logs
GET http://localhost:8080/api/agents/text/logs
GET http://localhost:8080/api/agents/image/logs
```

## Compatibility Notes

The Manager response fields remain unchanged:

```text
chat_id
assistant_message
used_agents
generated_artifacts
trace_id
```

The image prompt route remains backward compatible. Real image generation is available through the new `/api/agents/image/generate` route and through the Manager graph image path.
