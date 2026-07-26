"""
Collect route data from aviation APIs.
This is a stub — will be filled when we integrate API sources.

Usage:
    python3 scripts/collect.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from api.db import get_db


def collect():
    print("🔍 collect.py — watching for API sources...")
    print("  Next steps: integrate AviationStack or AeroDataBox API")
    print("  For now, use scripts/seed.py to load curated data from data/airlines.yaml")
    # TODO: call external APIs to verify/cross-check airline status
    # TODO: update routes.last_verified
    # TODO: detect status changes and log to status_log


if __name__ == '__main__':
    collect()
