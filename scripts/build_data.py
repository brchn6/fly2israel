"""
Build static JSON data for the frontend from SQLite.
Output: frontend/data.json (consumed by the SPA).
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from api.db import query

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'data.json')


def build():
    data = {
        "airlines": query("""
            SELECT
                a.id, a.name, a.iata, a.icao, a.country,
                COUNT(r.id) AS total_routes,
                SUM(CASE WHEN r.status = 'active' THEN 1 ELSE 0 END) AS active_routes,
                SUM(CASE WHEN r.status = 'suspended' THEN 1 ELSE 0 END) AS suspended_routes,
                SUM(CASE WHEN r.status = 'seasonal' THEN 1 ELSE 0 END) AS seasonal_routes
            FROM airlines a
            LEFT JOIN routes r ON r.airline_id = a.id
            GROUP BY a.id
            ORDER BY active_routes DESC, a.name
        """),
        "routes": query("""
            SELECT r.*, a.name AS airline_name, a.iata AS airline_iata, a.country AS airline_country
            FROM routes r
            JOIN airlines a ON a.id = r.airline_id
            ORDER BY a.name, r.destination
        """),
        "stats": {},
        "destinations": query("""
            SELECT destination, destination_name, destination_country,
                   COUNT(*) AS airline_count
            FROM routes
            JOIN airlines a ON a.id = routes.airline_id
            WHERE routes.status = 'active'
            GROUP BY destination
            ORDER BY destination_name
        """),
        "generated_at": None,
    }

    # Calculate stats
    total = len(data["airlines"])
    active_airlines = sum(1 for a in data["airlines"] if a["active_routes"] > 0 and a["suspended_routes"] == 0)
    suspended_airlines = sum(1 for a in data["airlines"] if a["active_routes"] == 0 and a["suspended_routes"] > 0)
    partial_airlines = sum(1 for a in data["airlines"] if a["active_routes"] > 0 and a["suspended_routes"] > 0)
    total_routes = len(data["routes"])
    active_routes = sum(1 for r in data["routes"] if r["status"] == "active")
    suspended_routes = sum(1 for r in data["routes"] if r["status"] == "suspended")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    data["stats"] = {
        "total_airlines": total,
        "total_routes": total_routes,
        "active_routes": active_routes,
        "suspended_routes": suspended_routes,
        "active_airlines": active_airlines,
        "suspended_airlines": suspended_airlines,
        "partial_airlines": partial_airlines,
        "last_updated": now,
    }
    data["generated_at"] = now

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(data, f, indent=2, default=str)

    print(f"✓ Built {OUTPUT_PATH} ({len(json.dumps(data))} bytes)")
    print(f"  {total} airlines, {total_routes} routes ({active_routes} active, {suspended_routes} suspended)")


if __name__ == '__main__':
    build()
