# Anforderungen – Code-Nachweis (Index)

Quellen: [`Bewertungen/semesterprojekt_anleitung.pdf`](Bewertungen/semesterprojekt_anleitung.pdf),  
[`Bewertungen/semesterprojekt_bewertung.pdf`](Bewertungen/semesterprojekt_bewertung.pdf)  
Kurz-Checkliste: [`Anforderungserfuellung.md`](Anforderungserfuellung.md)

**Detaillierte Einträge** (Status, Code-Stellen, Besprechung, Nachweise) liegen unter  
[`Abgabe-Nachweis/`](Abgabe-Nachweis/README.md) – je Anforderung eine Datei.

**Legende Status:** `ja` · `teilweise` · `offen`

---

## Pflicht P1–P5

| ID | Status | Kern-Ort(e) | Detail |
|----|--------|-------------|--------|
| P1 | ja | `rag.py`, `chat_with_tools`, `MEMORY_SEARCH_TOOL` | [P1.md](Abgabe-Nachweis/P/P1/P1.md) |
| P2 | ja | `trace_service.add_step`, `TAO_VERBOSE`, Logs-UI | [P2.md](Abgabe-Nachweis/P/P2/P2.md) |
| P3 | teilweise | `manager_chat_graph.py` | [P3.md](Abgabe-Nachweis/P/P3/P3.md) |
| P4 | teilweise | Root-`README.md` | [P4.md](Abgabe-Nachweis/P/P4/P4.md) |
| P5 | ja | Git-Historie | [P5.md](Abgabe-Nachweis/P/P5/P5.md) |

---

## Wahlpflicht W1–W14

| ID | Status | Kern-Ort(e) | Detail |
|----|--------|-------------|--------|
| W1 | ja | Manager-Graph + Text/Image Agents | [W1.md](Abgabe-Nachweis/W/W1/W1.md) |
| W2 | ja | Image multipart + img2img | [W2.md](Abgabe-Nachweis/W/W2/W2.md) |
| W3 | ja | MCP Memory + `RAGService` | [W3.md](Abgabe-Nachweis/W/W3/W3.md) |
| W4 | ja | `rag_react_node` Tool-Loop | [W4.md](Abgabe-Nachweis/W/W4/W4.md) |
| W5 | ja | Traces + Logs-Seite | [W5.md](Abgabe-Nachweis/W/W5/W5.md) |
| W6 | ja | FastAPI Routes in `main.py` | [W6.md](Abgabe-Nachweis/W/W6/W6.md) |
| W7 | ja | `docker-compose.yml` | [W7.md](Abgabe-Nachweis/W/W7/W7.md) |
| W8 | ja | `backend/tests/W8 Tests/` (5) | [W8.md](Abgabe-Nachweis/W/W8/W8.md) |
| W9 | ja | Pydantic + Upload-Checks + `validation_node` | [W9.md](Abgabe-Nachweis/W/W9/W9.md) |
| W10 | offen | — | [W10.md](Abgabe-Nachweis/W/W10/W10.md) |
| W11 | ja | `GET /health` | [W11.md](Abgabe-Nachweis/W/W11/W11.md) |
| W12 | offen | Reflexion | [W12.md](Abgabe-Nachweis/W/W12/W12.md) |
| W13 | offen | Konzept | [W13.md](Abgabe-Nachweis/W/W13/W13.md) |
| W14 | offen | Reflexion | [W14.md](Abgabe-Nachweis/W/W14/W14.md) |

**Schein-Minimum:** P1–P5 alle + ≥ 11 von W1–W14.  
**Aktuell Wahlpflicht:** 10 ja (W1–W9, W11) → **noch 1** nötig (empfohlen: W12–W14 für Note Dim. 5).

---

## Vorschlag Reihenfolge

1. [P1](Abgabe-Nachweis/P/P1/P1.md) → [P2](Abgabe-Nachweis/P/P2/P2.md) → [P3](Abgabe-Nachweis/P/P3/P3.md)/[P4](Abgabe-Nachweis/P/P4/P4.md) → [P5](Abgabe-Nachweis/P/P5/P5.md)  
2. W1–W9, W11 (Technik kurz bestätigen)  
3. Entscheidung: [W10](Abgabe-Nachweis/W/W10/W10.md) vs. [W12](Abgabe-Nachweis/W/W12/W12.md)–[W14](Abgabe-Nachweis/W/W14/W14.md)  
4. Nachweise (Screenshots) in den jeweiligen Ordnern sammeln  
