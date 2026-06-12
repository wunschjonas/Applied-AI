# MCP Agent Memory Layer — Implementierungsplan & Status

> Workspace-Root für Cursor: `C:\Users\wunsc\Desktop\Applied-AI`
> (Ordner öffnen, damit backend/, frontend/, memory_layer/ alle sichtbar sind)

---

## Fortschritt

| # | Schritt | Datei(en) | Status |
|---|---------|-----------|--------|
| 1 | memory-Service + Volume in docker-compose | `docker-compose.yml` | ✅ Fertig |
| 2 | Python-Abhängigkeiten hinzufügen | `backend/requirements.txt` | ⬜ Offen |
| 3 | MCP_MEMORY_URL als Config-Setting | `backend/app/core/config.py` | ⬜ Offen |
| 4 | RAGService mit echten MCP-Aufrufen | `backend/app/services/rag_service.py` | ⬜ Offen |
| 5 | rag_context an Agenten weitergeben | `backend/app/graphs/manager_chat_graph.py` | ⬜ Offen |
| 6 | rag_context-Parameter in TextAgent & ImageAgent | `backend/app/agents/text_agent.py` + `image_agent.py` | ⬜ Offen |
| 7 | Neue Memory-API-Endpunkte | `backend/app/api/routes_memory.py` (neu) | ⬜ Offen |
| 8 | Frontend RAG-Seite ausbauen | `frontend/src/app/pages/rag/` | ⬜ Offen |

---

## Schritt 1 — Was wurde gemacht (Referenz)

`docker-compose.yml` wurde erweitert um:

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

Außerdem im `backend`-Service hinzugefügt:
```yaml
depends_on:
  - memory
environment:
  - MCP_MEMORY_URL=http://memory:8765/mcp
```

Und am Ende der Datei:
```yaml
volumes:
  memory_data:
```

---

## Schritt 2 — Nächster Schritt

**Dateien:** `backend/requirements.txt` und `backend/app/core/config.py`

### `backend/requirements.txt`
Zwei Pakete hinzufügen:
```
mcp
httpx
```

### `backend/app/core/config.py`
Eine neue Einstellung ergänzen:
```python
MCP_MEMORY_URL: str = "http://localhost:8765/mcp"
```
(Lokal zeigt die URL auf localhost; via Docker Compose überschreibt die Umgebungsvariable
`MCP_MEMORY_URL=http://memory:8765/mcp` den Wert automatisch.)

---

## Schritt 3 — RAGService (Vorschau)

**Datei:** `backend/app/services/rag_service.py`

Den bisherigen Stub durch echte MCP-Aufrufe ersetzen.
Das Python-Paket `mcp` stellt `streamablehttp_client` und `ClientSession` bereit.

```python
import asyncio
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

class RAGService:
    def __init__(self, memory_url: str):
        self.memory_url = memory_url

    def retrieve(self, query: str) -> str:
        return asyncio.run(self._search(query))

    def store(self, content: str, tags: list[str] | None = None) -> None:
        asyncio.run(self._store(content, tags or []))

    async def _search(self, query: str) -> str:
        async with streamablehttp_client(self.memory_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "memory_search", {"query": query, "n_results": 3}
                )
                # Ergebnisse zu Text zusammenfassen
                ...

    async def _store(self, content: str, tags: list[str]) -> None:
        async with streamablehttp_client(self.memory_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                await session.call_tool(
                    "memory_store", {"content": content, "tags": tags}
                )
```

---

## Architektur-Kurzübersicht

```
docker compose up
  ├── memory   :8765  ← MCP Memory Service (fertiger Container, kein eigener Code)
  ├── backend  :8080  ← FastAPI + LangGraph (kommuniziert mit memory via HTTP/MCP)
  └── frontend :4200  ← Angular UI

Datenfluss im Agent-Request:
  User-Nachricht
    → ManagerChatGraph (LangGraph)
    → rag_decision_node
    → rag_retrieval_node  →  RAGService.retrieve()  →  MCP memory_search  →  Memory Container
    → TextAgent / ImageAgent  (mit rag_context im Prompt)
    → Antwort an User
```

---

## Hinweise für den nächsten Chat

- Workspace in Cursor als **`C:\Users\wunsc\Desktop\Applied-AI`** öffnen
  (nicht den memory_layer-Unterordner), damit alle Projektordner sichtbar sind
- Diese Datei liegt in `memory_layer/IMPLEMENTIERUNG_STATUS.md`
- Das Konzept liegt in `memory_layer/KONZEPT.md`
- Nächster Schritt: Schritt 2 — `requirements.txt` + `config.py`
