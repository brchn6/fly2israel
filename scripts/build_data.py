"""
Build static JSON data for the frontend from SQLite.
Output: frontend/data.json (consumed by the SPA).
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from api.db import query, query_one

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'data.json')


def build():
    airlines = query("""
        SELECT
            a.id, a.name, a.iata, a.icao, a.country, a.never_suspended,
            COUNT(r.id) AS total_routes,
            SUM(CASE WHEN r.status = 'active' THEN 1 ELSE 0 END) AS active_routes,
            SUM(CASE WHEN r.status = 'suspended' THEN 1 ELSE 0 END) AS suspended_routes,
            SUM(CASE WHEN r.status = 'seasonal' THEN 1 ELSE 0 END) AS seasonal_routes
        FROM airlines a
        LEFT JOIN routes r ON r.airline_id = a.id
        GROUP BY a.id
        ORDER BY active_routes DESC, a.name
    """)

    routes = query("""
        SELECT r.*, a.name AS airline_name, a.iata AS airline_iata, a.country AS airline_country
        FROM routes r
        JOIN airlines a ON a.id = r.airline_id
        ORDER BY a.name, r.destination
    """)

    destinations = query("""
        SELECT destination, destination_name, destination_country,
               COUNT(*) AS airline_count
        FROM routes
        JOIN airlines a ON a.id = routes.airline_id
        WHERE routes.status = 'active'
        GROUP BY destination
        ORDER BY destination_name
    """)

    scores = query("""
        SELECT a.name AS airline_name, a.iata,
               s.uptime_pct, s.reliability_score, s.score_label,
               s.suspension_lag_days, s.resumption_lag_days, s.still_suspended
        FROM airlines a
        LEFT JOIN airline_scores s ON s.airline_id = a.id
        ORDER BY s.reliability_score DESC NULLS LAST
    """)

    timeline = query("""
        SELECT te.*, a.name AS airline_name, a.iata
        FROM timeline_events te
        JOIN airlines a ON a.id = te.airline_id
        ORDER BY te.event_date DESC
    """)

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    # Stats
    total = len(airlines)
    active_airlines = sum(1 for a in airlines if a['active_routes'] > 0 and a['suspended_routes'] == 0)
    suspended_airlines = sum(1 for a in airlines if a['active_routes'] == 0 and a['suspended_routes'] > 0)
    partial_airlines = sum(1 for a in airlines if a['active_routes'] > 0 and a['suspended_routes'] > 0)
    total_routes = len(routes)
    active_routes_count = sum(1 for r in routes if r['status'] == 'active')
    suspended_routes_count = sum(1 for r in routes if r['status'] == 'suspended')

    avg_score = None
    scored = [s for s in scores if s['reliability_score'] is not None]
    if scored:
        avg_score = round(sum(s['reliability_score'] for s in scored) / len(scored), 1)

    data = {
        "airlines": airlines,
        "routes": routes,
        "destinations": destinations,
        "scores": scores,
        "timeline": timeline,
        "stats": {
            "total_airlines": total,
            "total_routes": total_routes,
            "active_routes": active_routes_count,
            "suspended_routes": suspended_routes_count,
            "active_airlines": active_airlines,
            "suspended_airlines": suspended_airlines,
            "partial_airlines": partial_airlines,
            "avg_reliability_score": avg_score,
            "last_updated": now,
        },
        "generated_at": now,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(data, f, indent=2, default=str)

    print(f"✓ Built {OUTPUT_PATH} ({len(json.dumps(data))} bytes)")
    print(f"  {total} airlines, {total_routes} routes ({active_routes_count} active, {suspended_routes_count} suspended)")
    print(f"  {len(scores)} scores, {len(timeline)} timeline events")


if __name__ == '__main__':
    build()
