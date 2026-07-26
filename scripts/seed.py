"""
Seed the database from data/airlines.yaml and data/timeline.yaml.
Idempotent — safe to re-run.
"""
import sqlite3
import yaml
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scripts.init_db import init_db, DB_PATH

SEED_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'airlines.yaml')
TIMELINE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'timeline.yaml')


def seed():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ── Seed airlines & routes ──
    with open(SEED_PATH) as f:
        data = yaml.safe_load(f)

    airlines_loaded = 0
    routes_loaded = 0

    for al in data.get('airlines', []):
        cur.execute("""
            INSERT INTO airlines (name, iata, icao, country)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                iata = excluded.iata,
                icao = excluded.icao,
                country = excluded.country,
                updated_at = datetime('now')
        """, (al['name'], al.get('iata'), al.get('icao'), al.get('country')))
        airline_id = cur.lastrowid
        if airline_id is None:
            cur.execute("SELECT id FROM airlines WHERE name = ?", (al['name'],))
            airline_id = cur.fetchone()['id']

        airlines_loaded += 1

        for rt in al.get('routes', []):
            cur.execute("""
                INSERT INTO routes (airline_id, origin, destination, destination_name, destination_country, status, source, last_verified)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(airline_id, origin, destination) DO UPDATE SET
                    status = excluded.status,
                    destination_name = excluded.destination_name,
                    destination_country = excluded.destination_country,
                    source = excluded.source,
                    last_verified = excluded.last_verified,
                    updated_at = datetime('now')
            """, (
                airline_id,
                rt.get('origin', 'TLV'),
                rt['destination'],
                rt.get('destination_name'),
                rt.get('destination_country'),
                rt.get('status', 'unknown'),
                al.get('source', 'seed')
            ))
            routes_loaded += 1

    # ── Seed timeline events ──
    timeline_loaded = 0
    if os.path.exists(TIMELINE_PATH):
        with open(TIMELINE_PATH) as f:
            timeline_data = yaml.safe_load(f) or {}

        for entry in timeline_data.get('timeline', []):
            # Find airline
            cur.execute("SELECT id FROM airlines WHERE name = ? OR iata = ?",
                        (entry['airline'], entry.get('iata', '')))
            row = cur.fetchone()
            if not row:
                print(f"  ⚠ Airline not found for timeline: {entry['airline']}")
                continue
            airline_id = row['id']

            # Mark never_suspended
            if entry.get('never_suspended'):
                cur.execute("UPDATE airlines SET never_suspended = 1 WHERE id = ?", (airline_id,))

            # Insert events
            for ev in entry.get('events', []):
                cur.execute("""
                    INSERT INTO timeline_events (airline_id, route_id, event_date, event_type, status_before, status_after, source, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    airline_id,
                    ev.get('route_id'),
                    ev['date'],
                    ev['event_type'],
                    ev.get('status_before'),
                    ev.get('status_after'),
                    ev.get('source', ''),
                    ev.get('notes', '')
                ))
                timeline_loaded += 1

    conn.commit()
    conn.close()
    print(f"✓ Seeded {airlines_loaded} airlines, {routes_loaded} routes, {timeline_loaded} timeline events")


if __name__ == '__main__':
    seed()
