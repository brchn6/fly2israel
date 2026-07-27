# ✈️ fly2israel — Agent Handoff

## What is this?

Tracks which airlines fly **to and from Israel** and whether their routes are active, suspended, or seasonal. Live dashboard + clean API. Reliability scores based on historical data from Wikipedia.

## 🚫 ABSOLUTE RULES

- **Never guess route status** — only update from verified sources
- **Never delete production data** — all destructive DB ops need explicit confirmation
- **No paid API keys** without explicit approval. Free tiers only.
- **Dashboard shows ONLY verified data** — no mock/fake/simulated data ever
- **Score formula transparency** — every metric must have visible formula explanation

## Current State (July 26, 2026)

✅ **Live at:** https://fly2israel.pages.dev  
✅ **GitHub:** https://github.com/brchn6/fly2israel  
✅ **Collector host:** head1 (100.93.8.110) — `/home/barc/dev/fly2israel`

## Architecture

```
head1 (collector host)
  ├── scripts/research/scrape_wikipedia_timeline.py  ← fetches 34 monthly snapshots
  ├── scripts/research/generate_timeline_from_wikipedia.py  ← builds timeline.yaml
  ├── scripts/seed.py          ← loads timeline.yaml → SQLite
  ├── scripts/calculate_scores.py  ← computes reliability scores
  ├── scripts/build_data.py    ← SQLite → frontend/data.json (static)
  └── data/airlines.db         ← SQLite (source of truth)

Cloudflare Pages
  └── frontend/                ← static SPA dashboard (vanilla JS)
```

## Data Pipeline

```
Wikipedia "Ben Gurion Airport" page (34 monthly revisions: Oct 2023 - Jul 2026)
         ↓
scrape_wikipedia_timeline.py   ← extracts airline table from each revision
         ↓
generate_timeline_from_wikipedia.py   ← detects status changes between snapshots
         ↓
data/timeline.yaml   ← 195 events, 40 airlines (VERIFIED, source-attributed)
         ↓
seed.py  →  SQLite (airlines.db)
         ↓
calculate_scores.py  →  airline_scores table
         ↓
build_data.py  →  frontend/data.json
         ↓
wrangler pages deploy  →  fly2israel.pages.dev
```

## Data Sources

| Source | Type | Coverage |
|--------|------|----------|
| **Wikipedia Ben Gurion Airport page** | Monthly snapshots | Oct 2023 - Jul 2026 (34 revisions) |
| Airlines & destinations table | Current state + historical | 53 airlines with notes |

Each snapshot saved as `data/research/snapshot_YYYY-MM-DD.json`.  
Combined data: `data/research/combined_timeline.json`.  
Generated timeline: `data/timeline.yaml` (auto-generated from snapshots, some manual fixes applied).

## Data Model

### airlines table
| Column | Description |
|--------|-------------|
| id, name, iata, icao, country | Core airline info |
| never_suspended | Flag: true = operated throughout the entire period |

### routes table
| Column | Description |
|--------|-------------|
| airline_id, origin, destination | Route definition |
| status | active / suspended / seasonal / unknown |
| last_verified | When this status was last confirmed |

### timeline_events table
| Column | Description |
|--------|-------------|
| airline_id, route_id | Event target |
| event_date | Midpoint between observed snapshot changes (±15 days) |
| event_type | suspension / resumption / notice / maintained |
| status_before, status_after | State transition |
| source | "Wikipedia Ben Gurion Airport page snapshots" |

### airline_scores table
| Column | Description |
|--------|-------------|
| airline_id | FK to airlines |
| uptime_pct | % of days active since Oct 7, 2023 |
| reliability_score | 0-100 composite score |
| score_label | excellent / good / average / unreliable |
| still_suspended | Currently suspended flag |

## Reliability Score Formula

```
Base: 100

Penalties:
  - First suspension within 7 days of Oct 7:  -35 (panicked)
  - First suspension within 30 days:           -20 (fast to flee)
  - Each month suspended (total):              -5 pts/month
  - Total suspended > 180 days:                -15
  - Total suspended > 365 days:                -30
  - Still suspended as of now:                 -40

Bonuses:
  - Never suspended:                           +20

Min: 0, Max: 100

Labels:
  90-100: excellent (🟢)
  70-89:  good     (🟡)
  40-69:  average  (🟠)
  0-39:   unreliable (🔴)
```

**⚠️ Known issue:** Score formula needs tuning. Airlines with multiple short suspension cycles (e.g. Lufthansa, Delta) get 0% because the cycling penalty + still_suspended flag crush the score. The data is correct, the formula is too harsh.

## Current Scores (from Wikipedia data)

| Tier | Airlines |
|------|----------|
| **100%** | El Al, Arkia, Israir, Etihad, Flydubai, Ethiopian, Bluebird, TUS |
| **95%** | TAROM |
| **85%** | Uzbekistan Airways |
| **65%** | Azerbaijan Airlines |
| **43%** | Wizz Air, SAS |
| **19%** | Hainan Airlines |
| **0%** | Delta, United, American, Lufthansa, Air France, BA, KLM, + many more |

## Frontend

### Current Features
- KPI cards: Total, Active, Suspended, Avg Reliability
- Airline cards with status badges and route counts
- Uptime bars (when real timeline data available)
- Reliability badges
- "Which airline should I fly?" recommendation button
- Search + filter by status
- Expandable airline cards with route lists
- Dark/light mode (auto)
- Mobile-first responsive

### Future Features (not yet built)
- Monthly timeline heatmap per airline
- Score formula display (math transparency)
- Security proxy / external metric correlation
- Historical trend chart

## API Endpoints

| Route | Description |
|-------|-------------|
| `GET /api/airlines` | All airlines with scores |
| `GET /api/airlines/{iata}` | Single airline with routes + timeline |
| `GET /api/routes?status=` | Filterable routes |
| `GET /api/stats` | Summary statistics |
| `GET /api/scores` | All scores |
| `GET /api/recommend` | Best airline recommendation |
| `GET /api/timeline?airline=` | Timeline events |
| `GET /api/destinations` | Active destinations |

## Quick Reference

```bash
# Full pipeline (from scratch)
cd ~/dev/fly2israel
source .venv/bin/activate
rm -f data/airlines.db
python3 scripts/init_db.py
python3 scripts/seed.py
python3 scripts/calculate_scores.py
python3 scripts/build_data.py
wrangler pages deploy frontend/ --project-name fly2israel

# Re-scrape Wikipedia data
python3 scripts/research/scrape_wikipedia_timeline.py

# Re-generate timeline.yaml from snapshots
python3 scripts/research/generate_timeline_from_wikipedia.py
```

## Open Issues / Decisions Needed

1. **Score formula** — too harsh for airlines with multiple short cycles. Needs user input on desired behavior.
2. **Data accuracy** — Wikipedia snapshots are ±15 day precision. Some "suspension" events detected from seasonal route notes (not airline-wide suspensions).
3. **Emirates disappeared from Wikipedia table** — was present early 2024, then absent from later 2024. Still flies to TLV. The Wikipedia table is not a perfect source.
4. **Deploy automation** — no CI/CD yet. Manual `wrangler pages deploy` only.
5. **Historical data beyond Wikipedia** — eTurboNews Jan 2024 article has earlier resumption dates that could refine the timeline.

## Project Structure

```
fly2israel/
├── api/
│   ├── main.py              ← FastAPI (8 endpoints)
│   └── db.py                ← SQLite helper
├── frontend/
│   ├── index.html           ← Dashboard SPA
│   ├── style.css            ← Dark/light theme, cards, responsive
│   ├── app.js               ← Vanilla JS (490 lines)
│   └── data.json            ← Static data (gitignored, built locally)
├── scripts/
│   ├── init_db.py           ← Create SQLite schema
│   ├── seed.py              ← Load YAML data → SQLite
│   ├── collect.py           ← Stub for live API collection
│   ├── calculate_scores.py  ← Reliability score computation
│   ├── build_data.py        ← SQLite → frontend/data.json
│   └── research/
│       ├── scrape_wikipedia_timeline.py       ← Fetch historical snapshots
│       └── generate_timeline_from_wikipedia.py ← Build timeline.yaml
├── data/
│   ├── airlines.yaml        ← Seed data (41 airlines, 78 routes)
│   ├── timeline.yaml        ← Auto-generated timeline (195 events)
│   ├── airlines.db          ← SQLite (gitignored)
│   └── research/            ← Raw snapshots + combined data
├── .hermes/plans/           ← Plans and specs
├── .gitignore
├── .env.example
├── AGENTS.md                ← This file
├── README.md
└── requirements.txt
```

## Setup

```bash
git clone https://github.com/brchn6/fly2israel.git && cd fly2israel
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 scripts/init_db.py
python3 scripts/seed.py
python3 scripts/calculate_scores.py
python3 scripts/build_data.py
wrangler pages deploy frontend/ --project-name fly2israel
```
