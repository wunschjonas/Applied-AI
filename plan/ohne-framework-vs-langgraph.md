# Agents ohne Framework vs. mit LangGraph

## Die Frage: Braucht man überhaupt ein Framework?

Nein – technisch nicht. Man kann dasselbe mit reinem Python bauen.
Aber der Aufwand wächst schnell, sobald die Logik komplexer wird.
Diese Datei zeigt den direkten Vergleich.

---

## Variante A: Kein Framework – reines Python

### Wie würde das aussehen?

Ohne LangGraph baut man die Orchestrierung manuell:

```python
# backend/app.py – OHNE Framework

import openai
import json

client = openai.OpenAI()

def manager_decision(task: str) -> dict:
    """Manager entscheidet, was gebraucht wird."""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": f"""Analysiere: '{task}'
            Antworte NUR mit JSON: {{"run_text": true/false, "run_image": true/false}}"""
        }]
    )
    return json.loads(response.choices[0].message.content)

def generate_text(task: str) -> str:
    """Text Agent."""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"Schreibe Marketingtext für: {task}"}]
    )
    return response.choices[0].message.content

def generate_image(task: str) -> str:
    """Image Agent."""
    response = client.images.generate(
        model="dall-e-3",
        prompt=task,
        size="1024x1024"
    )
    return response.data[0].url

def run_pipeline(task: str) -> dict:
    """Manuelle Orchestrierung."""
    # Schritt 1: Manager entscheiden lassen
    decision = manager_decision(task)

    text_result = ""
    image_result = ""

    # Schritt 2: Manuell routen
    if decision["run_text"]:
        text_result = generate_text(task)

    if decision["run_image"]:
        image_result = generate_image(task)

    # Schritt 3: Manuell aggregieren
    return {
        "text": text_result,
        "image_url": image_result
    }
```

### FastAPI-Endpunkt dazu

```python
@app.post("/api/agent/run")
async def run_agent(request: AgentRequest):
    result = run_pipeline(request.task)
    return result
```

Das funktioniert. Für diesen einfachen Fall ist es sogar übersichtlich.

---

## Wo das ohne Framework anfängt zu brechen

### Problem 1: Fehlerbehandlung explodiert

Was wenn `generate_text` fehlschlägt? Was wenn die OpenAI API nicht antwortet?
Man muss jeden Schritt manuell absichern:

```python
def run_pipeline(task: str) -> dict:
    try:
        decision = manager_decision(task)
    except json.JSONDecodeError:
        # LLM hat kein valides JSON zurückgegeben – was jetzt?
        decision = {"run_text": True, "run_image": True}  # Fallback hart eingebaut
    except openai.APIError as e:
        raise HTTPException(status_code=503, detail=str(e))

    text_result = ""
    if decision["run_text"]:
        try:
            text_result = generate_text(task)
        except openai.APIError:
            text_result = ""  # Stille Fehler sind gefährlich

    image_result = ""
    if decision["run_image"]:
        try:
            image_result = generate_image(task)
        except openai.APIError:
            image_result = ""

    return {"text": text_result, "image_url": image_result}
```

Jede neue Funktion → neuer try/except-Block. Der Code wächst schnell unlesbar.

### Problem 2: Zustand wird unübersichtlich

Sobald Agents Zwischenergebnisse voneinander brauchen (z. B. Image Agent soll
auf dem Text des Text-Agenten aufbauen), muss man das manuell durchreichen:

```python
def run_pipeline(task: str) -> dict:
    decision = manager_decision(task)
    text_result = ""
    image_prompt = task  # Fallback

    if decision["run_text"]:
        text_result = generate_text(task)
        image_prompt = extract_image_prompt(text_result)  # neuer Schritt!

    image_result = ""
    if decision["run_image"]:
        image_result = generate_image(image_prompt)  # jetzt abhängig vom Text

    # Was wenn in Zukunft ein dritter Agent auch etwas braucht?
    # Alle Abhängigkeiten müssen hier manuell verwaltet werden
    ...
```

Jede neue Abhängigkeit → die `run_pipeline`-Funktion wird länger und fragiler.

### Problem 3: Parallelisierung ist aufwändig

Wenn Text- und Image-Agent gleichzeitig laufen sollen (spart Zeit):

```python
import asyncio

async def run_pipeline_parallel(task: str) -> dict:
    decision = manager_decision(task)

    tasks_to_run = []
    if decision["run_text"]:
        tasks_to_run.append(generate_text_async(task))
    if decision["run_image"]:
        tasks_to_run.append(generate_image_async(task))

    # asyncio.gather für parallele Ausführung
    results = await asyncio.gather(*tasks_to_run, return_exceptions=True)

    # Ergebnisse manuell den richtigen Variablen zuordnen
    # PROBLEM: Reihenfolge der Ergebnisse hängt von tasks_to_run ab
    text_result = results[0] if decision["run_text"] else ""
    image_result = results[1 if decision["run_text"] else 0] if decision["run_image"] else ""
    # → fehleranfällig, schwer lesbar
```

### Problem 4: Einen neuen Agent hinzufügen

Man will einen dritten Agent: einen SEO-Agent, der Keywords analysiert.

```python
# Ohne Framework muss man run_pipeline() anfassen:
def run_pipeline(task: str) -> dict:
    decision = manager_decision(task)   # Manager-Prompt muss auch angepasst werden
    text_result = ""
    image_result = ""
    seo_result = ""                     # neu

    if decision["run_text"]:
        text_result = generate_text(task)
    if decision["run_image"]:
        image_result = generate_image(task)
    if decision["run_seo"]:             # neu
        seo_result = generate_seo(task) # neu

    return {
        "text": text_result,
        "image_url": image_result,
        "seo": seo_result              # neu
    }
```

Jede Erweiterung erfordert Änderungen an der zentralen `run_pipeline`-Funktion.
Das ist ein Zeichen für schlechte Architektur – die Funktion weiß zu viel.

### Problem 5: Kein Logging, kein Nachvollziehen

Wenn etwas schiefläuft, hat man keine Sichtbarkeit:
- Welcher Agent hat was bekommen?
- Was hat der Manager genau entschieden?
- Wie lange hat jeder Schritt gedauert?

Man müsste das alles manuell einbauen.

---

## Variante B: Mit LangGraph

Dieselbe Logik, aber als Graph:

```python
# graph.py – MIT LangGraph

from langgraph.graph import StateGraph, END
from agents.state import AgentState

graph = StateGraph(AgentState)

graph.add_node("manager",    manager_agent)
graph.add_node("text",       text_agent)
graph.add_node("image",      image_agent)
graph.add_node("aggregator", aggregator)

graph.set_entry_point("manager")

graph.add_conditional_edges("manager", routing_function, {
    "text_only":  "text",
    "image_only": "image",
    "both":       "text",
})

graph.add_edge("text",       "aggregator")
graph.add_edge("image",      "aggregator")
graph.add_edge("aggregator", END)

app = graph.compile()
```

Neuen SEO-Agent hinzufügen:

```python
graph.add_node("seo", seo_agent)          # eine Zeile
graph.add_edge("seo", "aggregator")       # eine Zeile
# routing_function anpassen: "seo" als Option hinzufügen
```

Die zentrale Pipeline-Funktion existiert nicht mehr – der Graph übernimmt das.

---

## Direkter Vergleich

| Aspekt | Ohne Framework | Mit LangGraph |
|---|---|---|
| **Einstieg** | Einfach, sofort verständlich | Etwas Lernaufwand (Graph-Konzept) |
| **Routing-Logik** | Manuelles if/else in einer Funktion | Declarative Edges im Graphen |
| **Gemeinsamer Zustand** | Variablen manuell weitergeben | `AgentState` automatisch durch alle Nodes |
| **Fehlerbehandlung** | Try/except überall | Zentral im Graph konfigurierbar |
| **Parallelisierung** | Manuell mit asyncio, fehleranfällig | `graph.add_node` parallel by default möglich |
| **Neuen Agent hinzufügen** | Zentrale Pipeline-Funktion anfassen | Node + Edge hinzufügen, Rest bleibt unberührt |
| **Logging / Tracing** | Manuell einbauen | LangSmith-Integration eingebaut |
| **Streaming** | Manuell mit asyncio + SSE | `graph.astream()` out of the box |
| **Lesbarkeit bei 3+ Agents** | Pipeline-Funktion wird lang und fragil | Graph-Definition bleibt kurz und deklarativ |
| **Testbarkeit** | Gesamte Pipeline testen | Jeden Node isoliert testen |

---

## Wann macht kein Framework Sinn?

- Nur ein einziger Agent, keine Verzweigungen
- Proof-of-Concept oder schnelles Prototyping
- Das Team kennt LangGraph nicht und die Zeit für Einarbeitung fehlt
- Die Anforderungen sind stabil und werden sich nicht ändern

## Wann macht LangGraph Sinn – wie in unserem Projekt?

- Mehrere Agents mit unterschiedlichen Aufgaben
- Routing-Entscheidung zur Laufzeit (Manager entscheidet)
- Agents sollen austauschbar und erweiterbar sein
- Man möchte später Streaming oder komplexere Flows hinzufügen
- Nachvollziehbarkeit (welcher Agent hat was getan) ist wichtig

---

## Fazit

Das "Ohne Framework"-Beispiel oben funktioniert – aber es ist eine
**versteckte Komplexität**. Die `run_pipeline`-Funktion ist der heimliche
Orchestrator, der alles weiß und alles zusammenhält.

LangGraph macht diese Orchestrierung **explizit und sichtbar**:
Der Graph ist die Dokumentation. Man sieht auf einen Blick, welche Agents
es gibt, in welcher Reihenfolge sie laufen und unter welchen Bedingungen.

> "Ohne Framework baust du unbewusst ein schlechteres LangGraph nach."
