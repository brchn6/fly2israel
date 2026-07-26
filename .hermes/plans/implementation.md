# ✈️ fly2israel — Implementation Plan

> **Goal:** A clean, Data-Scientist-style dashboard + API showing which airlines fly to/from Israel and the status of their routes (active/suspended/seasonal).

> **Architecture:** Data collector on head1 → SQLite (source of truth) → static JSON files → Cloudflare Pages dashboard. Simple, zero-cost, self-hosted.

> **Tech Stack:** Python 3.12, SQLite, FastAPI (dev only), vanilla JS/HTML dashboard, Cloudflare Pages.

---

## Phase 1: Foundation (this session)

### Task 1: Project scaffold + Python setup
- Create `.venv`, `requirements.txt`, `.env.example`
- `requirements.txt`: fastapi, uvicorn, pyyaml, httpx, python-dotenv
- First commit

### Task 2: SQLite data model + seed loader
- `scripts/init_db.py` — creates tables from AGENTS.md schema
- `scripts/seed.py` — loads `data/airlines.yaml` into SQLite
- `scripts/collect.py` — stub for future API collection
- Idempotent (safe to re-run)

### Task 3: Status lookup API (FastAPI)
- `api/main.py` — FastAPI app with endpoints:
  - `GET /api/airlines` — all airlines with route counts
  - `GET /api/airlines/{iata}` — single airline + routes
  - `GET /api/routes?status=active|suspended` — filterable
  - `GET /api/stats` — summary statistics
- `api/db.py` — SQLite wrapper

### Task 4: Static data builder
- `scripts/build_data.py` — reads SQLite → writes `frontend/data.json`
- This is what Cloudflare Pages will serve (static JSON)

### Task 5: Minimal frontend
- `frontend/index.html` — standalone SPA
- Clean Data-Scientist-style: table, status badges, counters
- Dark/light theme, responsive
- No frameworks — vanilla JS, CSS Grid

### Task 6: Git + GitHub setup
- First commit with all files
- Push to GitHub (user's account: brchn6?)

### Task 7: Cloudflare Pages deploy
- Connect GitHub repo → Cloudflare Pages
- Deploy from `frontend/` directory

---

## Phase 2: Data Automation (future)

- Integrate AviationStack / OpenSky API for live verification
- Cron job on head1: daily data refresh
- Status change detection + logging
- Telegram alerts on status changes

## Phase 3: Dashboard Polish (future)

- Route timeline (when did X suspend/resume?)
- Map visualization
- Search/filter by destination
- Data export (CSV)
- Status change history graph

---

## Data Flow

```
data/airlines.yaml (curated seed)
         ↓
scripts/seed.py → SQLite (data/airlines.db)
         ↓
scripts/collect.py → API calls → update SQLite
         ↓
scripts/build_data.py → frontend/data.json (static)
         ↓
Cloudflare Pages → serves frontend/ + data.json
```

## Files to Create

```
fly2israel/
├── .gitignore
├── .env.example
├── README.md
├── AGENTS.md
├── requirements.txt
├── data/
│   ├── airlines.yaml        ← seed data (curated)
│   └── airlines.db          ← SQLite (gitignored)
├── scripts/
│   ├── init_db.py           ← create tables
│   ├── seed.py              ← load YAML → SQLite
│   ├── collect.py           ← API collection (stub)
│   └── build_data.py        ← SQLite → static JSON
├── api/
│   ├── __init__.py
│   ├── main.py              ← FastAPI app
│   └── db.py                ← DB helper
├── frontend/
│   ├── index.html           ← dashboard SPA
│   ├── style.css            ← clean DS theme
│   └── app.js               ← logic
├── docs/                    ← (reserved for future use)
└── .hermes/
    └── plans/
        └── implementation.md ← this file
```

## Verification

1. `python3 scripts/init_db.py` → creates SQLite schema
2. `python3 scripts/seed.py` → 30+ airlines, 80+ routes loaded
3. `python3 -m api.main` → FastAPI at localhost:8000
4. `curl localhost:8000/api/stats` → returns JSON summary
5. `python3 scripts/build_data.py` → creates `frontend/data.json`
6. Open `frontend/index.html` → see dashboard with airline table
7. Push to GitHub → Cloudflare Pages auto-deploys → live site
