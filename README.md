# Applied-AI — Marketing Multi-Agent

Das ist das Abgabeprojekt für Applied-AI von Jonas Wunsch und Fabian Sichert. Eine Web-App, mit der man Marketing-Posts per Chat erstellen kann: Ein Manager-Agent sammelt die Angaben (Steckbrief), holt bei Bedarf Wissen aus Gedächtnis oder Web und lässt Text- und Bild-Agenten den Post erzeugen. Ergebnis und Vorschau sind im Frontend sichtbar.

Damit das Projekt funktioniert, muss im Backend in die `.env`-Datei ein HuggingFace-Token eingefügt werden. Dazu haben Sie eine E-Mail mit Token erhalten, den Sie einfügen können.

## Tech-Stack

| Teil | Technik |
|------|---------|
| Frontend | Angular |
| Backend | FastAPI, LangGraph, HuggingFace Inference |
| Memory | MCP Memory Service (sqlite_vec) |
| Betrieb | Docker Compose |

## Projektstruktur

| Pfad | Inhalt |
|------|--------|
| [`frontend/`](frontend/) | Angular-UI |
| [`backend/`](backend/) | FastAPI-API, LangGraph-Manager, Agents, Tests |
| [`dokumentation/`](dokumentation/) | Abgabe-Unterlagen, Workflow-Graph |
| [`docker-compose.yml`](docker-compose.yml) | Frontend, Backend, Memory |

## Dokumentation

- Projektdokumentation: [`dokumentation/Projektdokumentation - AAI - Jonas Wunsch, Fabian Sichert.pdf`](dokumentation/Projektdokumentation%20-%20AAI%20-%20Jonas%20Wunsch%2C%20Fabian%20Sichert.pdf)
- LangGraph-Workflow (Manager-Graph): [`dokumentation/langgraph-manager-workflow.PNG`](dokumentation/langgraph-manager-workflow.PNG)

## Voraussetzungen

- Docker + Docker Compose **oder** Python 3.12+ und Node/npm
- HuggingFace-Token aus der E-Mail (siehe oben)

## Setup

Ohne gültigen `HF_TOKEN` in `backend/.env` startet Docker Compose nicht (`env_file`).

Im Ordner [`backend/`](backend/) liegt [`backend/.env.example`](backend/.env.example). Diese Datei kopieren und als `.env` ablegen (also umbenennen bzw. als `backend/.env` speichern). Dort den HuggingFace-Token aus der E-Mail bei `HF_TOKEN=` eintragen.

Compose setzt `MCP_MEMORY_URL=http://memory:8765/mcp` automatisch. Lokal (ohne Backend-Container) gilt der Default `http://localhost:8765/mcp`.

### Mit Docker (alles)

```bash
# aus dem Projektroot — .env muss schon existieren
docker compose up --build
```

### Lokal ohne Docker (Backend + Frontend)

Das Gedächtnis (Memory) läuft immer als Docker-Container. Lokal startet ihr nur diesen Container, Backend und Frontend daneben normal:

```bash
# Terminal 1 — MCP Memory (Port 8765)
docker compose up memory

# Terminal 2 — Backend
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py

# Terminal 3 — Frontend (ng serve)
cd frontend
npm install
npm start
```

## Tests & CI

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest "tests/W8 Tests" -q
```

GitHub Actions: [`.github/workflows/backend-ci.yml`](.github/workflows/backend-ci.yml) — W8-Suite + Docker-Build (Fake-`HF_TOKEN`, kein Secret nötig).

## Monitoring

| Service | URL |
|---------|-----|
| Frontend | http://localhost:4200 |
| Backend API / Docs | http://localhost:8080/docs |
| Health | http://localhost:8080/health |
| Metrics (Prometheus) | http://localhost:8080/metrics |
| MCP Memory | http://localhost:8765 |

## Endpoints

Die API-Endpunkte wurden mit Postman abgefragt und getestet.

| Methode | Pfad | Zweck |
|---------|------|--------|
| GET | `/health` | Betriebsstatus |
| GET | `/metrics` | Prometheus |
| POST | `/api/posts/init` | Post + Welcome anlegen |
| GET/POST | `/api/posts` | Posts listen / anlegen |
| GET/PUT/DELETE | `/api/posts/{post_id}` | Post lesen / ändern / löschen |
| POST | `/api/posts/{post_id}/generate-preview` | Preview anstoßen |
| GET | `/api/posts/{post_id}/preview` | Preview laden |
| POST | `/api/agents/manager/chat` | Manager-Chat (Steckbrief, Ack, Tools) |
| POST | `/api/agents/manager/generate` | Text/Bild erzeugen (`force_generation`) |
| GET | `/api/agents/manager/chats/{chat_id}` | Manager-Chatverlauf |
| GET | `/api/agents/manager/logs` | Manager-Logs |
| POST | `/api/agents/text/chat` | Text nachschärfen |
| POST | `/api/agents/image/chat` | Bild verfeinern / neu erzeugen |
| POST | `/api/memory/store` | Fakt speichern |
| GET | `/api/memory/search` | Gedächtnis suchen |
| GET | `/api/memory/list` | Gedächtnis auflisten |
| POST | `/api/memory/upload` | PDF/Datei hochladen |
| DELETE | `/api/memory/{content_hash}` | Eintrag löschen |
| DELETE | `/api/logs` | Agent-Logs löschen |

Input-Validierung: leere/Whitespace-Messages → 422; unbekannte `post_id` → 404; Chat-UI zeigt Backend-`detail`.

## Tests

Unter [`backend/tests/W8 Tests/`](backend/tests/W8%20Tests/) liegen **15** Kern-Tests (pytest). Sie decken die Demo-kritischen Pfade ab: Steckbrief-Guardrails, Ack → Generate, Tools/Memory, Validation-Retry, Image-Refine, API-Validierung, Health und TAO-Trace-Form.

| Test | Prüft |
|------|--------|
| `test_missing_fields_for_intent_requires_text_and_image_extras` | Fehlende Steckbrief-Felder je Intent |
| `test_generate_with_only_topic_is_blocked` | Generate nur mit Thema → blockiert |
| `test_bildmotiv_briefing_does_not_generate_image` | Bildmotiv allein erzeugt kein Bild |
| `test_manager_chat_rejects_empty_message` | Leere Message → 422 |
| `test_manager_chat_unknown_post_returns_404` | Unbekannte `post_id` → 404 |
| `test_graph_combined_uses_both_agents` | Ack dann Generate → Text- + Image-Agent |
| `test_brief_complete_auto_ack_then_generate` | Letztes Feld → Ack → Generate |
| `test_dispatch_brief_tools` | Completeness- / Post-Data-Tools |
| `test_dispatch_memory_store` | Memory speichern (Dispatcher) |
| `test_incomplete_brief_uses_completeness_tool` | Unvollständiger Brief → Completeness-Tool |
| `test_memory_store_on_explicit_user_request` | Explizites Speichern im Graph |
| `test_trace_steps_include_thought_action_observation` | TAO-Schritte im Trace |
| `test_short_text_triggers_one_retry_and_recovers` | Kurzer Text → ein Retry, dann ok |
| `test_image_agent_refines_post_image_via_img2img` | Image-Agent img2img-Verfeinerung |
| `test_health_endpoint_includes_components` | `/health` mit Components |
