---
name: Projekt-Audit Verbesserungen
overview: Vollständiges Audit von Backend, Frontend und Infrastruktur. Gefunden wurden zwei funktionale Bugs im Manager-Graph, ein Datenverlust-Risiko im JSON-Storage, mehrere Clean-Install-Blocker sowie Git-Hygiene-Probleme und diverse Inkonsistenzen.
todos:
  - id: router-intent
    content: "routers.py: Tool-Treffer nur bei memory_inquiry/web_inquiry/memory_store routen; bei Generierungs-Intents rag_context/web_context als Kontext behalten und zum Spezialisten weiterleiten"
    status: completed
  - id: auto-generate
    content: "planning.py: clarification_needed und memory_store in _SKIP_AUTO_GENERATE_INTENTS aufnehmen"
    status: cancelled
  - id: json-store-lock
    content: "json_store.py: Store-Registry pro Datei mit gemeinsamem Lock, damit parallele Requests sich nicht überschreiben"
    status: completed
  - id: json-store-corrupt
    content: "json_store.py: bei JSONDecodeError Datei sichern statt leeren"
    status: completed
  - id: hf-timeout
    content: "huggingface_service.py: Timeouts für chat_completion, text_to_image und image_to_image setzen"
    status: completed
  - id: clean-install
    content: "Clean Install reparieren: Angular CLI auf 19.x, requirements.txt pinnen + requirements-dev.txt, .env-Pflicht im README"
    status: pending
  - id: frontend-config
    content: "Frontend-Konfiguration entkoppeln: memory.service.ts auf api.config.ts umstellen, Angular environments einführen und BACKEND_URL nutzen (oder aus compose entfernen)"
    status: completed
  - id: git-hygiene
    content: .gitignore erweitern, getrackte .pyc/Storage/Bilder per git rm --cached entfernen, .dockerignore anlegen
    status: pending
  - id: backend-consistency
    content: "Backend aufräumen: CORS korrigieren, generate_preview HTTPException durchreichen, MIN_TEXT_LENGTH an text_length koppeln, Cascade-Delete, toten Code entfernen"
    status: pending
  - id: frontend-consistency
    content: "Frontend aufräumen: toten Code inkl. getAgentTrace entfernen, doppelte HTTP-Calls reduzieren, Fehler-UI vereinheitlichen, Chat-Input während Arbeit sperren, SCSS-Duplikat auflösen"
    status: pending
  - id: ui-polish
    content: "UI-Konsistenz: Sprachmix bereinigen, lang=de, aria-labels und trackBy ergänzen"
    status: pending
  - id: tests-docs
    content: Tests für Posts-API, Memory-Upload und json_store ergänzen, W2-Multimodal-Test wiederherstellen, Frontend-CI, Doku-Korrekturen (monitoring.md Port, backend_cmds.txt, frontend/README, Troubleshooting)
    status: pending
isProject: false
---

## Zusammenfassung

Vier parallele Audits plus eigene Gegenprüfung im Code. Die schwerwiegendsten Punkte sind nicht kosmetisch: der Manager-Graph kann bei Generierungs-Anfragen still in eine Wissensantwort abbiegen, und der JSON-Storage kann bei parallelen Requests Daten verlieren. Die Backend-Testsuite (60 Tests) läuft komplett grün, der Frontend-Build ebenfalls.

Die Punkte sind nach Wirkung sortiert. Auth/Rate-Limits usw. sind bewusst als "nicht im Abgabe-Scope" markiert.

---

## P0 — Funktionale Fehler

### 1. Tool-Treffer überschreiben Generierungs-Intents

`backend/app/graphs/routers.py:26-38` priorisiert Tool-Ergebnisse über den Intent:

```python
elif "web_search" in tools and state.get("web_context"):
    target = "web_answer_node"
elif ("memory_search" in tools or "memory_list" in tools) and state.get("rag_context"):
    target = "memory_answer_node"
```

Das Backend erzeugt diesen Zustand selbst: `backend/app/graphs/nodes/rag.py:328-352` (`_keyword_fallback`) ruft `memory_search` genau für `text_only`/`image_only`/`text_and_image` auf, und der ReAct-Prompt (`rag.py:44`) weist bei Generierungs-Intents zusätzlich `web_search` an. Liefert Memory oder Web einen Treffer, bekommt der Nutzer eine Wissensantwort statt seines Posts.

Fix: Tool-Routing nur bei `memory_inquiry` / `web_inquiry` / `memory_store` greifen lassen. Bei Generierungs-Intents `rag_context` / `web_context` als Briefing-Material behalten und regulär zum Spezialisten routen.

### 2. Auto-Generierung überschreibt Rückfragen — verworfen (Fehlalarm)

Bei der Umsetzung geprüft und wieder verworfen: `brief_just_completed` wird in `backend/app/graphs/nodes/post_sync.py:50` nur beim Übergang von unvollständig auf vollständig gesetzt, d.h. der Override ist genau die gewollte Auto-Generierung. Eine reine Feldangabe ("Bildstil fotorealistisch") wird als `clarification_needed` klassifiziert — die Änderung hätte das Feature abgeschaltet. Die relevanten Sonderfälle (`memory_inquiry`, `memory_store`, `web_inquiry`, `post_status_inquiry`) sind bereits ausgenommen. Ursprüngliche Analyse zur Nachvollziehbarkeit:

`backend/app/graphs/nodes/planning.py:47-53` setzt bei `brief_just_completed` hart auf `text_and_image`. `clarification_needed` fehlt in `_SKIP_AUTO_GENERATE_INTENTS` (Zeile 24-31), d.h. eine mehrdeutige Nachricht beim Füllen des letzten Steckbrief-Feldes löst ungewollt eine Vollgenerierung aus.

Fix: `clarification_needed` und `memory_store` ins Skip-Set aufnehmen.

### 3. JSON-Store: Locks greifen nicht

`backend/app/storage/json_store.py:13` legt ein `RLock` **pro Instanz** an. Für `chats.json` existieren mindestens fünf unabhängige Instanzen (je ein `ChatService` in `routes_text_agent.py`, `routes_image_agent.py`, `routes_manager_agent.py`, plus je einer in jedem `AgentService` und `PostService`). Da die Routen synchrone `def`-Endpunkte sind, führt FastAPI sie im Threadpool parallel aus — zwei gleichzeitige Chats können sich überschreiben.

Fix: Store-Instanzen pro Datei als Modul-Singleton mit gemeinsamem Lock (einfachste Variante: Registry `_STORES: dict[Path, JSONStore]` in `json_store.py`).

### 4. Beschädigte JSON-Datei wird gelöscht

```python
except json.JSONDecodeError:
    self._write([])
    return []
```

`json_store.py:27-29` macht aus einem Lesefehler sofort totalen Datenverlust.

Fix: Datei nach `.corrupt-<timestamp>` sichern, Fehler loggen, dann erst neu initialisieren.

### 5. HuggingFace-Calls ohne Timeout

`backend/app/services/huggingface_service.py` setzt weder auf `chat_completion` noch auf `text_to_image`/`image_to_image` ein Timeout. Ein hängender HF-Call blockiert den kompletten Graph-Durchlauf und damit einen Worker-Thread.

Fix: `InferenceClient(..., timeout=...)` setzen.

---

## P1 — Clean Install reparieren

Das ist der offene Punkt aus `TODO.txt:26`. Drei bestätigte Ursachen:

- **Angular-Versionskonflikt:** `frontend/package.json:27` hat `@angular/cli` `^21.2.14` bei Angular-19-Paketen und `@angular-devkit/build-angular` `^19.1.6`. Frischer `npm install` läuft in ERESOLVE. CLI auf `^19.1.x` zurückziehen.
- **Keine Versions-Pins:** `backend/requirements.txt` pinnt nichts. `langgraph`, `mcp`, `huggingface-hub` sind API-instabil. Pinnen und `pytest` in eine `requirements-dev.txt` auslagern. (`python-dotenv` in Zeile 5 wird nirgends importiert — Config läuft über `pydantic-settings`.)
- **`backend/.env` fehlt:** `docker-compose.yml:25-26` nutzt `env_file`, ohne die Datei bricht `docker compose up` ab. Im README als harte Voraussetzung markieren, inkl. Windows-Variante (`copy` statt `cp`).

Zusätzlich Konfiguration entkoppeln: `BACKEND_URL` wird in `docker-compose.yml:50` gesetzt, aber im Frontend gibt es keinen einzigen Treffer dafür — es existiert gar keine Angular-Environment-Konfiguration. Die Backend-Adresse steht fest in `frontend/src/app/core/api.config.ts:1`, und `frontend/src/app/services/memory.service.ts:41` dupliziert sie nochmal. Mindestens die Duplikation entfernen, besser `environments/` einführen.

---

## P2 — Git-Hygiene

`.gitignore` im Root enthält exakt eine Zeile: `.env`. Dadurch liegen im Repository:

- 67 kompilierte `__pycache__/*.pyc` (inklusive `test_image_multimodal.cpython-314-pytest-9.0.3.pyc`, dessen `.py`-Quelle gelöscht wurde — das ist der offene W2-Punkt aus `TODO.txt:1`)
- 4 Laufzeit-Datendateien unter `backend/app/storage/data/` (`posts.json`, `chats.json`, `traces.json`, `agent_logs.json`)
- 8 generierte PNGs unter `backend/app/storage/generated_images/`

Fix: `.gitignore` um `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `.venv/`, `backend/app/storage/data/`, `backend/app/storage/generated_images/` erweitern, dann `git rm -r --cached` für die betroffenen Pfade. Ergänzend `backend/.dockerignore`, damit Tests und Cache nicht ins Image wandern.

---

## P3 — Konsistenz und Aufräumen

**Backend**
- `backend/app/main.py:35-36`: `allow_origins=["*"]` zusammen mit `allow_credentials=True` ist laut CORS-Spec unzulässig und wird vom Browser blockiert. Eines von beiden ändern.
- `backend/app/services/post_service.py:150-156`: `generate_preview` fängt alle Exceptions und wirft immer 500 — auch wenn darunter bereits eine `HTTPException` (z.B. 503 bei fehlendem HF-Token) lag. `HTTPException` durchreichen.
- `backend/app/graphs/support/validation.py:10`: `MIN_TEXT_LENGTH = 180` widerspricht `text_length=kurz` (40-80 Wörter laut `post_fields.py:131`) — kurze Posts triggern fast immer einen Retry. Schwelle von `text_length` abhängig machen.
- `delete_post` (`post_service.py:97-100`) räumt Logs, Traces und generierte Bilder nicht mit auf.
- Logs, Traces und Chats wachsen unbegrenzt ohne Pagination oder Retention.
- Toter Code: `ManagerAgent` (`manager_agent.py:236-237`), `chat_service.get_chats_by_agent`, `rag_service._list`, die `getattr`-Fallbacks in `log_service.py:58-77`, State-Felder `tool_safety_blocked` / `validation_requirements` / `errors` / `warnings`.

**Frontend**
- `frontend/src/app/services/post.service.ts:70-74` ruft `GET /api/posts/{id}/agent-trace` auf — diese Route existiert im Backend nicht (`routes_posts.py` hat nur `/preview` und `/generate-preview`). Die Methode wird nirgends verwendet.
- Ungenutzt: `getHealth`, `createPost`, `updatePost`, `generatePreview`, `getPreview` in `post.service.ts`, `memory.service.ts:search`, sowie die Facade-Signale `is*AgentWorking` und `missingFields`/`hasText`/`hasImage`.
- `home.component.ts:106-113` und `225-234` feuern je zwei `GET /api/posts/:id`-Requests für denselben Zweck.
- Fehlerbehandlung uneinheitlich: `createPost` (home), `store` (rag) und das Laden in `logs` melden Fehler nur auf der Konsole, während die Agent-Seiten `chatError` anzeigen. Überall `httpErrorDetail` aus `core/http-error.ts` nutzen.
- `chat-input` wird während der Agent arbeitet nicht deaktiviert — Doppel-Sends möglich. Die vorhandenen `is*AgentWorking`-Signale lösen genau das.
- `text-agent.component.scss` und `image-agent.component.scss` sind fast identisch — in ein gemeinsames SCSS-Partial ziehen.
- Sprachmix: Button "Create" in `home.component.html:81`, Sidebar mischt "Preview"/"Rag"/"Logs" mit "Kontakt"/"Gedächtnis", `index.html` hat `lang="en"`, "Naechstes" statt "Nächstes" in `chat-input`.
- Barrierefreiheit: Icon-Buttons ohne `aria-label`, Chat-Container ohne `role="log"`, Filter-Buttons in Logs ohne `aria-pressed`.

**Ungenutzte Backend-Endpunkte** (vom Frontend nie aufgerufen): `/api/agents/text/generate`, `/api/agents/image/generate`, `/api/agents/image/generate-prompt`, `/api/agents/manager/traces/{trace_id}`. Entweder anbinden oder entfernen.

---

## P4 — Tests und Dokumentation

- Ohne Testabdeckung: `routes_posts.py` / `post_service.py` (CRUD und Preview), Memory-Upload inklusive PDF-Pfad, `json_store.py`. Der gelöschte `test_image_multimodal.py` (W2) fehlt.
- Frontend hat genau einen Test (`app.component.spec.ts`, prüft nur Instanziierung). `ng test` braucht zudem eine Chrome-Installation bzw. `CHROME_BIN`.
- Kein Frontend-CI — `.github/workflows/backend-ci.yml` deckt nur das Backend ab.
- `backend/docs/monitoring.md:35` nennt Port 8000, korrekt ist 8080.
- `backend/backend_cmds.txt` empfiehlt `python main.py` statt des dokumentierten `uvicorn app.main:app`.
- `frontend/README.md` ist unveränderter Angular-CLI-Boilerplate ohne Projektbezug.
- README fehlt ein Troubleshooting-Abschnitt für genau die Clean-Install-Fallen aus P1.

---

## Nicht im Abgabe-Scope

Für ein Studienprojekt bewusst ausgeklammert, aber der Vollständigkeit halber: es gibt keinerlei Authentifizierung (jeder kann per `DELETE /api/logs` alle Logs löschen), `MCP_ALLOW_ANONYMOUS_ACCESS=true` in `docker-compose.yml:13`, und der Frontend-Container fährt `ng serve` statt eines Production-Builds. Diese Punkte passen gut in den W14-Abschnitt "Responsible AI / Privacy" des README.

---

## Vorgeschlagene Reihenfolge

P0 zuerst, weil dort echtes Fehlverhalten und Datenverlust drinstecken. Danach P1+P2 gemeinsam in einem Commit "reproduzierbares Setup", weil beides den Clean Install betrifft. P3 und P4 sind gut portionierbar.