# Agent Memory Layer — Konzept & Erklärung

## Was bauen wir hier?

Wir erweitern unser bestehendes Agentensystem (Backend + Frontend) um einen **semantischen Gedächtnisspeicher**.
Die Agenten (TextAgent, ImageAgent) können dadurch auf gespeicherte Informationen zugreifen und diese
als Kontext in ihre Antworten einbeziehen — ähnlich wie ein Mensch, der sich an frühere Gespräche erinnert.

---

## Wo läuft was?

```
docker-compose.yml startet 3 Container:
┌─────────────────────────────────────────────────────────┐
│                    Docker Compose                       │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────────┐  │
│  │  frontend   │  │   backend   │  │    memory      │  │
│  │ Angular     │  │ FastAPI     │  │ MCP Memory     │  │
│  │ :4200       │  │ :8080       │  │ Service :8765  │  │
│  └─────────────┘  └──────┬──────┘  └────────┬───────┘  │
│                          │    MCP über HTTP  │          │
│                          └───────────────────┘          │
└─────────────────────────────────────────────────────────┘
```

**Der Memory Service ist ein völlig eigenständiger Container.**
Er gehört nicht zum Python-Code des Backends. Er läuft auf Port 8765 und
kommuniziert über ein standardisiertes Protokoll namens **MCP** (Model Context Protocol).

Das Backend spricht über HTTP mit ihm — genauso wie es mit einer Datenbank über SQL spräche,
nur eben über HTTP/MCP statt über eine Datenbankverbindung.

---

## Was ist der MCP Memory Service?

Das ist ein fertiges Open-Source-Projekt (`doobidoo/mcp-memory-service`), das wir als Docker-Image
direkt verwenden. Es stellt uns automatisch folgende Funktionen bereit:

| Funktion          | Was es tut                                              |
|-------------------|---------------------------------------------------------|
| `memory_store`    | Einen Text/Fakt speichern (mit semantischer Einbettung) |
| `memory_search`   | Semantisch ähnliche Einträge finden                     |
| `memory_list`     | Alle gespeicherten Einträge auflisten                   |
| `memory_delete`   | Einen Eintrag löschen                                   |

**Technisch dahinter:** Der Service wandelt jeden gespeicherten Text in einen Zahlenvektor um
(sog. *Embedding* mit dem Modell `all-MiniLM-L6-v2`). Bei einer Suche wird die Anfrage
ebenfalls in einen Vektor umgewandelt und mathematisch verglichen — das nennt sich
**semantische Ähnlichkeitssuche** (Vektorsuche). Texte mit ähnlicher *Bedeutung* werden
gefunden, nicht nur solche mit identischen Wörtern.

Die Daten werden in einer SQLite-Datenbank mit Vektorerweiterung (`sqlite_vec`) gespeichert,
die in einem Docker Volume (`memory_data`) persistiert — d.h. die Inhalte bleiben auch nach
einem Container-Neustart erhalten.

---

## Was ist MCP (Model Context Protocol)?

MCP ist ein offenes Protokoll von Anthropic, das standardisiert, wie KI-Agenten auf externe
Werkzeuge und Datenquellen zugreifen. Stell es dir wie eine einheitliche "Steckdose" vor:
Jeder MCP-Server stellt Werkzeuge (Tools) bereit, jeder MCP-Client kann sie nutzen —
unabhängig davon, welches Agenten-Framework man verwendet.

```
Backend (Client)  ──MCP über HTTP──►  Memory Service (Server)
   "Suche nach: Zielgruppe"               führt memory_search aus
                  ◄──────────────────   gibt 3 ähnliche Einträge zurück
```

---

## Wie ändert sich der Ablauf im Backend?

### Vorher (aktueller Stand):
```
User-Nachricht
  → ManagerChatGraph
  → rag_decision_node  (Keyword-Check: enthält Nachricht "pdf"/"dokument"?)
  → rag_retrieval_node (gibt nur "not implemented" zurück)
  → TextAgent/ImageAgent (ohne Kontext aus Memory)
```

### Nachher (mit Memory Layer):
```
User-Nachricht
  → ManagerChatGraph
  → rag_decision_node  (semantische Relevanz-Entscheidung)
  → rag_retrieval_node (echte MCP-Suche im Memory Service)
  → TextAgent/ImageAgent (MIT rag_context aus dem Speicher)
```

**Beispiel:**
1. Nutzer hat früher gespeichert: *"Unsere Zielgruppe sind junge Fachkräfte zwischen 25 und 35."*
2. Nutzer fragt jetzt: *"Erstelle einen LinkedIn-Post für unser neues Produkt."*
3. Der `rag_retrieval_node` sucht im Memory nach relevanten Einträgen.
4. Er findet den Zielgruppen-Eintrag und gibt ihn als `rag_context` weiter.
5. Der TextAgent bekommt diesen Kontext und berücksichtigt ihn im Prompt:
   ```
   Memory context: Unsere Zielgruppe sind junge Fachkräfte zwischen 25 und 35.
   ```
6. Der generierte Post passt automatisch zur Zielgruppe — ohne dass der Nutzer sie
   nochmal erwähnen musste.

---

## Was wird konkret implementiert?

### 1. Infrastruktur (`docker-compose.yml`)
Den `memory`-Container als dritten Service hinzufügen. Er startet automatisch mit
`docker compose up`.

### 2. Backend — RAGService (`backend/app/services/rag_service.py`)
Den bisherigen Platzhalter durch echte Aufrufe an den Memory Service ersetzen:
- `retrieve(query)` → ruft `memory_search` via MCP auf
- `store(content, tags)` → ruft `memory_store` via MCP auf

Das Python-Paket `mcp` stellt dafür den Client bereit.

### 3. Backend — LangGraph-Graph (`manager_chat_graph.py`)
Den `rag_context` (die gefundenen Erinnerungen) an die Agenten weiterreichen.
Aktuell wird er zwar abgerufen, aber den Agenten nie übergeben.

### 4. Backend — TextAgent & ImageAgent
`rag_context` als Parameter aufnehmen und in den LLM-Prompt einbauen,
damit das Sprachmodell den Kontext beim Generieren berücksichtigt.

### 5. Backend — neue API-Endpunkte (`/api/memory/`)
Damit auch das Frontend (und Nutzer direkt) den Memory verwalten können:
- `POST /api/memory/store` — Fakt speichern
- `GET /api/memory/search?q=...` — Semantisch suchen
- `GET /api/memory/list` — Alle Einträge anzeigen

### 6. Frontend — RAG-Seite (`/rag`)
Die Seite existiert schon, ist aber leer. Sie bekommt:
- Ein Formular zum Speichern von Fakten/Kontext
- Eine Suche mit Ergebnisliste
- Eine Übersicht aller gespeicherten Memories

---

## Was brauche ich, um das lokal zu starten?

```powershell
# Einmalig: Memory Container hochfahren (ohne docker compose)
docker run -d --name memory -p 8765:8765 `
  -v memory_data:/app/sqlite_db `
  -e MCP_MODE=streamable-http `
  -e MCP_SSE_HOST=0.0.0.0 -e MCP_SSE_PORT=8765 `
  -e MCP_ALLOW_ANONYMOUS_ACCESS=true `
  -e MCP_MEMORY_STORAGE_BACKEND=sqlite_vec `
  -e MCP_MEMORY_SQLITE_PATH=/app/sqlite_db/memory.db `
  doobidoo/mcp-memory-service:latest

# Oder: Alles zusammen mit docker compose
docker compose up
```

Der Memory Service ist dann erreichbar unter: `http://localhost:8765/mcp`

---

## Zusammenfassung

| Frage                                        | Antwort                                                  |
|----------------------------------------------|----------------------------------------------------------|
| Läuft Memory Service im Backend-Ordner?      | Nein — eigener Docker-Container                          |
| Müssen wir den Memory Service selbst bauen?  | Nein — fertiges Docker-Image von doobidoo               |
| Wie kommuniziert das Backend damit?          | HTTP über das MCP-Protokoll (Python-Paket `mcp`)        |
| Wo werden die Daten gespeichert?             | Docker Volume `memory_data` (SQLite + Vektoren)         |
| Bleibt der Inhalt nach Neustart erhalten?    | Ja, dank persistentem Docker Volume                     |
| Was ändert sich am bestehenden Backend-Code? | RAGService, Graph-Nodes, TextAgent, ImageAgent, neue API |
