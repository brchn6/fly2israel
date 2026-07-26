"""
FastAPI app: clean REST API for fly2israel data.
"""
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from api.db import query, query_one

app = FastAPI(
    title="fly2israel API",
    description="Track which airlines fly to/from Israel",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/airlines")
def list_airlines():
    """All airlines with route counts."""
    return query("""
        SELECT
            a.id, a.name, a.iata, a.icao, a.country,
            COUNT(r.id) AS total_routes,
            SUM(CASE WHEN r.status = 'active' THEN 1 ELSE 0 END) AS active_routes,
            SUM(CASE WHEN r.status = 'suspended' THEN 1 ELSE 0 END) AS suspended_routes,
            SUM(CASE WHEN r.status = 'seasonal' THEN 1 ELSE 0 END) AS seasonal_routes,
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
        GROUP BY a.id
        ORDER BY active_routes DESC, a.name
    """)


@app.get("/api/airlines/{iata}")
def get_airline(iata: str):
    """Single airline with its routes."""
    airline = query_one("""
        SELECT * FROM airlines
        WHERE UPPER(iata) = UPPER(?)
    """, (iata,))
    if not airline:
        return {"error": "Airline not found"}

    routes = query("""
        SELECT * FROM routes
        WHERE airline_id = ?
        ORDER BY status, destination
    """, (airline['id'],))

    airline['routes'] = routes
    return airline


@app.get("/api/routes")
def list_routes(
    status: str = Query(None, regex="^(active|suspended|seasonal|unknown)?$"),
    airline: str = Query(None, description="Filter by airline IATA code"),
    origin: str = Query(None, description="Filter by origin airport code"),
    destination: str = Query(None, description="Filter by destination airport code"),
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
    seasonal_routes = query_one("SELECT COUNT(*) AS count FROM routes WHERE status='seasonal'")['count']

    airlines_by_status = query("""
        SELECT overall_status AS status, COUNT(*) AS count
        FROM v_airline_status
        GROUP BY overall_status
    """)

    destinations = query("""
        SELECT destination, destination_name, destination_country, COUNT(*) AS airline_count
        FROM routes
        WHERE status = 'active'
        GROUP BY destination
        ORDER BY airline_count DESC
    """)

    return {
        "total_airlines": total_airlines,
        "total_routes": total_routes,
        "active_routes": active_routes,
        "suspended_routes": suspended_routes,
        "seasonal_routes": seasonal_routes,
        "airlines_by_status": {r['status']: r['count'] for r in airlines_by_status},
        "top_destinations": destinations[:10],
        "last_updated": query_one("SELECT MAX(updated_at) AS t FROM airlines")['t'],
    }


@app.get("/api/destinations")
def list_destinations():
    """All unique destinations with airline count."""
    return query("""
        SELECT destination, destination_name, destination_country,
               COUNT(*) AS airline_count,
               GROUP_CONCAT(a.name) AS airlines
        FROM routes r
        JOIN airlines a ON a.id = r.airline_id
        WHERE r.status = 'active'
        GROUP BY destination
        ORDER BY destination_name
    """)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
