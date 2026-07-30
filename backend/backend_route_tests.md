# Backend Route Tests

Deprecated: this file used to describe an older manual route test flow.

Use the current walkthrough instead:

```text
backend/docs/backend_agent_postman_walkthrough.md
```

Important current route corrections:

```text
GET /api/agents/manager/traces/{trace_id}
GET /api/agents/manager/chats/{chat_id}
GET /api/agents/text/chats/{chat_id}
GET /api/agents/image/chats/{chat_id}
POST /api/agents/image/generate
```

The old `/api/posts/{post_id}/agent-trace` route is not part of the current backend.
