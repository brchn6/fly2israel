"""
Seed the database from data/airlines.yaml.
Idempotent — safe to re-run (upserts).
"""
import sqlite3
import yaml
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scripts.init_db import init_db, DB_PATH

SEED_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'airlines.yaml')


def seed():
    # Ensure DB exists
    init_db()

    with open(SEED_PATH) as f:
        data = yaml.safe_load(f)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    airlines_loaded = 0
    routes_loaded = 0

    for al in data.get('airlines', []):
        # Upsert airline
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

        # If it was a conflict, get the existing id
        if airline_id is None:
            cur.execute("SELECT id FROM airlines WHERE name = ?", (al['name'],))
            row = cur.fetchone()
            airline_id = row['id']

        airlines_loaded += 1

        # Upsert routes
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

    conn.commit()
    conn.close()
    print(f"✓ Seeded {airlines_loaded} airlines, {routes_loaded} routes")


if __name__ == '__main__':
    seed()
