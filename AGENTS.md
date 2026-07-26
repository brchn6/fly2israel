# ✈️ fly2israel — Agent Handoff

## What is this?

Tracks which airlines fly **to and from Israel** and whether their routes are active, suspended, or seasonal. Live dashboard + clean API.

## 🚫 ABSOLUTE RULES

- **Never guess route status** — only update from verified sources (official airline announcements, IAA notices, news with named sources).
- **Never delete production data** — all destructive DB ops need explicit confirmation.
- **No paid API keys** without explicit approval. Free tiers only.

## Architecture

```
head1 (collector host)
  ├── cron job: fetch data daily from free APIs
  ├── data/airlines.db (SQLite — source of truth)
  ├── scripts/ — data collection & processing
  └── api/ — FastAPI backend (optional, for dev)

Cloudflare Pages
  └── Frontend (static HTML/CSS/JS — SPA)
```

## Quick Reference

| Item | Value |
|------|-------|
| **Repo** | (TBD — will be pushed to GitHub) |
| **Collector** | **head1** (100.93.8.110) — `~/dev/fly2israel/` |
| **API Sources** | AviationStack (free: 500/mo), OpenSky Network (free), AeroDataBox (RapidAPI free) |
| **Dashboard** | `fly2israel.pages.dev` (Cloudflare Pages) |
| **Deploy** | `git push` → GitHub → Cloudflare Pages auto-deploy |
| **Secrets** | `.env` on head1 (mode 600) — API keys |

## Data Sources (free tiers)

| Source | Cost | Rate Limit | Data Type |
|--------|------|-----------|-----------|
| **AviationStack** | Free (500 req/mo) | 1 req/s | Routes, airlines, flights |
| **OpenSky Network** | Free | 4 req/s (unregistered), 10 req/s (registered) | Live flight positions |
| **AeroDataBox** (RapidAPI) | Free (tier) | Varies | Routes, schedules |
| **FlightRadar24** (unofficial) | Free | Unofficial API | Live tracking |
| **IAA** (Israel Airports Authority) | Free | — | Official TLV flight data |

## Data Model

### airlines table
```sql
CREATE TABLE airlines (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  iata TEXT,           -- 2-letter code (e.g. LY)
  icao TEXT,           -- 3-letter code (e.g. ELY)
  country TEXT,
  logo_url TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);
```

### routes table
```sql
CREATE TABLE routes (
  id INTEGER PRIMARY KEY,
  airline_id INTEGER NOT NULL REFERENCES airlines(id),
  origin TEXT NOT NULL,        -- airport code (e.g. TLV)
  destination TEXT NOT NULL,   -- airport code
  destination_name TEXT,       -- city name
  destination_country TEXT,
  status TEXT NOT NULL CHECK(status IN ('active','suspended','seasonal','unknown')),
  last_verified TEXT,          -- when we last checked
  source TEXT,                 -- where we got the status
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  UNIQUE(airline_id, origin, destination)
);
```

### status_log table
```sql
CREATE TABLE status_log (
  id INTEGER PRIMARY KEY,
  route_id INTEGER NOT NULL REFERENCES routes(id),
  old_status TEXT,
  new_status TEXT NOT NULL,
  changed_at TEXT DEFAULT (datetime('now')),
  source TEXT,
  notes TEXT
);
```

## Setup

```bash
git clone ... && cd fly2israel
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add API keys
```

## Running

```bash
# Collect data
python3 scripts/collect.py

# Generate static data for dashboard
python3 scripts/build_data.py

# Or run the API locally
python3 -m api.main
```

## Deploy

Push to GitHub → Cloudflare Pages auto-deploys from the `docs/` or `frontend/` directory.

## Current Airlines Serving Israel (initial dataset)

See `data/airlines.yaml` for the curated seed list.
