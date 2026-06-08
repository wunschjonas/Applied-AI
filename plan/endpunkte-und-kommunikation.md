# Endpunkte & Kommunikation – Frontend ↔ Backend ↔ Agents

## Übersicht

Das Angular-Frontend kommuniziert ausschließlich über **HTTP mit FastAPI**.
FastAPI leitet die Anfragen intern an den LangGraph-Graphen weiter.
Der Graph entscheidet dann, welche Agents laufen.

```
Angular (Port 4200)
    │
    │  HTTP POST  (JSON Body)
    ▼
FastAPI (Port 8080)
    │
    │  graph.invoke() / agent_function()
    ▼
LangGraph
    ├── Manager Agent
    ├── Text Agent
    └── Image Agent
```

---

## Geplante Endpunkte

### Endpunkt 1 – Manager Agent (orchestriert alles)

```
POST /api/agent/run
```

Das Frontend gibt nur den Task an – der Manager entscheidet selbst,
ob Text, Bild oder beides generiert wird.

**Request (Angular → FastAPI):**
```json
{
  "task": "Erstelle einen Instagram-Post für unser neues Produkt SolarX"
}
```

**Response (FastAPI → Angular):**
```json
{
  "text": "☀️ Stell dir vor, nie wieder eine Stromrechnung zu zahlen...",
  "image_url": "https://oaidalleapi.blob.core.windows.net/...",
  "ran_text_agent": true,
  "ran_image_agent": true
}
```

**Was intern passiert:**
```
FastAPI empfängt Request
    │
    ▼
graph.invoke({ "task": "..." })
    │
    ▼
manager_node → entscheidet: run_text=True, run_image=True
    │
    ▼
text_node → generiert Text  →  image_node → generiert Bild
    │
    ▼
aggregator_node → { text: "...", image_url: "..." }
    │
    ▼
FastAPI gibt final_output als JSON zurück
```

---

### Endpunkt 2 – Text Agent direkt ansprechen

```
POST /api/agent/text
```

Das Frontend ruft den Text-Agenten direkt auf, ohne den Manager-Umweg.
Nützlich wenn das Frontend selbst entscheidet, dass nur Text gebraucht wird
(z. B. Caption-Generator, Blog-Intro, Produktbeschreibung).

**Request:**
```json
{
  "task": "Schreibe eine kurze Produktbeschreibung für SolarX"
}
```

**Response:**
```json
{
  "text": "SolarX ist das revolutionäre Solarpanel für Privathaushalte..."
}
```

**Was intern passiert:**
```
FastAPI empfängt Request
    │
    ▼
text_agent({"task": "..."})  ← direkt aufgerufen, kein Graph
    │
    ▼
gibt {"text_result": "..."} zurück
    │
    ▼
FastAPI verpackt es als {"text": "..."}
```

---

### Endpunkt 3 – Image Agent direkt ansprechen

```
POST /api/agent/image
```

Das Frontend ruft den Image-Agenten direkt auf.
Nützlich für reine Bildgenerierung (z. B. Thumbnail, Banner, Produktbild).

**Request:**
```json
{
  "task": "Erstelle ein futuristisches Bild eines Solarpanels auf einem Hausdach"
}
```

**Response:**
```json
{
  "image_url": "https://oaidalleapi.blob.core.windows.net/..."
}
```

**Was intern passiert:**
```
FastAPI empfängt Request
    │
    ▼
image_agent({"task": "..."})  ← direkt aufgerufen, kein Graph
    │
    ▼
gibt {"image_result": "https://..."} zurück
    │
    ▼
FastAPI verpackt es als {"image_url": "..."}
```

---

## Alle Endpunkte im Überblick

| Methode | Endpunkt | Aufruft | Wann nutzen |
|---|---|---|---|
| `POST` | `/api/agent/run` | Manager → Graph (beide Agents) | Frontend will alles auf einmal |
| `POST` | `/api/agent/text` | Text Agent direkt | Nur Text gewünscht |
| `POST` | `/api/agent/image` | Image Agent direkt | Nur Bild gewünscht |

---

## Wie Angular die Endpunkte aufruft

### Service-Klasse im Frontend (Angular)

Anstatt HTTP-Calls direkt in der Komponente zu machen (wie aktuell in `app.ts`),
wird ein dedizierter **Angular Service** erstellt:

```typescript
// frontend/src/app/agent.service.ts

@Injectable({ providedIn: 'root' })
export class AgentService {
  private baseUrl = 'http://localhost:8080';

  constructor(private http: HttpClient) {}

  // Manager Agent – Text + Bild
  runAgent(task: string): Observable<AgentResponse> {
    return this.http.post<AgentResponse>(`${this.baseUrl}/api/agent/run`, { task });
  }

  // Nur Text
  generateText(task: string): Observable<TextResponse> {
    return this.http.post<TextResponse>(`${this.baseUrl}/api/agent/text`, { task });
  }

  // Nur Bild
  generateImage(task: string): Observable<ImageResponse> {
    return this.http.post<ImageResponse>(`${this.baseUrl}/api/agent/image`, { task });
  }
}
```

### Verwendung in einer Komponente

```typescript
// Aufruf des Manager Agents aus einer Komponente
this.agentService.runAgent("Post für SolarX erstellen").subscribe({
  next: (result) => {
    this.generatedText.set(result.text);
    this.generatedImageUrl.set(result.image_url);
  },
  error: (err) => this.errorMessage.set('Agent-Fehler')
});
```

---

## Wie FastAPI die Endpunkte implementiert

```python
# backend/app.py (Erweiterung)

from fastapi import FastAPI
from pydantic import BaseModel
from agents.graph import app as agent_graph
from agents.text_agent import text_agent
from agents.image_agent import image_agent

# Request-Modelle (Pydantic validiert den JSON-Body automatisch)
class AgentRequest(BaseModel):
    task: str

# Endpunkt 1: Manager Agent
@app.post("/api/agent/run")
async def run_agent(request: AgentRequest):
    result = agent_graph.invoke({"task": request.task})
    return result["final_output"]

# Endpunkt 2: Text Agent direkt
@app.post("/api/agent/text")
async def run_text_agent(request: AgentRequest):
    result = text_agent({"task": request.task})
    return {"text": result["text_result"]}

# Endpunkt 3: Image Agent direkt
@app.post("/api/agent/image")
async def run_image_agent(request: AgentRequest):
    result = image_agent({"task": request.task})
    return {"image_url": result["image_result"]}
```

**Warum Pydantic `BaseModel`?**
FastAPI validiert den eingehenden JSON-Body automatisch anhand des Modells.
Wenn das Frontend ein leeres `task`-Feld schickt, antwortet FastAPI direkt mit
einem `422 Unprocessable Entity` – kein extra Validierungscode nötig.

---

## Fehlerfälle & HTTP-Statuscodes

| Situation | HTTP-Status | Response-Body |
|---|---|---|
| Erfolg | `200 OK` | `{ text: "...", image_url: "..." }` |
| Fehlender `task` im Body | `422 Unprocessable Entity` | FastAPI-Validierungsfehler |
| OpenAI API nicht erreichbar | `503 Service Unavailable` | `{ detail: "OpenAI nicht erreichbar" }` |
| Ungültiger API-Key | `401 Unauthorized` | `{ detail: "API-Key ungültig" }` |
| Interner Fehler im Graphen | `500 Internal Server Error` | `{ detail: "Agent-Fehler" }` |

---

## Datenfluss komplett (von Klick bis Antwort)

```
1. User tippt Task ins Angular-Formular und klickt "Generieren"

2. Angular Component ruft AgentService.runAgent(task) auf

3. HttpClient schickt:
   POST http://localhost:8080/api/agent/run
   Content-Type: application/json
   Body: { "task": "Post für SolarX" }

4. FastAPI empfängt Request → Pydantic validiert Body → ruft graph.invoke() auf

5. LangGraph-Graph läuft durch:
   manager_node → text_node → image_node → aggregator_node

6. graph.invoke() gibt finalen State zurück

7. FastAPI extrahiert final_output und sendet:
   HTTP 200 OK
   Content-Type: application/json
   Body: { "text": "...", "image_url": "..." }

8. Angular empfängt Response → Component aktualisiert die Signals

9. Angular rendert Text und Bild in der UI
```

---

## Swagger UI – kostenlos mitgeliefert

FastAPI generiert automatisch eine interaktive API-Dokumentation:

```
http://localhost:8080/docs
```

Dort kann man alle Endpunkte direkt im Browser testen – ohne Angular oder Postman.
Ideal zum Entwickeln und Debuggen der Agents.
