# ✈️ fly2israel

**Which airlines fly to and from Israel?**  
Live uptime radar — routes, status, and reliability scores.

**[fly2israel.pages.dev](https://fly2israel.pages.dev)**

## What it does

- Tracks **41 airlines** and **78 routes** serving Israel
- Shows current status: active / suspended / seasonal
- **Reliability score** (0-100) based on historical track record since Oct 2023
- Data sourced from **Wikipedia Ben Gurion Airport page** — 34 monthly snapshots, 195 verified events
- Clean API + static dashboard, zero cost

## Stack

- **Backend:** Python, FastAPI, SQLite
- **Frontend:** Vanilla JS, CSS (dark/light auto), mobile-first
- **Hosting:** Cloudflare Pages (free)
- **Data:** Wikipedia API → automated scraping pipeline

## Reproduce

```bash
git clone https://github.com/brchn6/fly2israel.git
cd fly2israel
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/init_db.py
python3 scripts/seed.py
python3 scripts/calculate_scores.py
python3 scripts/build_data.py
```

## License

MIT
