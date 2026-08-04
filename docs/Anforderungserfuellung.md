# Anforderungserfüllung – Stand Checkliste

Quellen: [`Bewertungen/semesterprojekt_anleitung.pdf`](Bewertungen/semesterprojekt_anleitung.pdf),  
[`Bewertungen/semesterprojekt_bewertung.pdf`](Bewertungen/semesterprojekt_bewertung.pdf)

**Audit-Stand:** 04.08.2026 (erneuter Durchgang durch Code, Tests, Docker, README, `docs/`)

**Abgabe-Minimum (Schein):** alle **P1–P5** + mind. **11 von 14** Wahlpflicht (W1–W14).  
**Note:** separat über 6 Dimensionen (0–3 Punkte, max. 18).

Legende: **ja** = fachlich umgesetzt und abnahmefähig · **teilweise** = Code da, Doku/Nachweis/README noch riskant · **offen** = fehlt

---

## Gesamturteil

| Bereich | Stand | Kommentar |
|---------|-------|-----------|
| Technik (Agenten, RAG, API, Docker, Tests) | **stark** | Multi-Agent + LangGraph + Tool-Use + Multimodalität + MCP-Memory sind real implementiert |
| Schein-Schwelle P1–P5 | **fast** | P1/P2/P5 klar; P3/P4 durch veraltetes README gefährdet |
| Schein-Schwelle W (≥11) | **10 / 11** | W1–W9, W11 = ja; **noch 1 W** nötig |
| Abgabe-Paket (Doku/Nachweise/Reflexion) | **dünn** | README falsch; keine W12–W14; Nachweise (Screenshots/Logs) noch sammeln |
| Noten-Potenzial | **mittel → gut** | Domäne & Agentik gut; Reflexion (Dim 5) und README/Architektur-Begründung limitieren die Note |

**Wichtigste Lücke für den Schein:** eine weitere Wahlpflicht (**W12/W13/W14** oder **W10**).  
**Wichtigste Lücke für die Note/P-Abnahme:** Root-`README.md` aktualisieren (falsche Aussagen).

---

## Pflichtanforderungen (P1–P5) – alle nötig

| ID | Anforderung | Status | Evidenz im Repo | Risiko / Noch zu tun |
|----|-------------|--------|-----------------|----------------------|
| **P1** | Echter AI Agent mit Tool-Use | **ja** | ReAct-Loop `rag_react_node` → `chat_with_tools` + `MEMORY_SEARCH_TOOL` ([`rag.py`](../backend/app/graphs/nodes/rag.py), [`huggingface_service.py`](../backend/app/services/huggingface_service.py), MCP in [`rag_service.py`](../backend/app/services/rag_service.py)); Test [`test_agentic_rag.py`](../backend/tests/W8%20Tests/test_agentic_rag.py) | Abgabe: Trace/Log-Screenshot mit `call_memory_search` |
| **P2** | TAO sichtbar (≥ 3 Schritte) | **ja** | Jeder Trace-Step: `thought` / `action` / `observation` ([`dependencies.py`](../backend/app/graphs/dependencies.py), [`trace_service.py`](../backend/app/services/trace_service.py)); Terminal via `TAO_VERBOSE`; Test [`test_tao_trace.py`](../backend/tests/W8%20Tests/test_tao_trace.py); Graph erzeugt klar >3 Steps pro Run | Abgabe: Terminal- oder Trace-Screenshot ≥ 3 Iterationen |
| **P3** | Framework (LangGraph o. ä.) | **teilweise** | **Code: ja** – `StateGraph` in [`manager_chat_graph.py`](../backend/app/graphs/manager_chat_graph.py), Dependency `langgraph` | **README lügt:** „LangGraph (noch nicht implementiert)“ → Korrektur + 2–3 Sätze Begründung (warum LangGraph) |
| **P4** | README (Kurzbeschr., Architektur, Install/.env, Beispiel) | **teilweise** | Start/Docker grob vorhanden; tiefere Doku liegt unter [`docs/`](./) | README nennt `python app.py` (Datei existiert nicht → `main.py` / `uvicorn app.main:app`); keine `.env`/`HF_TOKEN`-Erklärung; kein Architektur-Überblick; kein Ein-/Ausgabe-Beispiel |
| **P5** | Git-Historie (≥ 10 Commits) | **ja** | **40 Commits**, inkrementell (LangGraph, Memory, Frontend, RAG, Cleanup, …) | Optional `git log --oneline` als Nachweis in der Abgabe |

**Pflicht-Fazit:** Implementierung trägt P1–P5; **ohne README-Fix wirkt P3/P4 nach außen unerfüllt**.

---

## Wahlpflichtanforderungen (W1–W14) – mind. 11 nötig

| ID | Anforderung | VL | Status | Evidenz | Noch zu tun |
|----|-------------|----|--------|---------|-------------|
| **W1** | Multi-Agent (Orchestrator + Subagenten) | 4 | **ja** | Manager-Graph + TextAgent + ImageAgent; Test `test_manager_combined.py` | Rollen kurz in Projektdoku beschreiben |
| **W2** | Multimodale Eingabe | 4 | **ja** | Image-Agent `source_image` → img2img; Memory PDF/Bild-Upload ([`routes_image_agent.py`](../backend/app/api/routes_image_agent.py), [`routes_memory.py`](../backend/app/api/routes_memory.py)); Test `test_image_multimodal.py` | Screenshot Referenzbild-Flow |
| **W3** | RAG eigene Wissensbasis | 7 | **ja** | MCP Memory Service in Compose; `RAGService`; RAG-UI | Demo: speichern → fragen |
| **W4** | Agentic RAG (Retrieval als Tool) | 7 | **ja** | LLM entscheidet über `memory_search`; nicht nur hartcodiert; Test `test_agentic_rag.py` | Trace-Nachweis |
| **W5** | Observability | 7 | **ja** | Traces, Agent-Logs, TAO-Print, Logs-Seite Frontend | Beispiel-Trace verlinken |
| **W6** | HTTP-API | 9 | **ja** | FastAPI [`main.py`](../backend/app/main.py) + `/api/agents/*`, `/api/posts`, `/api/memory` | — |
| **W7** | Containerisierung | 9/13 | **ja** | [`docker-compose.yml`](../docker-compose.yml) (memory + backend + frontend), Dockerfiles | Frischer Clone-Test empfohlen |
| **W8** | ≥ 5 automatisierte Tests | 10 | **ja** | Genau **5** Tests in [`backend/tests/W8 Tests/`](../backend/tests/W8%20Tests/) | `pytest "tests/W8 Tests" -q` |
| **W9** | Validierung & Fehlerbehandlung | 9/10 | **ja** | Pydantic-Schemas; Upload-Limits/MIME; `HTTPException`; Artifact-Validation im Graph | 1–2 Beispiele in Doku |
| **W10** | CI/CD bei Push | 13 | **offen** | Kein `.github/workflows` (o. ä.) | Optional Action mit pytest **oder** durch Reflexion ersetzen |
| **W11** | Monitoring (`/health`) | 11/13 | **ja** | `GET /health` in [`main.py`](../backend/app/main.py) | In README erwähnen |
| **W12** | Data/Concept Drift – Reflexion | 11 | **offen** | Keine Markdown-Reflexion | ≥ ½ Seite, konkret auf Marketing-Agent/RAG |
| **W13** | Continual Learning – Konzept | 12 | **offen** | — | ≥ ½ Seite |
| **W14** | Responsible AI – Reflexion | 14 | **offen** | — | ≥ ½ Seite (Bias, Missbrauch von Content-Gen) |

### Wahlpflicht-Zählung

| Kategorie | IDs | Anzahl |
|-----------|-----|--------|
| **ja** | W1–W9, W11 | **10** |
| **offen** | W10, W12–W14 | **4** |
| **Ziel** | — | ≥ **11** |

**→ Noch genau 1 Wahlpflicht fürs Minimum.** Empfohlen: **W12 + W13 + W14** schreiben (Schein + Noten-Dimension 5), alternativ nur eine davon oder W10.

---

## Abgabe-Paket (laut Anleitung)

| # | Liefergegenstand | Status | Befund |
|---|------------------|--------|--------|
| 1 | Lauffähiger Code, reproduzierbar | **teilweise** | Docker-Stack vorhanden und sinnvoll; README-Startbefehl `python app.py` ist **falsch** (korrekt: `python main.py` bzw. `uvicorn app.main:app`); `.env` mit `HF_TOKEN` nötig, in README nicht erklärt |
| 2 | Ausführliche Projektdokumentation | **teilweise** | Unter `docs/` viel Material (Architektur, Audit, MCP-Zusammenfassung, Postman) – wirkt eher als Arbeitsnotizen; fehlt eine klare Abgabe-Projektdoku: Architektur *warum*, Designentscheidungen, Grenzen |
| 3 | Anforderungserfüllung mit Nachweis | **teilweise** | Diese Datei; pro Punkt noch Screenshot/Log/Commit-Verweis ergänzen |
| 4 | Reflexionstexte W12–W14 | **offen** | Keine Dateien vorhanden |

---

## Noten-Dimensionen (Einschätzung nach Code-Review)

Voraussetzung: Schein-Schwelle. Grobe Selbsteinschätzung (0–3):

| # | Dimension | Max | Einschätzung | Begründung |
|---|-----------|-----|--------------|------------|
| 1 | Systemverständnis & Architektur | 3 | **1–2** | System ist durchdacht (Graph, Memory, Specialists), aber README/Abgabe-Doku begründen Entscheidungen zu wenig; Alternativen/Grenzen fehlen als Abgabe-Text |
| 2 | Qualität der Agentic-Implementierung | 3 | **2** | Mehrstufiger Graph, Tool-Entscheidung, Fallbacks, Briefing, Validation-Retry – nicht nur ein starres Skript; Intent teils keyword-basiert |
| 3 | Domäneneignung & Eigenleistung | 3 | **2–3** | Eigene Domäne (Marketing-Post Multi-Agent), kein reines Tutorial-Copy |
| 4 | Code- & Projektqualität | 3 | **2** | Modulare Struktur, Docker, 5 Tests, gute Commit-Historie; README-Drift und kein CI |
| 5 | Reflexionstiefe | 3 | **0–1** | Keine W12–W14 → hier aktuell der größte Noten-Hebel nach unten |
| 6 | Kursbezug | 3 | **2** | TAO, ReAct/Tools, Multi-Agent, RAG/MCP sind umgesetzt; in der Doku noch expliziter auf VL-Konzepte mappen |

**Geschätzte Bandbreite (wenn Schein geschafft):** eher **mittel**, mit guten Reflexionen + README/Projektdoku Richtung **gut** verschiebbar.

---

## Was ihr abhaken könnt (Checkliste)

### Sofort abhakbar (Technik steht)

- [x] P1 Tool-Use (`memory_search`)
- [x] P2 TAO-Traces
- [x] P5 Git-Historie
- [x] W1 Multi-Agent
- [x] W2 Multimodal (Bild + PDF)
- [x] W3 RAG / Memory
- [x] W4 Agentic RAG
- [x] W5 Observability
- [x] W6 FastAPI
- [x] W7 Docker Compose
- [x] W8 Fünf Tests
- [x] W9 Validierung/Fehler
- [x] W11 `/health`

### Noch nicht abhakbar

- [ ] P3/P4 aus Sicht der Abgabe (README korrigieren + anreichern)
- [ ] W10 CI **oder** bewusst weglassen
- [ ] W12 Drift-Reflexion
- [ ] W13 Continual-Learning-Konzept
- [ ] W14 Responsible-AI-Reflexion
- [ ] Abgabe-Nachweise (Screenshots/Logs) sammeln
- [ ] Kurze, abgabetaugliche Projektdoku (Architektur/Grenzen)

---

## Empfohlene Reihenfolge (priorisiert)

1. **README fixen** (P3/P4/Abgabe 1): LangGraph als implementiert; Start via `main.py`/`uvicorn`; `.env` (`HF_TOKEN`, `MCP_MEMORY_URL`); Kurzarchitektur; ein Beispiel-Dialog  
2. **Mindestens eine Reflexion W12/W13/W14** → 11. Wahlpflicht (besser alle drei)  
3. **Nachweise:** Trace mit Tool-Call, TAO-Terminal, `pytest "tests/W8 Tests"`, `GET /health`, optional `docker compose up`  
4. Optional **W10** GitHub Action  
5. Eine klare **Projektdoku** (Designentscheidungen + Grenzen) aus bestehenden `docs/`-Dateien verdichten
