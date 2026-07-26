"""
Initialize the SQLite database schema.
Idempotent — safe to re-run.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'airlines.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS airlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    iata TEXT,
    icao TEXT,
    country TEXT,
    logo_url TEXT,
    never_suspended INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    airline_id INTEGER NOT NULL REFERENCES airlines(id),
    origin TEXT NOT NULL DEFAULT 'TLV',
    destination TEXT NOT NULL,
    destination_name TEXT,
    destination_country TEXT,
    status TEXT NOT NULL DEFAULT 'unknown' CHECK(status IN ('active','suspended','seasonal','unknown')),
    suspended_date TEXT,
    resumed_date TEXT,
    last_verified TEXT,
    source TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(airline_id, origin, destination)
);

CREATE TABLE IF NOT EXISTS status_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id INTEGER NOT NULL REFERENCES routes(id),
    old_status TEXT,
    new_status TEXT NOT NULL,
    changed_at TEXT DEFAULT (datetime('now')),
    source TEXT,
    notes TEXT
);

-- Timeline of airline-level events (suspensions, resumptions)
CREATE TABLE IF NOT EXISTS timeline_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    airline_id INTEGER NOT NULL REFERENCES airlines(id),
    route_id INTEGER REFERENCES routes(id),
    event_date TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN ('suspension','resumption','partial_suspension','partial_resumption','notice','maintained')),
    status_before TEXT,
    status_after TEXT,
    source TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_timeline_airline ON timeline_events(airline_id);
CREATE INDEX IF NOT EXISTS idx_timeline_date ON timeline_events(event_date);

-- Computed reliability scores (refreshed on build)
CREATE TABLE IF NOT EXISTS airline_scores (
    airline_id INTEGER PRIMARY KEY REFERENCES airlines(id),
    uptime_pct REAL,
    suspension_lag_days INTEGER,
    resumption_lag_days INTEGER,
    still_suspended INTEGER DEFAULT 0,
    reliability_score REAL,
    score_label TEXT,
    last_calculated TEXT DEFAULT (datetime('now'))
);

-- Views for convenience
CREATE VIEW IF NOT EXISTS v_summary AS
SELECT
    a.id AS airline_id,
    a.name AS airline,
    a.iata,
    a.country,
    COUNT(r.id) AS total_routes,
    SUM(CASE WHEN r.status = 'active' THEN 1 ELSE 0 END) AS active_routes,
    SUM(CASE WHEN r.status = 'suspended' THEN 1 ELSE 0 END) AS suspended_routes,
    SUM(CASE WHEN r.status = 'seasonal' THEN 1 ELSE 0 END) AS seasonal_routes
FROM airlines a
LEFT JOIN routes r ON r.airline_id = a.id
GROUP BY a.id
ORDER BY active_routes DESC;

CREATE VIEW IF NOT EXISTS v_airline_status AS
SELECT
    a.name AS airline,
    a.iata,
    a.country,
    CASE
        WHEN SUM(CASE WHEN r.status = 'active' THEN 1 ELSE 0 END) > 0
         AND SUM(CASE WHEN r.status IN ('suspended','unknown') THEN 1 ELSE 0 END) = 0
        THEN 'active'
        WHEN SUM(CASE WHEN r.status = 'active' THEN 1 ELSE 0 END) = 0
         AND SUM(CASE WHEN r.status = 'suspended' THEN 1 ELSE 0 END) > 0
        THEN 'suspended'
        WHEN SUM(CASE WHEN r.status = 'active' THEN 1 ELSE 0 END) > 0
         AND SUM(CASE WHEN r.status = 'suspended' THEN 1 ELSE 0 END) > 0
        THEN 'partial'
        ELSE 'unknown'
    END AS overall_status
FROM airlines a
LEFT JOIN routes r ON r.airline_id = a.id
GROUP BY a.id;

CREATE VIEW IF NOT EXISTS v_airline_scores AS
SELECT
    a.name AS airline,
    a.iata,
    COALESCE(s.uptime_pct, 0) AS uptime_pct,
    COALESCE(s.reliability_score, 0) AS reliability_score,
    COALESCE(s.score_label, 'unknown') AS score_label,
    s.last_calculated
FROM airlines a
LEFT JOIN airline_scores s ON s.airline_id = a.id
ORDER BY s.reliability_score DESC;
"""


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"✓ Database initialized at {DB_PATH}")


if __name__ == '__main__':
    init_db()
