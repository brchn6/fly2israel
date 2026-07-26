"""
SQLite DB helper for the FastAPI app.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'airlines.db')


def get_db():
    """Return a connection with row_factory set."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def query(sql, params=None):
    """Convenience: run a query and return list of dicts."""
    conn = get_db()
    cur = conn.execute(sql, params or [])
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def query_one(sql, params=None):
    """Convenience: run a query and return one dict or None."""
    conn = get_db()
    cur = conn.execute(sql, params or [])
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None
