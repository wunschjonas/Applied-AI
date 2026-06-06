# Backend Route Tests

Diese Datei beschreibt die wichtigsten manuellen API-Tests für das FastAPI-Backend.

Basis-URL:

```txt
http://localhost:8080
```

---

# 1. Health Check

## Request

**Methode:** `GET`

```txt
/health
```

## Erwartung

Status:

```txt
200 OK
```

Beispielantwort:

```json
{
  "status": "ok",
  "service": "applied-ai-marketing-agent",
  "version": "0.2.0"
}
```

---

# 2. Post erstellen

## Request

**Methode:** `POST`

```txt
/api/posts
```

## Body

```json
{
  "title": "Applied AI Marketing Agent",
  "topic": "LLM-basierte Marketing-Automatisierung",
  "platform": "linkedin",
  "target_audience": "Marketing Manager und Gründer",
  "tone_of_voice": "professionell und verständlich",
  "goal": "Interesse für KI-Agenten im Marketing wecken",
  "additional_context": "Semesterprojekt im Modul Applied AI an der HTWG Konstanz"
}
```

## Erwartung

Status:

```txt
201 Created
```

---

# 3. Alle Posts abrufen

## Request

**Methode:** `GET`

```txt
/api/posts
```

## Erwartung

Status:

```txt
200 OK
```

Antwort enthält eine Liste aller gespeicherten Posts.

---

# 4. Einzelnen Post abrufen

## Request

**Methode:** `GET`

```txt
/api/posts/{post_id}
```

Beispiel:

```txt
/api/posts/REPLACE_WITH_POST_ID
```

## Erwartung

Status:

```txt
200 OK
```

---

# 5. Post aktualisieren

## Request

**Methode:** `PUT`

```txt
/api/posts/{post_id}
```

## Beispiel Body

```json
{
  "tone_of_voice": "professionell, klar und motivierend",
  "goal": "Interesse für den Einsatz von KI-Agenten im Marketing wecken"
}
```

## Erwartung

Status:

```txt
200 OK
```

---

# 6. Preview generieren

## Request

**Methode:** `POST`

```txt
/api/posts/{post_id}/generate-preview
```

## Erwartung

Status:

```txt
200 OK
```

Der ManagerAgent erzeugt:

* generierten Social-Media-Post
* Poststruktur
* Hashtags
* Agent Trace
* Preview-Daten

---

# 7. Preview abrufen

## Request

**Methode:** `GET`

```txt
/api/posts/{post_id}/preview
```

## Erwartung

Status:

```txt
200 OK
```

---

# 8. Agent Trace abrufen

## Request

**Methode:** `GET`

```txt
/api/posts/{post_id}/agent-trace
```

## Erwartung

Status:

```txt
200 OK
```

Die Antwort zeigt die Agentenschritte.

Beispielstruktur:

```json
[
  {
    "timestamp": "...",
    "thought": "I need to understand the post briefing before writing content.",
    "action": "analyze_briefing",
    "observation": "The briefing is being analyzed."
  }
]
```

Dieser Endpoint dient als Nachweis für den TAO-Zyklus:

```txt
Thought → Action → Observation
```

---

# 9. Post löschen

## Request

**Methode:** `DELETE`

```txt
/api/posts/{post_id}
```

## Erwartung

Status:

```txt
204 No Content
```

---

# Empfohlene Test-Reihenfolge

1. `GET /health`
2. `POST /api/posts`
3. `GET /api/posts`
4. `GET /api/posts/{post_id}`
5. `POST /api/posts/{post_id}/generate-preview`
6. `GET /api/posts/{post_id}/preview`
7. `GET /api/posts/{post_id}/agent-trace`
8. Optional: `PUT /api/posts/{post_id}`
9. Optional: `DELETE /api/posts/{post_id}`

---

# HuggingFace Konfiguration

Für die Preview-Generierung muss eine `.env` Datei existieren:

```env
HF_TOKEN=hf_your_token_here
HF_MODEL_ID=Qwen/Qwen2.5-7B-Instruct
```

---

# Ziel dieses Backends

Das Backend dient als Grundlage für ein Applied-AI-Multi-Agent-System zur automatisierten Erstellung von Social-Media-Content.

Der aktuelle Fokus liegt auf:

* FastAPI Backend
* JSON-basierter Speicherung
* ManagerAgent
* LLM-basierter Preview-Generierung
* sichtbarem TAO-Zyklus
* nachvollziehbaren Agent-Traces

Spätere Erweiterungen:

* echte Multi-Agent-Kommunikation
* RAG
* Vision Agents
* Scheduling
* Social-Media-Publishing
* Engagement-Agenten
