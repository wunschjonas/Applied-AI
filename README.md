# Applied-AI — Marketing Multi-Agent

Angular-Frontend + FastAPI/LangGraph-Backend für Marketing-Posts: ein **Manager-Agent** orchestriert Intent, Tools (Memory/Web/Steckbrief) und Spezialisten (**Text** / **Bild**), speichert Previews und TAO-Traces.

## Stack

| Teil | Technik | Port (Docker) |
|------|---------|---------------|
| Frontend | Angular | `4200` |
| Backend | FastAPI, LangGraph, HuggingFace Inference | `8080` |
| Memory | MCP Memory Service (sqlite_vec) | `8765` |

Einstieg Backend: `uvicorn app.main:app` ([`backend/app/main.py`](backend/app/main.py)), nicht mehr `python app.py`.

## Architektur (kurz)

```text
User (Angular)
  → POST /api/agents/manager/chat
  → ManagerChatGraph
       init → Steckbrief → Intent → Plan → RAG-ReAct (Tools)
       → Route → Text-/Image-/Memory-/Web-/Clarification-Nodes
       → Validation (max. 1 Retry) → Persist → Trace
```

Weitere APIs: Posts-CRUD, Text-/Image-Agent-Chat, Memory Store/Search/Upload, Logs/Traces, Static `/generated-images`.

**Image-Agent:** Chat verfeinert das bestehende Post-Bild (img2img) bzw. erzeugt ohne Vorlagenbild per Text-to-Image.

## Voraussetzungen

- Docker + Docker Compose **oder** Python 3.12+, Node/npm
- **Pflicht:** `backend/.env` mit gültigem `HF_TOKEN` — ohne diese Datei bricht `docker compose up` ab (`env_file`)

```bash
# Linux/macOS
cp backend/.env.example backend/.env

# Windows (PowerShell / cmd)
copy backend\.env.example backend\.env
```

Token eintragen (siehe [`backend/.env.example`](backend/.env.example)):

```env
HF_TOKEN=hf_...
# optional:
# HF_MODEL_ID=...
# HF_IMAGE_MODEL_ID=...
# MCP_MEMORY_URL=http://localhost:8765/mcp
# WEB_SEARCH_ENABLED=true
# TAO_VERBOSE=true
```

Compose setzt `MCP_MEMORY_URL=http://memory:8765/mcp` automatisch.

## Start mit Docker

```bash
# aus dem Projektroot — .env muss schon existieren (siehe oben)
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:4200 |
| Backend API / Docs | http://localhost:8080/docs |
| Health | http://localhost:8080/health |
| Metrics (Prometheus) | http://localhost:8080/metrics |
| MCP Memory | http://localhost:8765 |

Volumes: `memory_data`, `backend_data` (Posts, Chats, Traces, generierte Bilder überleben Restarts). Backend hat einen Healthcheck auf `/health`.

## Lokale Entwicklung

### Memory (MCP)

```bash
docker compose up memory
```

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
# für Tests: pip install -r requirements-dev.txt
# backend/.env mit HF_TOKEN anlegen (siehe Voraussetzungen)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### Frontend

```bash
cd frontend
npm install
npm start
```

Frontend spricht das Backend unter `http://localhost:8080` an ([`frontend/src/environments/`](frontend/src/environments/), über [`api.config.ts`](frontend/src/app/core/api.config.ts)).

## Tests & CI

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest "tests/W8 Tests" -q
```

GitHub Actions: [`.github/workflows/backend-ci.yml`](.github/workflows/backend-ci.yml) — W8-Suite + Docker-Build (Fake-`HF_TOKEN`, kein Secret nötig).

## Troubleshooting (Clean Install)

| Symptom | Ursache | Fix |
|---------|---------|-----|
| `docker compose up` bricht sofort ab | `backend/.env` fehlt | `.env.example` kopieren und `HF_TOKEN` setzen |
| Agent-Calls / Preview schlagen fehl | Platzhalter-Token in `.env` | Echten HuggingFace-Token eintragen |
| `npm install` Peer-Dependency-Fehler | Angular CLI ≠ Angular Core | `@angular/cli` muss zu Angular 19 passen (`^19.1.x`) |
| Health `degraded`, Memory down | MCP-Container nicht erreichbar | `docker compose up memory` bzw. ganzes Compose |
| Frontend kann Backend nicht erreichen | falsche API-URL | Default ist `http://localhost:8080` in `src/environments/` |

## Monitoring
- **`GET /health`** — `status` (`ok`/`degraded`), `components` (storage, memory, huggingface-configured, web_search); HTTP immer 200
- **`GET /metrics`** — Prometheus (HTTP-Instrumentator + Custom Counter `manager_chat_*`, `manager_specialist_*`, `manager_validation_*`)

Details: [`backend/docs/monitoring.md`](backend/docs/monitoring.md)

## Wichtige Endpoints

| Methode | Pfad | Zweck |
|---------|------|--------|
| POST | `/api/agents/manager/chat` | Manager-Orchestrierung |
| POST | `/api/agents/text/chat` | Text nachschärfen |
| POST | `/api/agents/image/chat` | Bild per Chat verfeinern (img2img) / neu erzeugen |
| GET/POST | `/api/posts` … | Posts / Preview |
| POST/GET | `/api/memory/...` | Store, Search, List, Upload |
| GET | `/health`, `/metrics` | Betrieb |

Input-Validierung: leere/Whitespace-Messages → 422; unbekannte `post_id` → 404; Chat-UI zeigt Backend-`detail`.

---

## Stichwort-Skizzen W12–W14

Nur Stichpunkte — Fließtext (≥ ½ Seite) selbst ausformulieren (Abgabe).

### W12 – Data / Concept Drift (VL 11)

**Frage:** Wie könnte Drift das System beeinflussen? Was würde auffallen?

**Begriffe**

- Data Drift · Concept Drift · Label-/Intent-Drift · Embedding-/Retrieval-Drift
- Stationaritätsannahme bricht · Verteilungsverschiebung Input/Output

**Bezogen auf unser System**

- Keyword-Intent (`ManagerIntentClassifier`) vs. natürliche Sprache → neue Formulierungen, Slang, andere Sprachen
- RAG-Memory / MCP: veraltete Brand-Guidelines, alte Fakten, widersprüchliche Chunks
- Web-Search: aktuelle Trends vs. gespeicherte Memory → Konflikt
- HF-Modelle (Text/Bild): Modell-Updates, API-Verhalten ändert sich ohne Code-Change
- Steckbrief-/Validierungsheuristiken (Textlänge, Hashtag-Anzahl, Prompt-Länge) → früher „gute“ Posts scheitern oder schlechte passieren
- Plattform-Normen (LinkedIn/Instagram/X) ändern sich → Tonalität/Hashtags wirken veraltet

**Was würde auffallen?**

- mehr `clarification_needed` / falsche Intent-Routen
- mehr Validation-Retries / `partial_success` / Nutzer-Korrekturen im Chat
- Memory-Treffer off-topic oder widersprüchlich zum Steckbrief
- Metriken: `manager_chat_intent_total`, `manager_validation_total{retry_*}`, `manager_specialist_total{error}` steigen
- User-Feedback: „stimmt nicht mehr“, Marke falsch dargestellt
- Bilder: Stil/Qualität driftet (Caption-Modelle, Text-to-Image, img2img-Verfeinern)

**Monitoring-Anknüpfung**

- `/metrics` + `/health` · Trace-/TAO-Logs · Rate failed vs. success über Zeit vergleichen

---

### W13 – Continual Learning (VL 12)

**Frage:** Wie könnte das System mit neuen Daten verbessert werden?

**Begriffe**

- Continual Learning · Online-/Incremental Learning · Replay · Catastrophic Forgetting
- Human-in-the-Loop · Feedback-Loop · Retrieval vs. Parameter-Update
- Evaluation Gate · Versionierung von Memory/Prompts/Modellen

**Was bei uns schon „lernt“ (ohne Modell-Training)**

- MCP Memory: `memory_store` / Upload PDF/Bild → neues Wissen zur Laufzeit
- Post-Steckbrief wächst über Chat (`collect_post_data`)
- Web-Search liefert frische Fakten (kein persistentes Lernen, aber aktuelle Inputs)

**Konzept: Verbesserung mit neuen Daten**

1. **Feedback speichern** — User akzeptiert/verwirft Text/Bild → positives/negatives Beispiel + Intent + Trace-ID
2. **Memory kuratieren** — veraltete Chunks löschen/aktualisieren; Tags/Topic-Filter schärfen; Dedup
3. **Prompt-/Regel-Updates** — Specialist-Briefs, Validierungsschwellen, Keyword-Listen aus Fehlerfällen
4. **Intent-Layer** — Keyword → hybrides Intent (Keywords + kleines Classifier-/LLM-Label); Few-shot aus Feedback
5. **Evaluation-Set** — fixe Gold-Prompts (Steckbrief vollständig, Memory-Frage, Web-Frage); Regression nach Änderungen
6. **Modell-Updates** — neue HF-Modell-IDs in Config; A/B über Metriken, nicht blind ersetzen
7. **Replay** — alte erfolgreiche Traces + neue Cases mischen, damit Regeln/Memory nicht nur „neu“ kennen

**Grenzen**

- kein Fine-Tuning der Foundation Models im Projekt-Scope
- Gefahr: ungeprüftes Memory → Drift verstärken (W12 ↔ W13)
- Catastrophic Forgetting analog: neue Brand-Rules überschreiben alte ohne Versionierung

**Messbar machen**

- vor/nach Memory-Update gleiche Test-Queries · Retry-/Error-Raten · manuelle Spot-Checks TAO-Trace

---

### W14 – Responsible AI (VL 14)

**Frage:** Welche Risiken, Biases oder Missbrauchspotenziale hat euer System?

**Begriffe**

- Bias · Fairness · Transparenz · Accountability · Privacy · Safety · Misuse
- Halluzination · Deepfake-/Image-Risiken · Copyright · Informed Consent

**Systemspezifische Risiken**

- **Halluzinationen** — Marketing-Copy / Memory-Antworten klingen faktisch, sind falsch → Reputationsschaden Marke
- **Bias in HF-Modellen** — Stereotypen in Text/Bild (Geschlecht, Alter, Kultur, „Idealbild“ Campaign)
- **Memory-Poisoning** — absichtlich falsche Fakten speichern → alle späteren Posts kontaminiert
- **Web-Search** — ungeprüfte Quellen, Fake News in Posts übernommen
- **Missbrauch Content-Gen** — Spam, Phishing-Texte, irreführende Ads, Hate/Sensitive Topics ohne Filter
- **Bildrechte** — Memory-Bild-Uploads, fremde Marken/Personen, Training-Daten der Bildmodelle
- **Privacy** — Steckbrief, Chats, Traces, Uploads in JSON/MCP; `HF_TOKEN`; keine Auth im Demo-Setup
- **Transparenz** — User sieht fertigen Post, kaum Hinweis „KI-generiert“ / Quellen aus Memory/Web
- **Over-trust** — Validation nur heuristisch (Länge/Hashtags), keine Faktenprüfung
- **Automation Bias** — Manager-Delegation wirkt autoritativ; Fehler propagieren Text→Image

**Mögliche Gegenmaßnahmen (Stichworte)**

- Human review vor Publish · Quellenangabe Memory/Web im Trace · Content-Policy / Deny-Topics
- Memory: nur vertrauenswürdige Uploads, Review vor Store · Retention/Löschen
- Auth + Rate-Limits später · Audit-Logs (TAO schon da) · Disclaimer in UI
- Bias-Spotchecks diverse Personas/Themen · kein personenbezogenes Scraping

**Bezug Monitoring**

- Anomalien in Intent/Validation als Safety-Signal · Health/degraded ≠ ethische Unbedenklichkeit
