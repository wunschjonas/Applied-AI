# TODO — Nächste Schritte

> Stand: 12.06.2026 — Session beendet

---

## Sofort zu erledigen (kleiner Bug)

- [x] `routes_posts.py`: `/agent-trace`-Endpunkt entfernt ✅

---

## Social Media Agent Flow

Alle 8 Schritte noch offen. Reihenfolge einhalten.

### Schritt 1 — Chat-Schemas erweitern
**Datei:** `backend/app/schemas/chat.py`

`TextAgentChatRequest` und `ImageAgentChatRequest` bekommen je ein optionales Feld:
```python
previous_text: str | None = None          # für TextAgent
previous_image_prompt: str | None = None  # für ImageAgent
```

---

### Schritt 2 — Sub-Agent-Chat mit Kontext
**Datei:** `backend/app/services/agent_service.py`

`text_agent_chat()` und `image_agent_chat()` bauen `previous_artifact` in den System-Prompt ein:
```python
if previous_text:
    system_prompt += f"\n\nDer zuvor generierte Text lautet:\n{previous_text}\nVerfeinere ihn gemäß der Nutzereingabe."
```

---

### Schritt 3 — ArtifactFacade erstellen
**Neue Datei:** `frontend/src/app/facades/artifact.facade.ts`

```typescript
@Injectable({ providedIn: 'root' })
export class ArtifactFacade {
  generatedText        = signal<string | null>(null)
  generatedHashtags    = signal<string[]>([])
  generatedImagePrompt = signal<string | null>(null)
}
```

---

### Schritt 4 — Home befüllt ArtifactFacade
**Datei:** `frontend/src/app/pages/home/home.component.ts`

Nach Manager-Antwort: `generated_artifacts.text` und `generated_artifacts.image` in Facade schreiben.

---

### Schritt 5 — Preview-Seite
**Dateien:** `frontend/src/app/pages/preview/preview.component.*`

- Links: Marketing-Text + Hashtags
- Rechts: Image Prompt (copy-paste-fähig)
- Liest alles aus ArtifactFacade

---

### Schritt 6 — TextAgent-Seite mit Kontext
**Datei:** `frontend/src/app/pages/text-agent/text-agent.component.*`

- Info-Box: zeigt aktuell generierten Text aus Facade
- Sendet `previous_text` mit jedem Chat-Request
- Aktualisiert Facade nach Verfeinerungs-Antwort

---

### Schritt 7 — ImageAgent-Seite mit Kontext
**Datei:** `frontend/src/app/pages/image-agent/image-agent.component.*`

Identisch zu Schritt 6, aber für `previous_image_prompt`.

---

### Schritt 8 — Manager stellt Kontext-Fragen (LangGraph)
**Datei:** `backend/app/graphs/manager_chat_graph.py`

Neuer Node `context_question_node`: wenn Intent erkannt aber Plattform/Ton/Audience fehlt → gezielte Frage:
```
"Bevor ich starte:
- Plattform: LinkedIn, Instagram, X oder Blog?
- Tonalität: professionell, locker oder humorvoll?
- Zielgruppe?"
```

---

## Sonstiges (keine Priorität)

- Frontend: `PostInitResponse` hat kein `created_at` mehr → prüfen ob die Home-Seite das irgendwo anzeigt
- `agent_logs.json` Mock-Daten wurden geleert — beim nächsten Backend-Start entstehen echte Logs
- Memory Layer testen: Fakt speichern → Agent-Request mit RAG-Keyword → prüfen ob Memory-Kontext im Prompt landet
