# LangGraph Multi-Agent System – Implementierungsplan

## Projektziel

Ein intelligenter Marketing-Agent, der auf eine User-Anfrage hin sowohl
Marketingtext als auch ein passendes Bild generiert. Ein Manager-Agent
orchestriert dabei eigenständig die Unteragenten.

---

## 1. Architektur-Übersicht

```
User Request (POST /api/agent/run)
        │
        ▼
┌─────────────────────┐
│    Manager Agent     │  ◄── Analysiert Task, entscheidet Routing
│    (Supervisor)      │
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    ▼             ▼
┌────────┐  ┌────────────┐
│  Text  │  │   Image    │
│ Agent  │  │   Agent    │
│(GPT-4o)│  │(DALL-E 3)  │
└────┬───┘  └─────┬──────┘
     │             │
     └──────┬──────┘
            ▼
    ┌───────────────┐
    │   Aggregator  │  ◄── Fasst Ergebnisse zusammen
    └───────┬───────┘
            ▼
     API Response
  { text: "...", image_url: "..." }
```

### Ablauf

1. User schickt einen Marketingauftrag z. B. `"Erstelle einen Post für unser neues Produkt XY"`
2. Der **Manager Agent** analysiert den Task via LLM und entscheidet:
   - Nur Text benötigt → routet zu `text_agent`
   - Nur Bild benötigt → routet zu `image_agent`
   - Beides benötigt → routet zu beiden (parallel oder sequentiell)
3. **Text Agent** ruft GPT-4o auf und generiert Marketingtext
4. **Image Agent** ruft DALL-E 3 auf und gibt eine Bild-URL zurück
5. **Aggregator** kombiniert die Teilresultate
6. Antwort geht zurück an den FastAPI-Endpunkt

---

## 2. LangGraph Konzepte im Einsatz

| LangGraph-Konzept | Verwendung im Projekt |
|---|---|
| `StateGraph` | Zentraler Graph, der alle Nodes verbindet |
| `TypedDict` State | `AgentState` hält alle Zwischenergebnisse |
| Nodes | Je eine Funktion pro Agent + Aggregator |
| Conditional Edges | Manager entscheidet dynamisch das Routing |
| `END` | Graph terminiert nach Aggregation |

---

## 3. AgentState

Der gemeinsame Zustand, der durch den gesamten Graph fließt:

```python
# agents/state.py
from typing import TypedDict, Literal

class AgentState(TypedDict):
    task: str              # Original User-Input
    run_text: bool         # Manager: soll Text generiert werden?
    run_image: bool        # Manager: soll Bild generiert werden?
    text_result: str       # Output des Text-Agenten
    image_result: str      # Bild-URL vom Image-Agenten
    final_output: dict     # Aggregiertes Ergebnis { text, image_url }
    error: str             # Fehlermeldung falls etwas schiefläuft
```

---

## 4. Dateienstruktur

```
backend/
├── app.py                      # FastAPI + Einstiegspunkt
├── requirements.txt
├── Dockerfile
├── .env                        # OPENAI_API_KEY (nicht ins Git!)
└── agents/
    ├── __init__.py
    ├── state.py                # AgentState TypedDict
    ├── manager_agent.py        # Supervisor: analysiert Task, setzt run_text/run_image
    ├── text_agent.py           # Text-Generierung via GPT-4o
    ├── image_agent.py          # Bild-Generierung via DALL-E 3
    ├── aggregator.py           # Fasst text_result + image_result zusammen
    └── graph.py                # StateGraph bauen + kompilieren
```

---

## 5. Nodes & Edges im Detail

### Nodes

```
manager_node    → ruft Manager Agent auf → setzt run_text, run_image
text_node       → ruft Text Agent auf    → setzt text_result
image_node      → ruft Image Agent auf   → setzt image_result
aggregator_node → kombiniert Ergebnisse  → setzt final_output
```

### Graph-Aufbau

```
START
  │
  ▼
manager_node
  │
  ├─── (run_text=True)  ──► text_node  ──► aggregator_node ──► END
  │
  ├─── (run_image=True) ──► image_node ──► aggregator_node ──► END
  │
  └─── (beides=True)    ──► text_node + image_node (sequentiell) ──► aggregator_node ──► END
```

Conditional Edge nach `manager_node`:
- `"text_only"`  → next node: `text_node`
- `"image_only"` → next node: `image_node`
- `"both"`       → next node: `text_node` (dann `image_node`, dann `aggregator_node`)

---

## 6. Manager Agent – Routing-Logik

Der Manager Agent fragt das LLM, ob Text, Bild oder beides gebraucht wird.

```python
# agents/manager_agent.py
# Prompt-Beispiel für den Manager:
MANAGER_PROMPT = """
Du bist ein Marketing-Manager. Analysiere folgenden Auftrag und entscheide,
ob Text, ein Bild oder beides erstellt werden soll.

Auftrag: {task}

Antworte NUR mit einem JSON: {{"run_text": true/false, "run_image": true/false}}
"""
```

Die Antwort wird geparst → `run_text` und `run_image` werden im State gesetzt.
Der Conditional Edge liest dann den State aus und wählt den nächsten Node.

---

## 7. Text Agent

```python
# agents/text_agent.py
# Ruft GPT-4o auf mit dem originalen Task
# Speichert generierten Text in state["text_result"]
```

Beispiel-Prompt:
```
Du bist ein kreativer Marketing-Texter.
Erstelle für folgenden Auftrag einen ansprechenden Marketingtext (max. 150 Wörter):
{task}
```

---

## 8. Image Agent

```python
# agents/image_agent.py
# Ruft DALL-E 3 über openai.images.generate() auf
# Leitet aus dem Task einen Bildprompt ab
# Speichert die URL in state["image_result"]
```

Workflow:
1. GPT-4o generiert einen kurzen, bildbeschreibenden DALL-E Prompt aus dem Task
2. DALL-E 3 generiert das Bild
3. URL wird im State gespeichert

---

## 9. API Endpunkte (FastAPI)

```
POST /api/agent/run
  Body:  { "task": "Erstelle einen Post für Produkt XY" }
  Response: { "text": "...", "image_url": "https://..." }

POST /api/agent/stream   (optional, Phase 2)
  Body:  { "task": "..." }
  Response: Server-Sent Events (SSE) mit Status-Updates
```

---

## 10. Benötigte Dependencies

Zu `requirements.txt` hinzufügen:

```
langchain-openai    # LangChain OpenAI-Integration (GPT-4o)
openai              # Direktes OpenAI SDK (DALL-E 3)
python-dotenv       # .env Datei laden
sse-starlette       # SSE-Streaming (Phase 2)
```

---

## 11. Umgebungsvariablen (.env)

```
OPENAI_API_KEY=sk-...
```

`.env` in `.gitignore` eintragen!

---

## 12. Implementierungsreihenfolge

| Schritt | Datei | Aufgabe |
|---|---|---|
| 1 | `agents/state.py` | `AgentState` TypedDict definieren |
| 2 | `agents/manager_agent.py` | Supervisor mit Routing-Entscheidung |
| 3 | `agents/text_agent.py` | GPT-4o Text-Generierung |
| 4 | `agents/image_agent.py` | DALL-E 3 Bild-Generierung |
| 5 | `agents/aggregator.py` | Ergebnisse zusammenführen |
| 6 | `agents/graph.py` | StateGraph bauen, Nodes/Edges verdrahten |
| 7 | `app.py` | FastAPI Endpunkte an Graph anbinden |
| 8 | `requirements.txt` | Neue Dependencies ergänzen |
| 9 | `.env` + `Dockerfile` | API-Key sicher übergeben |

---

## 13. Testbarkeit

- Jeder Agent kann isoliert getestet werden (pure Python-Funktion)
- Graph kann mit einem Mock-State manuell aufgerufen werden: `graph.invoke({"task": "Test"})`
- FastAPI bietet `/docs` (Swagger UI) zum manuellen Testen der Endpunkte
