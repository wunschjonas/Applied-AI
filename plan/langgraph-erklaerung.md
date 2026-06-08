# LangGraph – Wie es funktioniert

## Was ist LangGraph?

LangGraph ist ein Framework von LangChain, das KI-Agenten als **gerichteten Graphen** modelliert.
Anstatt Agenten als einfache Ketten (`A → B → C`) zu bauen, ermöglicht LangGraph:

- **Schleifen** (ein Agent kann mehrfach aufgerufen werden)
- **Bedingtes Routing** (je nach Ergebnis wird ein anderer Pfad eingeschlagen)
- **Gemeinsamer Zustand** (alle Nodes teilen sich einen State)
- **Parallele Ausführung** (mehrere Agents gleichzeitig)

Das Grundprinzip: **Nodes** sind die Arbeiter, **Edges** sind die Wege dazwischen,
und der **State** ist das gemeinsame Gedächtnis.

---

## Die drei Kernkonzepte

### 1. State – das gemeinsame Gedächtnis

Der State ist ein Python-Dictionary (`TypedDict`), das durch den **gesamten Graphen** gereicht wird.
Jeder Node liest aus dem State und schreibt seine Ergebnisse zurück.

```
User-Input
    │
    ▼
{ task: "Erstelle Post für Produkt XY",  ◄── State zu Beginn
  run_text: False,
  run_image: False,
  text_result: "",
  image_result: "",
  final_output: {} }
    │
    ▼ Manager Node verarbeitet...
{ task: "Erstelle Post für Produkt XY",  ◄── State nach Manager
  run_text: True,
  run_image: True,          ← Manager hat entschieden: beides
  text_result: "",
  image_result: "",
  final_output: {} }
    │
    ▼ Text Node verarbeitet...
{ ...,
  text_result: "Entdecke Produkt XY...",  ◄── Text-Agent hat geschrieben
  image_result: "",
  ... }
```

**Wichtig:** Kein Node überschreibt den gesamten State – er gibt nur ein Dict mit den
geänderten Feldern zurück. LangGraph merged das automatisch.

---

### 2. Nodes – die Arbeiter

Jeder Node ist eine gewöhnliche Python-Funktion:

```python
def text_node(state: AgentState) -> dict:
    task = state["task"]
    result = llm.invoke(f"Schreibe Marketingtext für: {task}")
    return {"text_result": result.content}   # nur geänderte Felder zurückgeben
```

- Bekommt den **aktuellen State** als Input
- Gibt ein **partielles Dict** zurück (nur was sich geändert hat)
- Hat keine Kenntnis von anderen Nodes – völlig isoliert

---

### 3. Edges – die Verbindungen

Edges definieren, **welcher Node nach welchem** ausgeführt wird.

**Normale Edge** (immer dieser Pfad):
```python
graph.add_edge("text_node", "aggregator_node")
# text_node ist fertig → immer weiter zu aggregator_node
```

**Conditional Edge** (dynamische Entscheidung):
```python
graph.add_conditional_edges(
    "manager_node",          # Von diesem Node...
    routing_function,        # ...diese Funktion entscheidet den nächsten Node
    {
        "text_only":  "text_node",
        "image_only": "image_node",
        "both":       "text_node",
    }
)

def routing_function(state: AgentState) -> str:
    if state["run_text"] and state["run_image"]:
        return "both"
    elif state["run_text"]:
        return "text_only"
    else:
        return "image_only"
```

Die `routing_function` bekommt den State und gibt einen **String-Schlüssel** zurück.
LangGraph schlägt diesen Key in der Map nach und wählt den nächsten Node.

---

## Wie die Dateien in unserem Projekt zusammenspielen

```
┌─────────────────────────────────────────────────────────┐
│                        app.py                            │
│  FastAPI-Endpunkt empfängt Request                      │
│  → ruft graph.invoke({"task": user_input}) auf          │
│  → gibt final_output als HTTP-Response zurück           │
└────────────────────────┬────────────────────────────────┘
                         │ importiert
                         ▼
┌─────────────────────────────────────────────────────────┐
│                       graph.py                           │
│  Baut den StateGraph zusammen:                          │
│  - importiert alle Nodes                                │
│  - registriert Nodes: graph.add_node(...)               │
│  - verbindet Nodes: graph.add_edge(...)                 │
│  - kompiliert: app = graph.compile()                    │
└──┬──────────────┬──────────────┬──────────────┬─────────┘
   │              │              │              │
   │ importiert   │ importiert   │ importiert   │ importiert
   ▼              ▼              ▼              ▼
┌────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐
│state.py│  │manager_  │  │text_     │  │image_     │
│        │  │agent.py  │  │agent.py  │  │agent.py   │
│AgentState│ │          │  │          │  │           │
│TypedDict │ │→ setzt   │  │→ setzt   │  │→ setzt    │
│          │ │run_text  │  │text_     │  │image_     │
│          │ │run_image │  │result    │  │result     │
└────────┘  └──────────┘  └──────────┘  └───────────┘
                                              │
                                              ▼
                                       ┌───────────┐
                                       │aggregator │
                                       │.py        │
                                       │→ setzt    │
                                       │final_     │
                                       │output     │
                                       └───────────┘
```

### Abhängigkeiten im Detail

| Datei | Importiert | Gibt zurück |
|---|---|---|
| `state.py` | nichts | `AgentState` (TypedDict-Definition) |
| `manager_agent.py` | `state.py`, `langchain_openai` | `{"run_text": bool, "run_image": bool}` |
| `text_agent.py` | `state.py`, `langchain_openai` | `{"text_result": str}` |
| `image_agent.py` | `state.py`, `openai` | `{"image_result": str}` |
| `aggregator.py` | `state.py` | `{"final_output": dict}` |
| `graph.py` | alle agents, `state.py`, `langgraph` | kompilierter Graph |
| `app.py` | `graph.py` | HTTP Response |

---

## Der Lebenszyklus einer Anfrage

```
1. POST /api/agent/run  { "task": "Post für Produkt XY" }
        │
        ▼
2. app.py ruft auf:
   result = graph.invoke({"task": "Post für Produkt XY"})

        │
        ▼
3. LangGraph startet bei START-Node
   → State: { task: "Post für Produkt XY", run_text: False, ... }

        │
        ▼
4. manager_node läuft:
   → LLM analysiert Task
   → gibt zurück: { run_text: True, run_image: True }
   → State wird gemerged: { task: "...", run_text: True, run_image: True, ... }

        │
        ▼
5. Conditional Edge prüft State → routing_function gibt "both" zurück

        │
        ▼
6. text_node läuft:
   → GPT-4o generiert Text
   → gibt zurück: { text_result: "Entdecke Produkt XY..." }

        │
        ▼
7. image_node läuft:
   → DALL-E 3 generiert Bild
   → gibt zurück: { image_result: "https://oaidalleapi..." }

        │
        ▼
8. aggregator_node läuft:
   → kombiniert text_result + image_result
   → gibt zurück: { final_output: { text: "...", image_url: "..." } }

        │
        ▼
9. Graph erreicht END
   → graph.invoke() gibt den finalen State zurück

        │
        ▼
10. app.py extrahiert final_output und sendet HTTP Response:
    { "text": "Entdecke Produkt XY...", "image_url": "https://..." }
```

---

## Was LangGraph besonders macht

### vs. einfache Funktionskette

```python
# Ohne LangGraph – starr, keine Flexibilität
def pipeline(task):
    text = generate_text(task)
    image = generate_image(task)
    return aggregate(text, image)

# Mit LangGraph – dynamisch, erweiterbar
result = graph.invoke({"task": task})
# Der Graph entscheidet selbst, welche Nodes laufen
```

### Vorteile im Überblick

| Feature | Bedeutung für unser Projekt |
|---|---|
| **Shared State** | Alle Agents sehen denselben Task und die Ergebnisse der anderen |
| **Conditional Routing** | Manager entscheidet dynamisch: Text? Bild? Beides? |
| **Erweiterbarkeit** | Neuen Agent hinzufügen = neuen Node + neue Edge |
| **Fehlerbehandlung** | Error-Node kann bei Fehler angesprungen werden |
| **Observability** | LangGraph loggt jeden Node-Aufruf mit State |
| **Streaming** | `graph.astream()` schickt State-Updates in Echtzeit |

---

## Kompilierung des Graphen

```python
# graph.py – vereinfachtes Beispiel
from langgraph.graph import StateGraph, END
from agents.state import AgentState

graph = StateGraph(AgentState)

# Nodes registrieren
graph.add_node("manager_node", manager_agent)
graph.add_node("text_node", text_agent)
graph.add_node("image_node", image_agent)
graph.add_node("aggregator_node", aggregator)

# Einstiegspunkt setzen
graph.set_entry_point("manager_node")

# Conditional Edge nach Manager
graph.add_conditional_edges("manager_node", routing_function, {
    "text_only":  "text_node",
    "image_only": "image_node",
    "both":       "text_node",
})

# Feste Edges zu Aggregator
graph.add_edge("text_node", "aggregator_node")
graph.add_edge("image_node", "aggregator_node")
graph.add_edge("aggregator_node", END)

# Kompilieren → ab jetzt aufrufbar
app = graph.compile()
```

Nach `graph.compile()` ist der Graph ein aufrufbares Objekt:
- `app.invoke(state)` → synchron, gibt finalen State zurück
- `app.astream(state)` → async, streamt State-Updates als Events
