# Current Backend Agent Audit

Stand: 2026-07-27

## 1. Executive Summary

Das Backend ist eine kompakte FastAPI-Anwendung mit JSON-basierter Speicherung, direkter HuggingFace-Anbindung und einem bereits vorhandenen LangGraph-Manager-Workflow. Der produktive Manager-Chat läuft aktuell über `AgentService.manager_chat()` und `ManagerChatGraph.run()`, nicht mehr über die alte zentrale `ManagerAgent.chat()`-Methode.

`smolagents` wird im aktuellen Backend-Code nicht verwendet. Es gibt keine `smolagents`-Imports und keine `smolagents`-Dependency in `backend/requirements.txt`. LangGraph ist dagegen aktiv eingebunden über `langgraph.graph.StateGraph` in `backend/app/graphs/manager_chat_graph.py`.

Die FastAPI-Routenstruktur, JSON-Speicherung, Chat-Speicherung und Trace-Speicherung sind einfach und sollten für den geplanten Umbau stabil bleiben. Der kleinste sinnvolle Umbau betrifft vor allem `backend/app/graphs/manager_chat_graph.py` und eventuell `backend/app/agents/manager_agent.py`, weil dort Intent-Klassifikation und Orchestrierung noch teilweise doppelt oder historisch gewachsen sind.

Wichtig: Die bestehende Dokumentation ist teilweise veraltet. Besonders `docs/backend_agent_postman_walkthrough.md` nennt an mehreren Stellen Pfade wie `/api/agents/traces/{trace_id}` und `/api/agents/chats/{chat_id}`. Tatsächlich liegen die Trace- und Chat-History-Routen aktuell unter agent-spezifischen Prefixen wie `/api/agents/manager/traces/{trace_id}`, `/api/agents/manager/chats/{chat_id}`, `/api/agents/text/chats/{chat_id}` und `/api/agents/image/chats/{chat_id}`.

## 2. Relevante Ordnerstruktur

```text
backend/app
  main.py
  agents/
    base_agent.py
    image_agent.py
    manager_agent.py
    text_agent.py
  api/
    routes_image_agent.py
    routes_manager_agent.py
    routes_memory.py
    routes_posts.py
    routes_text_agent.py
  core/
    config.py
  graphs/
    manager_chat_graph.py
  schemas/
    agent.py
    chat.py
    logs.py
    post.py
    trace.py
  services/
    agent_service.py
    chat_service.py
    huggingface_service.py
    log_service.py
    post_service.py
    rag_service.py
    trace_service.py
  storage/
    json_store.py
    data/
      agent_logs.json
      campaigns.json
      chats.json
      posts.json
      previews.json
      traces.json
```

```text
backend/docs
  backend_agent_architecture.md
  backend_agent_postman_walkthrough.md
  frontend_backend_alignment_review.md
  current_backend_agent_audit.md
```

Backend-relevante Root- und Docker-Dateien:

```text
backend/requirements.txt
backend/Dockerfile
docker-compose.yml
```

`backend/app/__pycache__` und weitere `__pycache__`-Ordner existieren ebenfalls, sind aber Laufzeit-/Build-Artefakte und keine relevanten Quellcodedateien.

## 3. Backend-Start und Konfiguration

Die FastAPI-App wird in `backend/app/main.py` erstellt:

```python
app = FastAPI(...)
```

Der Docker-Startpfad liegt in `backend/Dockerfile`:

```text
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Der Backend-Service in `docker-compose.yml` baut aus `./backend`, veröffentlicht Port `8080:8080`, hängt von `memory` ab und setzt:

```text
MCP_MEMORY_URL=http://memory:8765/mcp
```

Aktive Router in `backend/app/main.py`:

```text
posts_router      -> backend/app/api/routes_posts.py
manager_router    -> backend/app/api/routes_manager_agent.py
text_router       -> backend/app/api/routes_text_agent.py
image_router      -> backend/app/api/routes_image_agent.py
memory_router     -> backend/app/api/routes_memory.py
```

Aktive Middleware:

```text
CORSMiddleware
  allow_origins=["*"]
  allow_credentials=True
  allow_methods=["*"]
  allow_headers=["*"]
```

Konfiguration kommt aus `backend/app/core/config.py` über `pydantic_settings.BaseSettings`.

Geladene Umgebungsvariablen:

```text
HF_TOKEN       -> settings.hf_token
HF_MODEL_ID    -> settings.hf_model_id, Default: Qwen/Qwen2.5-7B-Instruct
MCP_MEMORY_URL -> settings.mcp_memory_url, Default: http://localhost:8765/mcp
```

Weitere Settings:

```text
app_version = 0.2.0
data_dir = backend/app/storage/data
posts_file = posts.json
chats_file = chats.json
traces_file = traces.json
agent_logs_file = agent_logs.json
```

Die `.env` wird laut `Settings.Config.env_file` aus `backend/.env` geladen.

## 4. Aktuelle API-Routen

### Health

| Methode | Pfad | Request-Schema | Response-Schema | Service | Agent/Graph |
|---|---|---|---|---|---|
| GET | `/health` | keines | dict mit `status`, `service`, `version` | keiner | keiner |

### Manager-Agent

Router-Prefix: `/api/agents/manager`

| Methode | Pfad | Request-Schema | Response-Schema | Service | Agent/Graph |
|---|---|---|---|---|---|
| POST | `/api/agents/manager/chat` | `ManagerChatRequest` | `ManagerChatResponse` | `AgentService.manager_chat()` | `ManagerChatGraph` |
| GET | `/api/agents/manager/chats/{chat_id}` | Pfadparameter `chat_id` | `ChatHistoryResponse` | `ChatService.get_chat()` | keiner |
| GET | `/api/agents/manager/traces/{trace_id}` | Pfadparameter `trace_id` | `TraceResponse` | `TraceService.get_trace()` | keiner |
| GET | `/api/agents/manager/logs` | keines | `AgentLogsResponse` | `LogService.get_logs_by_agent("manager_agent")` | keiner |

`ManagerChatRequest`:

```text
message: str, 1..4000
post_id: str
context: str | dict | None
```

`ManagerChatResponse`:

```text
chat_id: str
assistant_message: str
used_agents: list[str]
generated_artifacts: dict
trace_id: str
```

### Text-Agent

Router-Prefix: `/api/agents/text`

| Methode | Pfad | Request-Schema | Response-Schema | Service | Agent/Graph |
|---|---|---|---|---|---|
| POST | `/api/agents/text/generate` | `TextGenerateRequest` | `TextGenerateResponse` | `AgentService.generate_text()` | `TextAgent` direkt, kein Graph |
| POST | `/api/agents/text/chat` | `TextAgentChatRequest` | `TextAgentChatResponse` | `AgentService.text_agent_chat()` | HuggingFace direkt, kein `TextAgent.generate()` |
| GET | `/api/agents/text/chats/{chat_id}` | Pfadparameter `chat_id` | `ChatHistoryResponse` | `ChatService.get_chat()` | keiner |
| GET | `/api/agents/text/logs` | keines | `AgentLogsResponse` | `LogService.get_logs_by_agent("text_agent")` | keiner |

### Image-Agent

Router-Prefix: `/api/agents/image`

| Methode | Pfad | Request-Schema | Response-Schema | Service | Agent/Graph |
|---|---|---|---|---|---|
| POST | `/api/agents/image/generate-prompt` | `ImagePromptRequest` | `ImagePromptResponse` | `AgentService.generate_image_prompt()` | `ImageAgent` direkt, kein Graph |
| POST | `/api/agents/image/chat` | `ImageAgentChatRequest` | `ImageAgentChatResponse` | `AgentService.image_agent_chat()` | HuggingFace direkt, kein `ImageAgent.generate_prompt()` |
| GET | `/api/agents/image/chats/{chat_id}` | Pfadparameter `chat_id` | `ChatHistoryResponse` | `ChatService.get_chat()` | keiner |
| GET | `/api/agents/image/logs` | keines | `AgentLogsResponse` | `LogService.get_logs_by_agent("image_agent")` | keiner |

### Posts und Preview

Router-Prefix: `/api/posts`

| Methode | Pfad | Request-Schema | Response-Schema | Service | Agent/Graph |
|---|---|---|---|---|---|
| POST | `/api/posts/init` | `PostInit` | `PostInitResponse` | `PostService.init_post()` | keiner |
| POST | `/api/posts` | `PostCreate` | `PostResponse` | `PostService.create_post()` | keiner |
| GET | `/api/posts` | keines | `list[PostResponse]` | `PostService.list_posts()` | keiner |
| GET | `/api/posts/{post_id}` | Pfadparameter `post_id` | `PostResponse` | `PostService.get_post()` | keiner |
| PUT | `/api/posts/{post_id}` | `PostUpdate` | `PostResponse` | `PostService.update_post()` | keiner |
| DELETE | `/api/posts/{post_id}` | Pfadparameter `post_id` | 204, kein Body | `PostService.delete_post()` | keiner |
| POST | `/api/posts/{post_id}/generate-preview` | Pfadparameter `post_id` | `PostResponse` | `PostService.generate_preview()` | ruft `AgentService.manager_chat()` -> `ManagerChatGraph` |
| GET | `/api/posts/{post_id}/preview` | Pfadparameter `post_id` | kein explizites Pydantic-Schema | `PostService.get_preview()` | keiner |

### Memory / RAG

Router-Prefix: `/api/memory`

| Methode | Pfad | Request-Schema | Response-Schema | Service | Agent/Graph |
|---|---|---|---|---|---|
| POST | `/api/memory/store` | lokale Klasse `MemoryStoreRequest` | lokale Klasse `MemoryStoreResponse` | `RAGService.store()` | MCP Memory Tool |
| GET | `/api/memory/search?q=...` | Queryparameter `q` | lokale Klasse `MemorySearchResponse` | `RAGService.retrieve()` | MCP Memory Tool |
| GET | `/api/memory/list` | keines | lokale Klasse `MemoryListResponse` | `RAGService.list_all()` | MCP Memory Tool |

Die Memory-Schemas sind direkt in `routes_memory.py` definiert, nicht in `backend/app/schemas`.

## 5. Aktuelle Agentenarchitektur

Existierende Agentenklassen:

```text
BaseAgent      -> backend/app/agents/base_agent.py
TextAgent      -> backend/app/agents/text_agent.py
ImageAgent     -> backend/app/agents/image_agent.py
AgentIntent    -> backend/app/agents/manager_agent.py
ManagerAgent   -> backend/app/agents/manager_agent.py
```

Tatsächlich verwendete Klassen:

```text
TextAgent
  - in AgentService.generate_text()
  - in ManagerChatGraph.text_agent_node()
  - in alter ManagerAgent.chat(), falls diese Methode direkt genutzt würde

ImageAgent
  - in AgentService.generate_image_prompt()
  - in ManagerChatGraph.image_agent_node()
  - in alter ManagerAgent.chat(), falls diese Methode direkt genutzt würde

ManagerAgent
  - im produktiven Manager-Graph nur indirekt für classify_intent()
  - ManagerChatGraph._classify() nutzt ManagerAgent.__new__(ManagerAgent).classify_intent(message)
  - ManagerAgent.chat() existiert, wird von AgentService.manager_chat() aber nicht aufgerufen

BaseAgent
  - Basisklasse für TextAgent, ImageAgent und ManagerAgent
```

Veraltet oder ungenutzt:

```text
ManagerAgent.chat()
ManagerAgent._decide_route()
ManagerAgent._summarize_result()
ManagerAgent._make_image_wording_safe()
```

Diese Methoden werden im aktuellen Manager-Endpoint nicht ausgeführt. Sie sind historisch oder potenziell ungenutzt, solange kein anderer Import außerhalb der geprüften Backend-Dateien sie direkt aufruft.

`smolagents`:

```text
Nicht verwendet.
Keine Imports.
Keine Dependency.
Keine Runtime-Abhängigkeit.
```

LangGraph:

```text
Aktiv verwendet.
Dependency in backend/requirements.txt.
Import in backend/app/graphs/manager_chat_graph.py:
from langgraph.graph import END, START, StateGraph
```

HuggingFace:

```text
HuggingFaceService nutzt huggingface_hub.InferenceClient.
AgentService._hf() erzeugt pro Bedarf eine neue HuggingFaceService-Instanz.
TextAgent und ImageAgent nutzen self.hf.generate().
TextAgentChat und ImageAgentChat nutzen HuggingFaceService direkt ohne Agentenklasse.
```

Manager-Auswahl:

```text
ManagerChatGraph.classify_intent_node()
  -> ManagerChatGraph._classify()
  -> ManagerAgent.classify_intent()
  -> intent_router()
  -> text_agent_node / image_agent_node / clarification_node
```

Die Klassifikation ist keyword-basiert und deterministisch. Es gibt keine LLM-basierte Intent-Klassifikation.

Fehlerbehandlung:

```text
HuggingFaceService.generate()
  - wrapped Provider-Fehler als RuntimeError("HuggingFace request failed: ...")
  - leere Antwort als RuntimeError("HuggingFace returned an empty response.")

AgentService.manager_chat()
  - fängt Exceptions und wandelt sie in HTTP 500 via _to_http_error()

ManagerChatGraph.text_agent_node() / image_agent_node()
  - fangen Agent-Exceptions
  - schreiben error in state["errors"]
  - setzen state["status"] = "error"
  - schreiben Trace-Step mit status "error"
  - schreiben Agent-Log mit status "error"
  - werfen nicht sofort weiter

validation_node()
  - prüft fehlende Artefakte
  - setzt assistant_message auf "Agent workflow failed: ..."
```

Trace-Schritte:

```text
TraceService.create_trace()
TraceService.add_step()
BaseAgent.trace()
ManagerChatGraph._add_step()
```

Alle Trace-Schritte haben:

```text
index, agent, thought, action, observation, status, timestamp
```

## 6. Aktueller LangGraph-Workflow

Graph-Datei:

```text
backend/app/graphs/manager_chat_graph.py
```

State:

```text
ManagerChatState(TypedDict, total=False)
  chat_id: str | None
  trace_id: str
  trace: dict
  chat: dict
  user_message: str
  context: str | dict | None
  intent: str
  rag_needed: bool
  rag_context: str | None
  used_agents: list[str]
  generated_artifacts: dict
  assistant_message: str
  trace_steps: list[dict]
  errors: list[str]
  status: str
  platform: str | None
```

Nodes:

```text
init_state_node
classify_intent_node
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

Edges:

```text
START -> init_state_node
init_state_node -> classify_intent_node
classify_intent_node -> rag_decision_node
rag_retrieval_node -> route_by_intent
image_agent_node -> validation_node
clarification_node -> validation_node
validation_node -> assemble_response_node
assemble_response_node -> save_trace_node
save_trace_node -> END
```

Conditional Edges:

```text
rag_decision_node -> maybe_rag_router()
  rag_retrieval_node, wenn state["rag_needed"] wahr ist
  route_by_intent, sonst

route_by_intent -> intent_router()
  text_agent_node, wenn intent == text_only
  image_agent_node, wenn intent == image_only
  text_agent_node, wenn intent == text_and_image
  clarification_node, sonst

text_agent_node -> after_text_router()
  image_agent_node, wenn intent == text_and_image
  validation_node, sonst
```

Nodes mit echter Logik:

```text
init_state_node
classify_intent_node
rag_decision_node
rag_retrieval_node
text_agent_node
image_agent_node
clarification_node
validation_node
assemble_response_node
save_trace_node
```

`route_by_intent_node` schreibt im Wesentlichen einen Trace-Schritt und bereitet die conditional edge vor. Die eigentliche Pfadentscheidung liegt in `intent_router()`.

Schleifen oder Retry-Pfade:

```text
Keine.
```

Situationsabhängigkeit:

```text
Ja, über conditional edges:
- RAG oder kein RAG
- Text
- Bild
- Text und Bild
- Klärungsfrage
```

Der Graph ist nicht überwiegend statisch, aber die Logik ist deterministisch und keyword-basiert.

### A) Text-only Anfrage

Typischer Ablauf:

```text
AgentService.manager_chat()
ManagerChatGraph.run()
init_state_node()
classify_intent_node()
rag_decision_node()
route_by_intent_node()
text_agent_node()
validation_node()
assemble_response_node()
save_trace_node()
```

Verwendete Services:

```text
ChatService
TraceService
RAGService.is_needed()
LogService
HuggingFaceService
```

Verwendeter Agent:

```text
TextAgent
```

Gespeicherte Daten:

```text
chats.json: USER- und AGENT-Nachricht
traces.json: Trace mit Steps
agent_logs.json: Manager- und TextAgent-Logs
```

Trace-Schritte:

```text
init_state_node
classify_intent_node
rag_decision_node
route_by_intent
TextAgent: build_text_prompt
TextAgent: return_text_artifact
text_agent_node
validation_node
assemble_response_node
save_trace_node
```

### B) Image-only Anfrage

Ablauf:

```text
AgentService.manager_chat()
ManagerChatGraph.run()
init_state_node()
classify_intent_node()
rag_decision_node()
route_by_intent_node()
image_agent_node()
validation_node()
assemble_response_node()
save_trace_node()
```

Verwendeter Agent:

```text
ImageAgent
```

Gespeicherte Daten:

```text
chats.json
traces.json
agent_logs.json
```

Trace-Schritte enthalten `ImageAgent`, aber keinen `TextAgent`.

### C) Text-und-Bild Anfrage

Ablauf:

```text
AgentService.manager_chat()
ManagerChatGraph.run()
init_state_node()
classify_intent_node()
rag_decision_node()
route_by_intent_node()
text_agent_node()
image_agent_node()
validation_node()
assemble_response_node()
save_trace_node()
```

Verwendete Agenten:

```text
TextAgent
ImageAgent
```

Die Reihenfolge ist fest: zuerst Text, danach Image.

Gespeicherte Artefakte:

```text
generated_artifacts.text.generated_text
generated_artifacts.text.hashtags
generated_artifacts.image.image_prompt
generated_artifacts.image.negative_prompt_optional
generated_artifacts.image.suggested_style
```

### D) Unklare Anfrage

Ablauf:

```text
AgentService.manager_chat()
ManagerChatGraph.run()
init_state_node()
classify_intent_node()
rag_decision_node()
route_by_intent_node()
clarification_node()
validation_node()
assemble_response_node()
save_trace_node()
```

Verwendete Agenten:

```text
Keine Spezialagenten.
Kein HuggingFace-Aufruf.
```

Response:

```text
assistant_message fragt nach Marketing-Text, Bildprompt oder beidem.
used_agents = []
generated_artifacts = {}
```

### E) Anfrage mit RAG-Bezug

Ablauf bei Keyword-Treffer in `RAGService.is_needed()`:

```text
AgentService.manager_chat()
ManagerChatGraph.run()
init_state_node()
classify_intent_node()
rag_decision_node()
rag_retrieval_node()
route_by_intent_node()
... danach Text/Bild/Klärung
```

`RAGService.retrieve()` ruft intern den MCP Memory Service auf:

```text
streamablehttp_client(settings.mcp_memory_url)
ClientSession.call_tool("memory_search", {"query": query, "n_results": 3})
```

Wenn Memory fehlschlägt, wird eine Warning geloggt und ein leerer String zurückgegeben. Der Graph läuft weiter.

### F) HuggingFace-Fehler

Direkte Text-/Image-Generate-Endpunkte:

```text
AgentService.generate_text()
AgentService.generate_image_prompt()
```

Bei Fehler:

```text
Trace-Step mit status "error"
HTTP 500 via AgentService._to_http_error()
```

Manager-Graph:

```text
text_agent_node() oder image_agent_node()
  fängt Exception
  state["errors"].append(...)
  state["status"] = "error"
  Trace-Step status "error"
  LogService.add_log(..., status="error")
validation_node()
  findet fehlende Artefakte
  assistant_message = "Agent workflow failed: ..."
assemble_response_node()
  behält Error-Response
save_trace_node()
  speichert Chat und Trace
```

Aktuelle Daten in `agent_logs.json` zeigen zwei Fehler durch fehlenden `HF_TOKEN`.

## 7. smolagents-Nutzung

`smolagents` ist aktuell nicht vorhanden:

```text
Keine Imports in backend/app.
Keine Erwähnung in backend/requirements.txt.
Keine Klassen oder Tools aus smolagents.
Keine Runtime-Abhängigkeit.
```

Für ein vollständiges Entfernen müssten aktuell keine Backend-Dateien angepasst werden, weil nichts darauf verweist.

Entfernbare Dependency:

```text
Keine, weil smolagents nicht in backend/requirements.txt steht.
```

## 8. HuggingFace-Anbindung

Datei:

```text
backend/app/services/huggingface_service.py
```

Verwendung:

```python
from huggingface_hub import InferenceClient
```

Initialisierung:

```text
HuggingFaceService(hf_token, hf_model_id)
InferenceClient(token=hf_token)
```

`HF_TOKEN` und `HF_MODEL_ID` werden in `backend/app/core/config.py` definiert und in `AgentService._hf()` gelesen.

Konfiguriertes Default-Modell:

```text
Qwen/Qwen2.5-7B-Instruct
```

Aufgerufene Methode:

```text
InferenceClient.chat_completion(
  model=settings.hf_model_id,
  messages=[system, user],
  max_tokens=...,
  temperature=0.7
)
```

Response-Parsing:

```text
response.choices[0].message.content
content.strip()
```

Fehlerweitergabe:

```text
fehlender HF_TOKEN -> ValueError
Provider-/Client-Fehler -> RuntimeError("HuggingFace request failed: ...")
leerer Content -> RuntimeError("HuggingFace returned an empty response.")
```

Tests:

```text
Keine Backend-Testdateien gefunden.
Kein Fake-HF-Client im geprüften Backend-Code gefunden.
Keine automatisierten Tests mit echten Modellaufrufen gefunden.
```

## 9. JSON-Speicherung

Zentrale Klasse:

```text
backend/app/storage/json_store.py
JSONStore
```

Eigenschaften:

```text
- speichert Listen von JSON-Objekten
- nutzt "id" als Primärschlüssel
- save() ersetzt vorhandene Einträge mit gleicher id
- delete() filtert nach id
- schreibt über temporäre Datei mit .tmp und replace()
- JSONDecodeError wird als leere Liste behandelt
- pro JSONStore-Instanz gibt es einen threading.Lock
```

Aktuelle JSON-Dateien:

```text
agent_logs.json -> verwendet von LogService
chats.json      -> verwendet von ChatService
posts.json      -> verwendet von PostService
traces.json     -> verwendet von TraceService
campaigns.json  -> aktuell keine Verwendung im geprüften Backend-Code
previews.json   -> aktuell keine Verwendung im geprüften Backend-Code
```

Aktuelle Inhalte:

```text
posts.json:
  ein Draft-Post mit id 68464548-d29e-4154-9474-df2320c53b46

chats.json:
  Chat 68464548-d29e-4154-9474-df2320c53b46::image_agent
  Chat 68464548-d29e-4154-9474-df2320c53b46::text_agent

agent_logs.json:
  zwei Error-Logs wegen fehlendem HF_TOKEN

campaigns.json:
  []

previews.json:
  []

traces.json:
  aktuell 0 Byte
```

Chat-History-Struktur:

```json
{
  "id": "post_id::agent",
  "agent": "manager_agent | text_agent | image_agent",
  "messages": [
    {
      "role": "USER",
      "content": "..."
    },
    {
      "role": "AGENT",
      "content": "..."
    }
  ]
}
```

Hinweis: `ChatService.add_message()` nimmt `metadata` entgegen, speichert diese aber aktuell nicht im Message-Objekt. Der Manager-Graph übergibt Metadata beim Speichern, sie geht aber verloren.

Trace-Struktur:

```json
{
  "id": "uuid",
  "trace_id": "uuid",
  "chat_id": "post_id::manager_agent",
  "created_at": "iso timestamp",
  "steps": [],
  "metadata": {}
}
```

Post-Struktur:

```json
{
  "id": "uuid",
  "title": "string",
  "status": "draft | processing | preview_ready | error",
  "topic": "string-or-null",
  "platform": "linkedin | instagram | x | blog | null",
  "target_audience": "string-or-null",
  "tone_of_voice": "string-or-null",
  "additional_context": "string-or-null",
  "preview": null
}
```

Preview-Artefakte werden im Post selbst unter `preview` gespeichert, nicht in `previews.json`.

Docker-Rebuild-Risiko:

```text
backend/app/storage/data liegt im Image/Container-Dateisystem.
docker-compose.yml mountet kein Volume für diese JSON-Dateien.
Bei Container-Neuerstellung oder Image-Rebuild können Laufzeitdaten verloren gehen, sofern sie nur im Container geschrieben wurden.
```

## 10. Tests und Dokumentation

Automatisierte Backend-Tests:

```text
Keine gefunden.
```

Es wurden keine Dateien unter üblichen Mustern wie `backend/tests`, `test_*.py` oder ähnlichen Backend-Testpfaden gefunden.

Manuelle Test-/Dokumentationsdateien:

```text
docs/backend_route_tests.md
docs/backend_agent_architecture.md
docs/backend_agent_postman_walkthrough.md
docs/frontend_backend_alignment_review.md
```

`docs/backend_agent_architecture.md` passt grob zur aktuellen LangGraph-Implementierung, ist aber an mindestens einer Stelle veraltet: Es beschreibt `rag_retrieval_node` als reinen Placeholder mit festem Placeholder-Text. Tatsächlich ruft `rag_retrieval_node()` aktuell `RAGService.retrieve()` und damit den MCP Memory Service auf.

`docs/backend_agent_postman_walkthrough.md` ist teilweise veraltet:

```text
- ManagerChatRequest-Beispiele lassen post_id weg, obwohl post_id im Schema Pflicht ist.
- Chat-History-Pfad wird als /api/agents/chats/{chat_id} beschrieben; echt ist /api/agents/manager/chats/{chat_id}, /api/agents/text/chats/{chat_id} oder /api/agents/image/chats/{chat_id}.
- Trace-Pfad wird als /api/agents/traces/{trace_id} beschrieben; echt ist /api/agents/manager/traces/{trace_id}.
- Erwartete Chat-History-Response nennt chat_id, created_at, updated_at, metadata; echtes Schema ist id, agent, messages mit role/content.
- RAG-Placeholder-Beschreibung passt nicht mehr exakt, weil RAGService MCP Memory aufruft und bei Fehler leer zurückgibt.
```

`docs/backend_route_tests.md` ist deutlich veraltet:

```text
- erwähnt /api/posts/{post_id}/agent-trace, diese Route existiert nicht.
- enthält Felder wie goal in PostCreate/Update-Beispielen, die nicht im aktuellen Schema stehen.
- beschrieb zwischenzeitlich decision/action/observation; die aktuelle TraceStep-Struktur ist wieder thought/action/observation.
```

Tests mit Fake-Clients:

```text
Keine gefunden.
```

Tests mit echten Modellaufrufen:

```text
Keine automatisierten Tests gefunden.
Manuelle Postman-Beispiele würden echte HuggingFace-Aufrufe auslösen, wenn HF_TOKEN gesetzt ist.
```

## 11. Veraltete oder ungenutzte Dateien

Wahrscheinlich ungenutzt im aktuellen Backend-Code:

```text
backend/app/storage/data/campaigns.json
backend/app/storage/data/previews.json
```

Historisch oder aktuell ungenutzte Methoden:

```text
ManagerAgent.chat()
ManagerAgent._decide_route()
ManagerAgent._summarize_result()
ManagerAgent._make_image_wording_safe()
ChatService.get_chats_by_agent()
```

Nicht mehr aktuelle Dokumentation oder Beispiele:

```text
docs/backend_route_tests.md
Teile von docs/backend_agent_postman_walkthrough.md
Teile von docs/backend_agent_architecture.md zur RAG-Placeholder-Beschreibung
```

## 12. Risiken beim Umbau

Schnittstellen, die stabil bleiben sollten:

```text
POST /api/agents/manager/chat
ManagerChatRequest: message, post_id, context
ManagerChatResponse: chat_id, assistant_message, used_agents, generated_artifacts, trace_id

POST /api/agents/text/generate
TextGenerateResponse: generated_text, hashtags, trace_id

POST /api/agents/image/generate-prompt
ImagePromptResponse: image_prompt, negative_prompt_optional, suggested_style, trace_id

GET /api/agents/manager/traces/{trace_id}
TraceResponse: trace_id, chat_id, created_at, steps, metadata

GET /api/agents/*/chats/{chat_id}
ChatHistoryResponse: id, agent, messages
```

Leicht kaputtbare Stellen:

```text
Manager intent labels:
  text_only, image_only, text_and_image, clarification_needed

Graph-Routing:
  intent_router(), after_text_router(), maybe_rag_router()

Trace-Speicherung:
  TraceService.add_step() wird von Graph-Nodes und BaseAgent verwendet.

Chat-ID-Konvention:
  post_id::agent

Post-Preview:
  PostService.generate_preview() erwartet generated_artifacts.text und generated_artifacts.image in aktueller Struktur.

HuggingFace-Fehler:
  direkte Endpunkte werfen HTTP 500, Graph-Endpunkte können Fehler als gespeicherte Error-Response zurückgeben.

RAGService:
  nutzt asyncio.run(); das kann in bereits laufenden Event-Loops problematisch werden, falls später async Routes eingeführt werden.

ChatService.add_message():
  metadata-Parameter wird aktuell nicht persistiert. Ein Umbau könnte versehentlich frontend-relevante Erwartungen erzeugen, die derzeit nicht erfüllt werden.
```

Docker-/Storage-Risiko:

```text
Keine Volume-Mounts für backend/app/storage/data.
JSON-Daten können bei Container-Neuerstellung verloren gehen.
```

## 13. Empfohlener Minimal-Umbau

Noch keinen Code schreiben. Der empfohlene Umbau sollte klein bleiben und sich auf Agenten-/Graph-Logik konzentrieren:

```text
FastAPI
-> AgentService
-> LangGraph Manager Workflow
   -> Intent-Klassifikation
   -> RAG-Entscheidung
   -> TextAgent
   -> ImageAgent
   -> Validierung
   -> Response
   -> Trace
-> bestehende JSON-Speicherung
```

Konkrete Empfehlung:

1. `ManagerChatGraph` als einzige Manager-Orchestrierung behalten.
2. Intent-Klassifikation aus `ManagerAgent` herauslösen oder `ManagerAgent` auf eine reine Klassifikationsklasse reduzieren.
3. Alte `ManagerAgent.chat()`-Orchestrierung entfernen, sobald bestätigt ist, dass kein anderer Branch sie braucht.
4. `TextAgent` und `ImageAgent` als einfache Spezialisten beibehalten.
5. `HuggingFaceService` beibehalten und nicht durch LangGraph-spezifische LLM-Wrapper ersetzen.
6. `RAGService` beibehalten, aber klar als Memory/Retrieval-Adapter markieren.
7. Keine Routen ändern.
8. Keine Request-/Response-Schemas ändern.
9. Keine JSON-Storage-Migration.
10. Keine echte Bildgenerierung, kein echtes Publishing, keine Datenbankmigration.

Minimaler Zielzustand:

```text
backend/app/graphs/manager_chat_graph.py
  zentrale Manager-Orchestrierung

backend/app/agents/text_agent.py
  Textgenerierung

backend/app/agents/image_agent.py
  Bildprompt-Generierung

backend/app/agents/manager_agent.py
  entweder entfernt oder reduziert auf IntentClassifier/AgentIntent
```

## 14. Dateien, die geändert werden müssten

Für den späteren Minimal-Umbau wahrscheinlich:

```text
backend/app/graphs/manager_chat_graph.py
backend/app/agents/manager_agent.py
backend/app/services/agent_service.py
docs/backend_agent_architecture.md
docs/backend_agent_postman_walkthrough.md
```

Optional, nur wenn der Umbau bereinigt werden soll:

```text
backend/app/agents/base_agent.py
```

Nur falls Tests ergänzt werden:

```text
backend/tests/... oder vergleichbarer neuer Testordner
```

Nicht erforderlich für smolagents:

```text
backend/requirements.txt
```

`smolagents` steht dort nicht drin.

## 15. Dateien, die unverändert bleiben sollten

Für den geplanten Agent-/Graph-Umbau sollten stabil bleiben:

```text
backend/app/main.py
backend/app/api/routes_manager_agent.py
backend/app/api/routes_text_agent.py
backend/app/api/routes_image_agent.py
backend/app/api/routes_posts.py
backend/app/api/routes_memory.py
backend/app/schemas/agent.py
backend/app/schemas/chat.py
backend/app/schemas/logs.py
backend/app/schemas/post.py
backend/app/schemas/trace.py
backend/app/services/chat_service.py
backend/app/services/trace_service.py
backend/app/services/log_service.py
backend/app/services/post_service.py
backend/app/services/huggingface_service.py
backend/app/services/rag_service.py
backend/app/storage/json_store.py
backend/Dockerfile
docker-compose.yml
backend/requirements.txt
```

Ausnahme: Dokumentation darf später aktualisiert werden. Docker sollte nur angepasst werden, wenn entschieden wird, JSON-Daten per Volume persistent zu machen. Das wäre kein Agenten-Umbau, sondern Betriebs-/Persistenzarbeit.

Frontend-Dateien wurden für diesen Audit nicht analysiert und sollten für diesen Umbau unverändert bleiben.

## 16. Offene Fragen

1. Soll `ManagerAgent.chat()` später vollständig entfernt werden, oder braucht der parallele Frontend-/Backend-Kommunikationsbranch diese Methode noch?
2. Soll die Intent-Klassifikation weiter keyword-basiert bleiben, oder später als eigener kleiner LangGraph-Node mit LLM-Klassifikation umgesetzt werden?
3. Soll `RAGService` als echte MCP-Memory-Anbindung gelten, oder fachlich weiterhin als Placeholder dokumentiert werden?
4. Soll `ChatService.add_message()` künftig `metadata` speichern? Der Manager-Graph übergibt bereits Metadata, aber der Service verwirft sie aktuell.
5. Soll `traces.json` mit 0 Byte bewusst toleriert werden, oder soll eine leere Datei standardmäßig `[]` enthalten?
6. Soll für `backend/app/storage/data` ein Docker-Volume ergänzt werden, damit JSON-Daten bei Container-Neuerstellung erhalten bleiben?
7. Soll es automatisierte Backend-Tests geben, bevor Agenten-/Graph-Logik bereinigt wird?
8. Sollen die veralteten Postman-/Route-Dokumente vor oder nach dem Graph-Umbau korrigiert werden?
