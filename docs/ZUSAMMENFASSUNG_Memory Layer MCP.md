# Memory Layer — Was wurde implementiert?

Dieses Dokument fasst alle Änderungen zusammen, die im Rahmen der Memory-Layer-Implementierung vorgenommen wurden.
Das Ziel: Unsere KI-Agenten können sich Fakten und Kontext "merken" und diesen bei der Inhaltserstellung berücksichtigen.

---

## Idee in einem Satz

Ein Nutzer speichert einmal: *"Unsere Zielgruppe sind Fachkräfte zwischen 25 und 35."*
Ab sofort berücksichtigt der Agent diesen Fakt automatisch bei jedem passenden Request — ohne dass der Nutzer ihn nochmal erwähnen muss.

---

## Architektur-Überblick

```
docker compose up
  ├── frontend  :4200   Angular UI
  ├── backend   :8080   FastAPI + LangGraph
  └── memory    :8765   MCP Memory Service (fertiger Docker-Container)

Datenfluss bei einem Agent-Request:
  Nutzernachricht
    → ManagerChatGraph (LangGraph)
    → rag_decision_node   — enthält die Nachricht ein RAG-Keyword?
    → rag_retrieval_node  — RAGService.retrieve() → MCP memory_search → Memory-Container
    → TextAgent / ImageAgent  — erhalten rag_context im LLM-Prompt
    → Antwort an Nutzer
```

Der Memory-Service ist ein **fertiges Open-Source-Docker-Image** (`doobidoo/mcp-memory-service`).
Er speichert Texte als semantische Vektoren (Embeddings) in einer SQLite-Datenbank und unterstützt Ähnlichkeitssuche.
Das Backend kommuniziert mit ihm über das **MCP-Protokoll** (Model Context Protocol) via HTTP.

---

## Was wurde geändert — Datei für Datei

### 1. `docker-compose.yml`

Neuer `memory`-Container als dritter Service:

```yaml
memory:
  image: doobidoo/mcp-memory-service:latest
  ports:
    - '8765:8765'
  volumes:
    - memory_data:/app/sqlite_db
  environment:
    - MCP_MODE=streamable-http
    - MCP_SSE_HOST=0.0.0.0
    - MCP_SSE_PORT=8765
    - MCP_ALLOW_ANONYMOUS_ACCESS=true
    - MCP_MEMORY_STORAGE_BACKEND=sqlite_vec
    - MCP_MEMORY_SQLITE_PATH=/app/sqlite_db/memory.db
  restart: unless-stopped
```

Der `backend`-Service erhielt außerdem:
- `depends_on: memory` — startet erst wenn memory läuft
- `MCP_MEMORY_URL=http://memory:8765/mcp` als Umgebungsvariable

Am Ende der Datei wurde das Volume deklariert:
```yaml
volumes:
  memory_data:
```

---

### 2. `backend/requirements.txt`

Zwei neue Python-Pakete:
```
mcp      # offizieller MCP-Client (Kommunikation mit dem Memory-Service)
httpx    # HTTP-Client, den mcp intern benötigt
```

---

### 3. `backend/app/core/config.py`

Neues Konfigurations-Setting:
```python
mcp_memory_url: str = Field(
    default="http://localhost:8765/mcp",
    alias="MCP_MEMORY_URL"
)
```
Lokal zeigt die URL auf `localhost`; in Docker Compose wird sie durch die Umgebungsvariable auf `http://memory:8765/mcp` überschrieben.

---

### 4. `backend/app/services/rag_service.py`

**Komplett neu geschrieben.** Vorher: Stub, der nur einen Platzhalter-String zurückgab.
Jetzt: Echter MCP-Client mit drei öffentlichen Methoden:

| Methode | Was sie tut |
|---|---|
| `is_needed(message)` | Prüft per Keyword-Matching ob RAG benötigt wird |
| `retrieve(query)` | Sucht semantisch ähnliche Einträge im Memory-Container (gibt bis zu 3 Treffer zurück) |
| `store(content, tags)` | Speichert einen Fakt mit optionalen Tags |
| `list_all()` | Gibt alle gespeicherten Einträge zurück |

Alle MCP-Aufrufe laufen async (`_search`, `_store`, `_list`) und werden synchron über `asyncio.run()` aufgerufen, damit der synchrone LangGraph-Code sie nutzen kann.
Bei Verbindungsfehlern zum Memory-Service: **kein Absturz** — nur ein Log-Warning, leerer String als Fallback.

---

### 5. `backend/app/services/agent_service.py`

Einzeilige Änderung: `RAGService` wird jetzt mit der URL aus den Settings instanziiert:
```python
# vorher:
self.rag_service = RAGService()

# nachher:
self.rag_service = RAGService(memory_url=settings.mcp_memory_url)
```

---

### 6. `backend/app/agents/text_agent.py`

Neuer Parameter `rag_context: str | None = None` in `generate()` und `_build_prompt()`.
Der Kontext wird nur dann in den LLM-Prompt eingebaut, wenn er nicht leer ist:
```
- Memory context: Unsere Zielgruppe sind Fachkräfte zwischen 25 und 35.
```

---

### 7. `backend/app/agents/image_agent.py`

Identische Änderung wie beim TextAgent: `rag_context`-Parameter in `generate_prompt()` und `_build_prompt()`.

---

### 8. `backend/app/graphs/manager_chat_graph.py`

In `text_agent_node` und `image_agent_node` je eine neue Zeile — der Graph-State enthält `rag_context` bereits, er wurde nur nicht weitergereicht:
```python
rag_context=state.get("rag_context"),
```

---

### 9. `backend/app/api/routes_memory.py` *(neue Datei)*

Drei neue REST-Endpunkte unter dem Prefix `/api/memory/`:

| Methode | Endpoint | Funktion |
|---|---|---|
| `POST` | `/api/memory/store` | Fakt + Tags speichern |
| `GET` | `/api/memory/search?q=...` | Semantisch suchen |
| `GET` | `/api/memory/list` | Alle Einträge auflisten |

---

### 10. `backend/app/main.py`

Router registriert:
```python
from app.api.routes_memory import router as memory_router
app.include_router(memory_router)
```

---

### 11. `frontend/src/app/services/memory.service.ts` *(neue Datei)*

Angular-Service mit drei Methoden, die die neuen Backend-Endpunkte ansprechen:
```typescript
store(content, tags)  →  POST /api/memory/store
search(q)             →  GET  /api/memory/search?q=...
list()                →  GET  /api/memory/list
```

---

### 12. `frontend/src/app/pages/rag/` *(vorher leere Placeholder-Seite)*

Die RAG-Seite (erreichbar unter `/rag`) hat jetzt drei Funktionsbereiche in einem Split-Layout:

**Links:**
- **Fakt speichern** — Textarea für den Inhalt, optionales Komma-getrenntes Tags-Feld, Speichern-Button mit Erfolgsmeldung
- **Semantisch suchen** — Suchfeld, Suchen-Button, farblich hervorgehobene Ergebnisliste

**Rechts:**
- **Alle Einträge** — wird beim Seitenaufruf automatisch geladen, Refresh-Button, Liste aller gespeicherten Fakten

---

## Lokaler Start (ohne Docker)

```powershell
# Memory-Container separat starten (einmalig)
docker run -d --name memory -p 8765:8765 `
  -v memory_data:/app/sqlite_db `
  -e MCP_MODE=streamable-http `
  -e MCP_SSE_HOST=0.0.0.0 -e MCP_SSE_PORT=8765 `
  -e MCP_ALLOW_ANONYMOUS_ACCESS=true `
  -e MCP_MEMORY_STORAGE_BACKEND=sqlite_vec `
  -e MCP_MEMORY_SQLITE_PATH=/app/sqlite_db/memory.db `
  doobidoo/mcp-memory-service:latest

# Dann Backend normal starten
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

## Mit Docker Compose (alles zusammen)

```powershell
docker compose up
```

Alle drei Services (frontend :4200, backend :8080, memory :8765) starten automatisch.
Die gespeicherten Memory-Einträge bleiben durch das Docker-Volume `memory_data` auch nach einem Neustart erhalten.

---

## API testen (FastAPI Swagger)

Nach dem Start ist die komplette API-Dokumentation verfügbar unter:
`http://localhost:8080/docs`

Dort sind die neuen `/api/memory/`-Endpunkte direkt testbar.
