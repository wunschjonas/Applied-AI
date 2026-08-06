# GitHub Actions – Backend CI

## Wann läuft der Workflow?

Der Workflow **Backend CI** (`.github/workflows/backend-ci.yml`) startet automatisch:

- bei jedem **Push** auf `main`, `development` oder Branches unter `feature/**`
- bei jedem **Pull Request** gegen `main` oder `development`

## Welche Tests werden ausgeführt?

Im Job wird aus dem Ordner `backend/` Folgendes ausgeführt:

```bash
python -m pytest "tests/W8 Tests/" -q
```

Damit laufen alle Tests unter [`backend/tests/W8 Tests/`](../tests/W8%20Tests/).  
Schlägt ein Test fehl, schlägt der gesamte Workflow fehl.

Zusätzlich prüft CI:

1. dass die FastAPI-App importierbar ist (`from app.main import app`)
2. dass das Backend-Docker-Image gebaut werden kann (`docker build` mit dem Backend-`Dockerfile`)

## Warum ist HuggingFace gemockt?

Die W8-Tests nutzen lokale Fakes (z. B. `FakeHF`) und rufen die HuggingFace-API nicht echt auf.  
In CI werden nur **Platzhalter**-Umgebungsvariablen gesetzt (`HF_TOKEN`, `HF_MODEL_ID`, `HF_IMAGE_MODEL_ID`, `MCP_MEMORY_URL`), damit die Settings laden, ohne Secrets oder Netzwerkanrufe zu HuggingFace/MCP zu brauchen.

Echte HF-Tokens gehören **nicht** in diesen CI-Workflow.

## Wo sieht man den Workflow auf GitHub?

1. Repository auf GitHub öffnen  
2. Tab **Actions**  
3. Links den Workflow **Backend CI** wählen  
4. Einzelne Runs und Logs der Steps (pytest, Import, Docker-Build) einsehen  
