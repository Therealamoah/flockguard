# FlockGuard AI

AI-native poultry intelligence and early-warning platform. *"Know before it becomes a problem."*

FlockGuard is an early-warning and decision-support tool for poultry farmers — it is **not** a disease-diagnosis system.

## Monorepo layout

```
flockguard/
├── frontend/   React + Vite + Tailwind CSS (yarn) — the FlockGuard PWA
├── backend/    Python + FastAPI — REST API, Risk Engine, Grok/Cloudinary integration
├── CHECKLIST.md  Build checklist, updated as work lands
└── README.md
```

## Frontend

```bash
cd frontend
yarn install
cp .env.example .env   # fill in Firebase + API config
yarn dev
```

Stack: React, Vite, Tailwind CSS, React Router, Zustand, Recharts, custom SVG AI Health Radar, Firebase Authentication, PWA (vite-plugin-pwa).

## Backend

```bash
cd backend
python -m venv .venv
./.venv/Scripts/activate   # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cp .env.example .env       # fill in Firebase, Cloudinary, Grok config
uvicorn app.main:app --reload
```

Stack: FastAPI, Firebase Admin (token verification), Cloud Firestore, Cloudinary, Grok API. The Grok API key lives only on the backend — never in the frontend.

### Architecture

```
Farmer records Flock Check → FastAPI validates → historical baseline retrieved
→ Risk Engine (deterministic, Python) scores 0–100 → Alert Engine → Grok explains → Farmer inspects
```

The Risk Engine is plain Python and deterministic — Grok explains scores, it never invents them.

## Build process

We build FlockGuard against [CHECKLIST.md](CHECKLIST.md), phase by phase. See that file for current status.
