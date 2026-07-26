"""
FastAPI app: clean REST API for fly2israel data.
"""
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from api.db import query, query_one

app = FastAPI(
    title="fly2israel API",
    description="Track which airlines fly to/from Israel",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/airlines")
def list_airlines(sort: str = Query("active", regex="^(active|name|score)$")):
    """All airlines with route counts and scores."""
    order_map = {
        'active': 'active_routes DESC, a.name',
        'name': 'a.name',
        'score': 's.reliability_score DESC NULLS LAST',
    }
    return query(f"""
        SELECT
            a.id, a.name, a.iata, a.icao, a.country, a.never_suspended,
            COUNT(r.id) AS total_routes,
            SUM(CASE WHEN r.status = 'active' THEN 1 ELSE 0 END) AS active_routes,
            SUM(CASE WHEN r.status = 'suspended' THEN 1 ELSE 0 END) AS suspended_routes,
            COALESCE(s.reliability_score, 0) AS reliability_score,
            COALESCE(s.score_label, 'unknown') AS score_label,
            COALESCE(s.uptime_pct, 0) AS uptime_pct
        FROM airlines a
        LEFT JOIN routes r ON r.airline_id = a.id
        LEFT JOIN airline_scores s ON s.airline_id = a.id
        GROUP BY a.id
        ORDER BY {order_map.get(sort, order_map['active'])}
    """)


@app.get("/api/airlines/{iata}")
def get_airline(iata: str):
    """Single airline with routes, timeline, and score."""
    airline = query_one("""
        SELECT a.*, s.uptime_pct, s.reliability_score, s.score_label,
               s.suspension_lag_days, s.resumption_lag_days, s.still_suspended
        FROM airlines a
        LEFT JOIN airline_scores s ON s.airline_id = a.id
        WHERE UPPER(a.iata) = UPPER(?)
    """, (iata,))
    if not airline:
        return {"error": "Airline not found"}

    airline['routes'] = query("""
        SELECT * FROM routes WHERE airline_id = ? ORDER BY status, destination
    """, (airline['id'],))

    airline['timeline'] = query("""
        SELECT * FROM timeline_events WHERE airline_id = ? ORDER BY event_date ASC
    """, (airline['id'],))

    # Score breakdown
    score_breakdown = {}
    if airline['reliability_score'] is not None:
        score_breakdown = {
            "score": airline['reliability_score'],
            "label": airline['score_label'],
            "uptime_pct": airline['uptime_pct'],
            "suspension_lag_days": airline['suspension_lag_days'],
            "resumption_lag_days": airline['resumption_lag_days'],
            "still_suspended": bool(airline['still_suspended']),
        }
    airline['score_breakdown'] = score_breakdown

    return airline


@app.get("/api/routes")
def list_routes(
    status: str = Query(None, regex="^(active|suspended|seasonal|unknown)?$"),
    airline: str = Query(None),
    origin: str = Query(None),
    destination: str = Query(None),
):
    """Filterable route list."""
    sql = """
        SELECT r.*, a.name AS airline_name, a.iata AS airline_iata, a.country AS airline_country
        FROM routes r
        JOIN airlines a ON a.id = r.airline_id
        WHERE 1=1
    """
    params = []
    if status:
        sql += " AND r.status = ?"
        params.append(status)
    if airline:
        sql += " AND UPPER(a.iata) = UPPER(?)"
        params.append(airline)
    if origin:
        sql += " AND UPPER(r.origin) = UPPER(?)"
        params.append(origin)
    if destination:
        sql += " AND UPPER(r.destination) = UPPER(?)"
        params.append(destination)

    sql += " ORDER BY a.name, r.destination"
    return query(sql, params)


@app.get("/api/stats")
def stats():
    """Summary statistics."""
    total_airlines = query_one("SELECT COUNT(*) AS count FROM airlines")['count']
    total_routes = query_one("SELECT COUNT(*) AS count FROM routes")['count']
    active_routes = query_one("SELECT COUNT(*) AS count FROM routes WHERE status='active'")['count']
    suspended_routes = query_one("SELECT COUNT(*) AS count FROM routes WHERE status='suspended'")['count']

    airlines_by_status = query("""
        SELECT overall_status AS status, COUNT(*) AS count
        FROM v_airline_status
        GROUP BY overall_status
    """)

    destinations = query("""
        SELECT destination, destination_name, destination_country, COUNT(*) AS airline_count
        FROM routes WHERE status = 'active'
        GROUP BY destination
        ORDER BY airline_count DESC
    """)

    avg_score = query_one("SELECT AVG(reliability_score) AS avg FROM airline_scores WHERE reliability_score IS NOT NULL")

    return {
        "total_airlines": total_airlines,
        "total_routes": total_routes,
        "active_routes": active_routes,
        "suspended_routes": suspended_routes,
        "airlines_by_status": {r['status']: r['count'] for r in airlines_by_status},
        "top_destinations": destinations[:10],
        "avg_reliability_score": round(avg_score['avg'], 1) if avg_score and avg_score['avg'] else None,
        "last_updated": query_one("SELECT MAX(updated_at) AS t FROM airlines")['t'],
    }


@app.get("/api/destinations")
def list_destinations():
    """All unique active destinations with airline count."""
    return query("""
        SELECT destination, destination_name, destination_country,
               COUNT(*) AS airline_count,
               GROUP_CONCAT(a.name) AS airlines
        FROM routes r
        JOIN airlines a ON a.id = r.airline_id
        WHERE r.status = 'active'
        GROUP BY destination
        ORDER BY airline_count DESC, destination_name
    """)


@app.get("/api/scores")
def list_scores():
    """All airline reliability scores."""
    return query("""
        SELECT a.name, a.iata, a.country, a.never_suspended,
               s.uptime_pct, s.reliability_score, s.score_label,
               s.suspension_lag_days, s.resumption_lag_days, s.still_suspended,
               s.last_calculated
        FROM airlines a
        LEFT JOIN airline_scores s ON s.airline_id = a.id
        ORDER BY s.reliability_score DESC NULLS LAST
    """)


@app.get("/api/recommend")
def recommend():
    """Recommend the most reliable active airline."""
    best = query_one("""
        SELECT a.name, a.iata, a.country,
               s.reliability_score, s.score_label, s.uptime_pct,
               COUNT(r.id) AS total_routes,
               SUM(CASE WHEN r.status = 'active' THEN 1 ELSE 0 END) AS active_routes
        FROM airlines a
        JOIN airline_scores s ON s.airline_id = a.id
        JOIN routes r ON r.airline_id = a.id AND r.status = 'active'
        WHERE s.reliability_score >= 90
        GROUP BY a.id
        ORDER BY s.reliability_score DESC, active_routes DESC
        LIMIT 1
    """)

    if best:
        top_dest = query("""
            SELECT destination_name FROM routes
            WHERE airline_id = (SELECT id FROM airlines WHERE iata = ?) AND status = 'active'
            ORDER BY destination_name LIMIT 5
        """, (best['iata'],))
        best['top_destinations'] = [d['destination_name'] for d in top_dest]

    return best or {"message": "No highly reliable airlines found"}


@app.get("/api/timeline")
def list_timeline(
    airline: str = Query(None),
    limit: int = Query(50, le=500),
):
    """All timeline events, optionally filtered by airline."""
    if airline:
        events = query("""
            SELECT te.*, a.name AS airline_name, a.iata
            FROM timeline_events te
            JOIN airlines a ON a.id = te.airline_id
            WHERE UPPER(a.iata) = UPPER(?)
            ORDER BY te.event_date DESC
            LIMIT ?
        """, (airline, limit))
    else:
        events = query("""
            SELECT te.*, a.name AS airline_name, a.iata
            FROM timeline_events te
            JOIN airlines a ON a.id = te.airline_id
            ORDER BY te.event_date DESC
            LIMIT ?
        """, (limit,))
    return events


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
