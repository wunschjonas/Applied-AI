# Logging – Wie Logs pro Agent aussehen und im Frontend angezeigt werden

## Ziel

Jeder Agent schreibt strukturierte Log-Einträge in den gemeinsamen `AgentState`.
Das Frontend kann diese Logs über einen eigenen Endpunkt abrufen und anzeigen –
entweder nach Abschluss oder live per Streaming.

---

## 1. Log-Eintrag – Datenstruktur

Jeder einzelne Log-Eintrag ist ein Dict mit festen Feldern:

```python
{
    "timestamp": "2026-06-08T14:32:01.123Z",  # ISO-Zeit
    "agent":     "manager_agent",              # Wer hat geloggt?
    "level":     "INFO",                       # INFO | WARNING | ERROR
    "event":     "decision_made",              # Maschinenlesbares Ereignis
    "message":   "Entscheidung: Text + Bild",  # Für Menschen lesbarer Text
    "data":      {                             # Optionale Zusatzdaten
        "run_text": True,
        "run_image": True
    }
}
```

---

## 2. Logs im AgentState

Die Logs leben direkt im State – so hat jeder Agent Zugriff darauf und kann anhängen:

```python
# agents/state.py

from typing import TypedDict

class AgentState(TypedDict):
    task:         str
    run_text:     bool
    run_image:    bool
    text_result:  str
    image_result: str
    final_output: dict
    error:        str
    logs:         list[dict]   # ← alle Log-Einträge aller Agents
```

---

## 3. Log-Einträge pro Agent

### Manager Agent

Der Manager loggt: was er bekommen hat, welche Entscheidung er getroffen hat.

```
[14:32:00.001] [manager_agent] [INFO]  task_received
               "Task empfangen"
               data: { task: "Post für SolarX erstellen" }

[14:32:00.850] [manager_agent] [INFO]  llm_call_start
               "LLM-Aufruf gestartet (Routing-Entscheidung)"

[14:32:01.723] [manager_agent] [INFO]  decision_made
               "Entscheidung: Text + Bild werden generiert"
               data: { run_text: true, run_image: true }
```

### Text Agent

Der Text Agent loggt: Start, wie lang der LLM-Aufruf dauert, Ergebnis-Länge.

```
[14:32:01.730] [text_agent]    [INFO]  generation_start
               "Textgenerierung gestartet"
               data: { model: "gpt-4o" }

[14:32:03.412] [text_agent]    [INFO]  generation_complete
               "Text erfolgreich generiert"
               data: { characters: 312, duration_ms: 1682 }
```

### Image Agent

Der Image Agent loggt: generierten DALL-E-Prompt, Bild-Dimensionen, URL.

```
[14:32:01.731] [image_agent]   [INFO]  prompt_generation_start
               "DALL-E Prompt wird aus Task abgeleitet"

[14:32:02.190] [image_agent]   [INFO]  dalle_prompt_ready
               "DALL-E Prompt erstellt"
               data: { prompt: "Futuristic solar panel on rooftop, sunset..." }

[14:32:02.195] [image_agent]   [INFO]  image_generation_start
               "Bildgenerierung mit DALL-E 3 gestartet"
               data: { model: "dall-e-3", size: "1024x1024" }

[14:32:07.880] [image_agent]   [INFO]  image_generation_complete
               "Bild erfolgreich generiert"
               data: { image_url: "https://oaidalleapi...", duration_ms: 5685 }
```

### Aggregator

```
[14:32:07.885] [aggregator]    [INFO]  aggregation_start
               "Ergebnisse werden zusammengeführt"
               data: { has_text: true, has_image: true }

[14:32:07.886] [aggregator]    [INFO]  aggregation_complete
               "final_output erstellt"
```

### Fehlerfall

Wenn ein Agent scheitert, schreibt er einen ERROR-Log – der Graph kann dann
zu einem Error-Handler-Node routen:

```
[14:32:05.001] [image_agent]   [ERROR] image_generation_failed
               "DALL-E API hat nicht geantwortet"
               data: { error: "APITimeoutError", retries: 0 }
```

---

## 4. Wie ein Agent einen Log-Eintrag schreibt

```python
# agents/logger.py – Hilfsfunktion

from datetime import datetime, timezone

def make_log(agent: str, level: str, event: str, message: str, data: dict = None) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent":     agent,
        "level":     level,
        "event":     event,
        "message":   message,
        "data":      data or {}
    }
```

Verwendung in einem Node:

```python
# agents/text_agent.py

from agents.logger import make_log

def text_agent(state: AgentState) -> dict:
    logs = list(state.get("logs", []))

    logs.append(make_log(
        agent="text_agent",
        level="INFO",
        event="generation_start",
        message="Textgenerierung gestartet",
        data={"model": "gpt-4o"}
    ))

    # ... GPT-4o Aufruf ...
    result = llm.invoke(...)

    logs.append(make_log(
        agent="text_agent",
        level="INFO",
        event="generation_complete",
        message="Text erfolgreich generiert",
        data={"characters": len(result.content)}
    ))

    return {
        "text_result": result.content,
        "logs": logs          # komplette Liste zurückgeben (LangGraph merged)
    }
```

---

## 5. Endpunkt – Logs abrufen

### Variante A: Logs kommen mit der Antwort zurück

Einfachste Variante: Die Logs sind Teil der `/api/agent/run`-Response.

```python
# backend/app.py

@app.post("/api/agent/run")
async def run_agent(request: AgentRequest):
    result = agent_graph.invoke({"task": request.task, "logs": []})
    return {
        **result["final_output"],
        "logs": result["logs"]        # ← Logs direkt in der Response
    }
```

**Response:**
```json
{
  "text": "☀️ Entdecke SolarX...",
  "image_url": "https://...",
  "logs": [
    {
      "timestamp": "2026-06-08T14:32:00.001Z",
      "agent": "manager_agent",
      "level": "INFO",
      "event": "task_received",
      "message": "Task empfangen",
      "data": { "task": "Post für SolarX erstellen" }
    },
    {
      "timestamp": "2026-06-08T14:32:01.723Z",
      "agent": "manager_agent",
      "level": "INFO",
      "event": "decision_made",
      "message": "Entscheidung: Text + Bild werden generiert",
      "data": { "run_text": true, "run_image": true }
    }
  ]
}
```

### Variante B: Live-Logs per Streaming (SSE)

Logs erscheinen im Frontend in Echtzeit, während die Agents noch laufen.
Das Frontend abonniert den SSE-Stream – jedes Mal wenn ein Node fertig ist,
schickt FastAPI die neuen Log-Einträge.

```
Frontend                         FastAPI + LangGraph
   │                                    │
   │── POST /api/agent/stream ─────────►│
   │                                    │
   │◄── data: {"agent":"manager",...} ──│  ← Manager fertig
   │◄── data: {"agent":"text_agent",...}│  ← Text Agent fertig
   │◄── data: {"agent":"image_agent",...│  ← Image Agent fertig
   │◄── data: {"event":"done"} ─────────│  ← Graph fertig
```

---

## 6. Darstellung im Angular-Frontend

### Log-Eintrag als Komponente

Jeder Log-Eintrag wird als Zeile angezeigt, farblich nach Level und Agent:

```
┌────────────────────────────────────────────────────────────────┐
│  Agent Run – "Post für SolarX erstellen"                       │
├────────────────────────────────────────────────────────────────┤
│  14:32:00  🔵 manager_agent    Task empfangen                  │
│  14:32:01  🔵 manager_agent    Entscheidung: Text + Bild       │
│  14:32:01  🟢 text_agent       Textgenerierung gestartet       │
│  14:32:01  🟡 image_agent      DALL-E Prompt wird erstellt     │
│  14:32:02  🟡 image_agent      Bildgenerierung gestartet       │
│  14:32:03  🟢 text_agent  ✓   Text generiert (312 Zeichen)    │
│  14:32:07  🟡 image_agent  ✓  Bild generiert                  │
│  14:32:07  ⚪ aggregator   ✓  Ergebnisse zusammengeführt      │
└────────────────────────────────────────────────────────────────┘
```

Farbschema:
- 🔵 Blau   → `manager_agent`
- 🟢 Grün   → `text_agent`
- 🟡 Gelb   → `image_agent`
- ⚪ Grau   → `aggregator`
- 🔴 Rot    → Level `ERROR`

### TypeScript-Interface dazu

```typescript
// frontend/src/app/models/log-entry.model.ts

export interface LogEntry {
  timestamp: string;
  agent:     'manager_agent' | 'text_agent' | 'image_agent' | 'aggregator';
  level:     'INFO' | 'WARNING' | 'ERROR';
  event:     string;
  message:   string;
  data:      Record<string, unknown>;
}

export interface AgentResponse {
  text:      string;
  image_url: string;
  logs:      LogEntry[];
}
```

---

## 7. Zusammenfassung – Datenfluss der Logs

```
1. graph.invoke() wird mit logs=[] gestartet

2. manager_node läuft:
   → hängt 3 Log-Einträge an logs[] an
   → gibt { ..., logs: [log1, log2, log3] } zurück

3. text_node läuft:
   → liest logs aus State (hat jetzt 3 Einträge)
   → hängt 2 eigene Einträge an
   → gibt { ..., logs: [log1, log2, log3, log4, log5] } zurück

4. image_node läuft (parallel oder danach):
   → hängt weitere Einträge an
   → ...

5. aggregator_node läuft:
   → letzte Einträge werden hinzugefügt
   → logs[] hat jetzt alle Einträge aller Agents

6. graph.invoke() gibt State zurück
   → result["logs"] = vollständige Log-Liste

7. FastAPI schickt logs als Teil der HTTP-Response
   → Angular empfängt und rendert die Log-Liste
```
