# Applied-AI

## Projekt: Intelligenter Marketing-Agent mit Docker-Containerisierung

Dieses Projekt verwendet:
- Backend: `FastAPI` API in `backend/app.py` (Port 8080)
- Frontend: `Angular` App in `frontend/` (Port 4200)
- Containerisierung: `Docker` + `docker-compose`

## Lokaler Start (Docker)

1. Docker & Docker Compose installieren
2. Root im Projektordner öffnen
3. Build & Start:

```bash
docker compose up --build
```

## Lokaler Start (Entwicklung)

Backend:
```bash
cd backend
pip install -r requirements.txt
python app.py
```

Frontend:
```bash
cd frontend
npm install
npm start
```

4. Frontend im Browser:
- `http://localhost:4200`

Backend API:
- `http://localhost:8080/api`

## Alternative: Backend einzeln

```bash
cd backend
pip install -r requirements.txt
python app.py
```

## Alternative: Frontend einzeln

```bash
cd frontend
npm install
npm start
```

## Dokumentation

Weitere Projekt-Dokumentation (Architektur, Audits, Walkthroughs, Zusammenfassungen) liegt unter [`docs/`](docs/).
