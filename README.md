# RunLedger (FastAPI + PostgreSQL + Alembic + React/Vite)

RunLedger is a minimal end-to-end app to track AI run costs per customer. Backend is FastAPI with PostgreSQL and Alembic migrations; frontend is React + Vite; functional tests via Playwright.

## Features

- Backend (FastAPI)
  - Customers: create/list
  - Runs: start a run (Google provider), list runs per customer
  - Portia integration with safe fallback to Dummy client (uses only GOOGLE_API_KEY)
  - CORS enabled for local dev
- Database (PostgreSQL via Homebrew)
  - SQLAlchemy models: Customer, AgentRun, ToolCall, BillingEvent
  - Alembic migrations configured; initial baseline applied
- Frontend (React + Vite)
  - Add customer, list customers, start run, list runs for selected customer
  - Configurable API base with Vite env `VITE_API_URL`
- Functional tests (Playwright)
  - E2E test that adds a customer, starts a run, and verifies a run row appears

## Prerequisites

- macOS with Homebrew
- Python 3.11+ (project developed with 3.13 available)
- Node.js 18+ and npm
- PostgreSQL via Homebrew (e.g., `brew install postgresql@16` and `brew services start postgresql@16`)

## Environment

Create `.env` in repo root (already present) with at least:

```
GOOGLE_API_KEY=your_google_api_key
DATABASE_URL=postgresql+psycopg2:///<your_db_name>?host=/tmp (Homebrew socket)
```

Notes:
- The socket path `/tmp` is the default for Homebrew Postgres on mac. If your socket is elsewhere, adjust `host=` accordingly.
- No other LLM keys are required. The system uses only Google for Portia.

## Backend Setup

1) Create venv and install deps

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

2) Prepare database

- Ensure Postgres is running (`brew services list`)
- Create DB if missing (example):

```
createdb <your_db_name>
```

3) Apply Alembic migrations

```
alembic upgrade head
```

4) Run the API

```
uvicorn backend.main:app --reload --port 8000
```

API base: `http://127.0.0.1:8000`

## Frontend Setup

1) Install deps

```
cd frontend
npm install
```

2) Run dev server

```
# default API base is http://127.0.0.1:8000
npm run dev

# or override API base (example):
VITE_API_URL=http://127.0.0.1:8000 npm run dev
```

Frontend: `http://localhost:5173`

## Functional Tests (Playwright)

Prereqs: Backend on :8000 and Vite on :5173

Install browsers (first time only):

```
cd frontend
npm i -D @playwright/test
npx playwright install
```

Run tests:

```
# from frontend/
npm run test:e2e
# optional UI mode
npm run test:e2e:ui
```

What it does:
- Visits the app
- Adds a customer
- Selects it
- Starts a run (Google provider)
- Refreshes runs and checks a result row

## Common API Endpoints

- GET `/health` — health check
- Customers
  - POST `/customers/` — create customer
  - GET `/customers/` — list customers
- Runs
  - POST `/runs/start` — start a run for a customer (uses Google provider)
  - GET `/runs/by_customer/{customer_id}` — list runs

## Project Structure

```
backend/
  main.py              # FastAPI app setup and router registration
  models.py            # SQLAlchemy ORM models
  db_sa.py             # SQLAlchemy engine + session + Base
  routers/
    customers.py       # /customers endpoints
    runs.py            # /runs endpoints
  services/
    portia_factory.py  # Portia client (real or Dummy fallback)
    stripe_service.py  # (stub for future billing)

alembic/
  env.py               # Alembic config using Base.metadata
  versions/            # migration scripts (baseline included)

frontend/
  src/
    App.tsx           # UI for customers and runs
    main.tsx          # React entry
    styles.css        # simple styling
  tests/
    app.e2e.spec.ts   # Playwright functional test
  playwright.config.ts
```

## Migrations Workflow

- Autogenerate a migration (after model changes):

```
alembic revision --autogenerate -m "describe change"
```

- Review and apply:

```
alembic upgrade head
```

## Troubleshooting

- Postgres connection errors
  - Verify socket path in `DATABASE_URL` (Homebrew commonly `/tmp`)
  - Try TCP URL: `postgresql+psycopg2://user@localhost:5432/dbname`
- CORS issues in browser
  - Ensure FastAPI includes CORSMiddleware (already configured)
- Runs not appearing immediately
  - Click "Refresh Runs"; slight delay is expected while the run is recorded
- Alembic complains about heads or revisions
  - Ensure you’re on the latest baseline, or stamp the DB state: `alembic stamp head` then re-run upgrade

## Security / Keys

- Only `GOOGLE_API_KEY` is used for the Portia integration
- Do not commit `.env`

## Next Steps

- Rich run details (token counts, tool calls)
- Analytics dashboard (daily cost, per-customer/provider)
- Stripe billing flow (invoices, webhooks)
- Authentication and multi-tenant orgs
