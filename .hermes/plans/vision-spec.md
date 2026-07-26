# 🚀 fly2israel — Full Vision Plan & Spec

> **Vision:** An Uptime Radar for airlines flying to/from Israel.  
> Like Datadog/Grafana for server uptime, but for airlines — showing who's flying, who's not, and who you can trust when things get tense.

---

## Core Problems This Solves

1. **Information is scattered** — every airline announces separately, no central view
2. **No historical context** — "this airline suspended in Oct 2023 and only resumed 14 months later" is invisible
3. **No reliability signal** — travelers need to know which airlines kept flying vs. cut and ran
4. **Mobile is terrible** — news articles, PDFs, Twitter threads — not glanceable

## Target Users

- **"The dumb user"** — doesn't read data, wants one answer: "which airline should I book?"
- **Travelers** — checking if their flight is likely to operate
- **Data-curious** — exploring trends across airlines over time

---

## Data Model Enhancements

### New: `timeline_events` table
```sql
CREATE TABLE timeline_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  airline_id INTEGER NOT NULL REFERENCES airlines(id),
  route_id INTEGER REFERENCES routes(id),  -- NULL if airline-wide event
  event_date TEXT NOT NULL,                 -- ISO date when it happened
  event_type TEXT NOT NULL CHECK(event_type IN ('suspension','resumption','partial_suspension','partial_resumption','notice')),
  status_before TEXT,                       -- e.g. 'active' -> 'suspended'
  status_after TEXT,
  source TEXT,                              -- URL or description of where we got this
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_timeline_airline ON timeline_events(airline_id);
CREATE INDEX idx_timeline_date ON timeline_events(event_date);
```

### New: `airline_scores` table (computed, refreshed on build)
```sql
CREATE TABLE airline_scores (
  airline_id INTEGER PRIMARY KEY REFERENCES airlines(id),
  uptime_pct REAL,          -- % of days since Oct 7 2023 that routes were active
  suspension_lag_days INTEGER,  -- days from Oct 7 2023 until suspension (lower = faster to flee)
  resumption_lag_days INTEGER,  -- days from suspension until resumption (higher = slower to return)
  reliability_score REAL,   -- composite 0-100
  last_calculated TEXT DEFAULT (datetime('now'))
);
```

### Updated: `routes` table
Add `suspended_date` and `resumed_date` columns for quick reference.

---

## Reliability Score Formula

```
reliability_score = 100

penalties:
  - suspension after Oct 7 within 30 days  → -20 pts (fast to flee)
  - suspension after Oct 7 within 7 days   → -35 pts (panicked)
  - each 30 days suspended                 → -5 pts
  - resumption took > 6 months             → -15 pts
  - resumption took > 12 months            → -30 pts
  - still suspended as of today            → -40 pts

bonuses:
  - never suspended                        → +20 pts
  - resumed within 3 months                → +10 pts
  - resumed with expanded routes           → +5 pts

min score: 0, max score: 100
```

Display:
- **90-100:** 🟢 Excellent
- **70-89:** 🟡 Good
- **40-69:** 🟠 Average
- **0-39:** 🔴 Unreliable

---

## Frontend Vision

### Layout (mobile-first)

```
┌──────────────────────────────────┐
│  ✈️ fly2israel                    │
│  "Who flies to Israel right now" │
├──────────────────────────────────┤
│  ┌───┐ ┌───┐ ┌───┐ ┌───┐      │
│  │41 │ │29 │ │11 │ │?? │      │
│  │ALs│ │ON │ │OFF│ │ AVG│      │
│  └───┘ └───┘ └───┘ └───┘      │
├──────────────────────────────────┤
│                                  │
│  🔍 "Find airline..."           │
│                                  │
│  ┌──────────────────────────┐   │
│  │ El Al   █████████████ 100%│   │
│  │         ── LY ── 15 routes│   │
│  │         🏆 Recommended    │   │
│  ├──────────────────────────┤   │
│  │ Delta   ████░░░░░░░░  23%│   │
│  │         ── DL ──  routes  │   │
│  │         ⚠️ Suspended      │   │
│  ├──────────────────────────┤   │
│  │ Korean  ██░░░░░░░░░░  12%│   │
│  │         ── KE ──          │   │
│  │         🔴 Still out      │   │
│  └──────────────────────────┘   │
│                                  │
│  [Which airline should I fly?]   │
│  → "El Al has the best record"   │
│                                  │
├──────────────────────────────────┤
│  Timeline: El Al                 │
│  Oct23 Nov Jan Mar May Jul...    │
│  ████████████████████████████    │
│                                  │
│  Timeline: Delta                 │
│  Oct23 Nov Jan Mar May Jul...    │
│  ████░░░░░░░░░░░░░░░░░░░░░░    │
│         ^ suspended Oct 12      │
│         still suspended         │
└──────────────────────────────────┘
```

### Key UI Features
1. **Airline cards** — uptime bar (green/red), reliability badge, route count
2. **Timeline sparkline** — miniature GitHub-contribution-style heatmap showing each month
3. **Recommended badge** — "🏆 This airline has the best reliability record"
4. **"Which airline should I fly?"** — single button → answer with reasoning
5. **Mobile-first** — one column, big text, swipeable
6. **Desktop** — grid view, more data density

### Pages
1. `/` — Main dashboard (airline list + summary)
2. `/airline/{iata}` — Deep dive: timeline, route list, score breakdown
3. `/compare` — Side-by-side comparison (v2)

---

## Data Collection Strategy

### Phase A: Historical (now)
- Manually curated timeline data for all 41 airlines
- Sources: Wikipedia, news archives, airline announcements
- Stored as YAML seed → imported to timeline_events

### Phase B: Live (next)
- AviationStack API (free tier: 500 req/mo) — weekly route verification
- AeroDataBox RapidAPI (free tier) — schedule lookup
- OpenSky Network — live flight tracking (technical)
- IAA (Israel Airports Authority) — official departure board

### Phase C: Automated (future)
- Cron job on head1: daily check + status change detection
- Auto-deploy to Cloudflare Pages on change
- Optional Telegram alerts for status changes

---

## Implementation Tasks

### Task 1: Schema + Seed Enhancement
- Add timeline_events table, airline_scores table
- Update init_db.py
- Create `data/timeline.yaml` with historical data for all airlines

### Task 2: Historical Research (Big one)
- For each of 41 airlines, find actual suspension/resumption dates
- Sources: Wikipedia, news, airline websites
- This is the most valuable asset of the project

### Task 3: Reliability Metrics
- scripts/calculate_scores.py — computes airline_scores from timeline
- API: GET /api/airlines/{iata}/score
- API: GET /api/airlines/{iata}/timeline

### Task 4: Frontend Overhaul
- Uptime bars on airline cards
- Timeline visualization (sparkline or mini-Gantt)
- "Which airline should I fly?" widget
- Mobile-first layout
- Airline detail page (expandable or separate view)

### Task 5: Automation
- GitHub Actions: daily build + deploy
- Or cron on head1
- Or both (redundant)

---

## File Changes

| File | Action |
|------|--------|
| `scripts/init_db.py` | Add timeline_events, airline_scores tables |
| `scripts/seed.py` | Also seed timeline_events from YAML |
| `data/timeline.yaml` | **NEW** — curated historical timeline |
| `scripts/calculate_scores.py` | **NEW** — compute reliability metrics |
| `scripts/build_data.py` | Include timeline + scores in data.json |
| `api/main.py` | Add /timeline, /score, /recommend endpoints |
| `frontend/index.html` | Full redesign |
| `frontend/style.css` | Full redesign |
| `frontend/app.js` | Full rewrite |

---

## Risks & Open Questions

1. **Historical data accuracy** — timeline.yamal must cite sources. Some dates may be approximate (±few days). Mark uncertain dates with `?`.
2. **"Security proxy"** — what external metric to correlate with? (Color red alerts? TASE index? Tourism data?) **Decision needed.**
3. **Data freshness expectations** — live = daily? every 5 mins? Users need to know latency.
4. **Reliability score transparency** — users MUST be able to see how the score is calculated (formula visible, like you said).
