"""
Calculate reliability scores for all airlines based on timeline events.
Computes uptime %, suspension/reaction lags, and composite score.
"""
import sqlite3
import os
import sys
from datetime import datetime, date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scripts.init_db import init_db, DB_PATH

# Reference date: the war started Oct 7, 2023
WAR_START = date(2023, 10, 7)
TODAY = date.today()


def score_label(score):
    if score >= 90:
        return 'excellent'
    elif score >= 70:
        return 'good'
    elif score >= 40:
        return 'average'
    else:
        return 'unreliable'


def calculate_scores():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get all airlines
    airlines = cur.execute("SELECT id, name, iata, never_suspended FROM airlines").fetchall()

    scores = []

    for al in airlines:
        aid = al['id']

        # Get timeline events for this airline
        events = cur.execute("""
            SELECT * FROM timeline_events
            WHERE airline_id = ?
            ORDER BY event_date ASC
        """, (aid,)).fetchall()

        if al['never_suspended']:
            # Never suspended — perfect score
            total_days = (TODAY - WAR_START).days
            scores.append({
                'airline_id': aid,
                'uptime_pct': 100.0,
                'suspension_lag_days': None,
                'resumption_lag_days': None,
                'still_suspended': 0,
                'reliability_score': 100.0,
                'score_label': 'excellent'
            })
            continue

        if not events:
            # No timeline data — can't calculate
            scores.append({
                'airline_id': aid,
                'uptime_pct': None,
                'suspension_lag_days': None,
                'resumption_lag_days': None,
                'still_suspended': 0,
                'reliability_score': None,
                'score_label': 'unknown'
            })
            continue

        # Find first suspension and last resumption
        first_suspension = None
        last_resumption = None
        still_suspended = True

        for ev in events:
            try:
                ev_date = date.fromisoformat(ev['event_date'])
            except:
                continue
            if ev['event_type'] == 'suspension' and first_suspension is None:
                first_suspension = ev_date
            if ev['event_type'] == 'resumption':
                last_resumption = ev_date
                still_suspended = False

        # Calculate metrics
        total_days = (TODAY - WAR_START).days

        if first_suspension and last_resumption:
            suspended_days = (last_resumption - first_suspension).days
        elif first_suspension and still_suspended:
            suspended_days = (TODAY - first_suspension).days
        else:
            suspended_days = 0

        uptime_pct = round(((total_days - suspended_days) / total_days) * 100, 1) if total_days > 0 else 0

        # Suspension lag: days from Oct 7 until suspension
        suspension_lag = (first_suspension - WAR_START).days if first_suspension else None

        # Resumption lag: days from suspension to resumption
        resumption_lag = (last_resumption - first_suspension).days if first_suspension and last_resumption else None

        # Calculate composite reliability score
        score = 100.0

        # Penalty for fast suspension (within 30 days = quick to flee)
        if suspension_lag is not None:
            if suspension_lag <= 7:
                score -= 35  # panicked
            elif suspension_lag <= 30:
                score -= 20  # fast to flee
            elif suspension_lag <= 60:
                score -= 10
            elif suspension_lag <= 90:
                score -= 5

        # Penalty for long suspension duration
        if suspended_days > 0:
            score -= (suspended_days / 30) * 5  # 5 pts per month suspended
            if suspended_days > 180:
                score -= 15  # > 6 months
            if suspended_days > 365:
                score -= 30  # > 12 months

        # Still suspended = heavy penalty
        if still_suspended and first_suspension:
            score -= 40

        # Bonus for never suspending or quick resumption
        if never_suspended := al['never_suspended']:
            score += 20
        elif last_resumption and resumption_lag and resumption_lag <= 90:
            score += 10  # resumed within 3 months

        score = max(0, min(100, round(score, 1)))

        scores.append({
            'airline_id': aid,
            'uptime_pct': uptime_pct,
            'suspension_lag_days': suspension_lag,
            'resumption_lag_days': resumption_lag,
            'still_suspended': 1 if still_suspended else 0,
            'reliability_score': score,
            'score_label': score_label(score),
        })

    # Upsert scores
    for s in scores:
        cur.execute("""
            INSERT INTO airline_scores (airline_id, uptime_pct, suspension_lag_days, resumption_lag_days, still_suspended, reliability_score, score_label, last_calculated)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(airline_id) DO UPDATE SET
                uptime_pct = excluded.uptime_pct,
                suspension_lag_days = excluded.suspension_lag_days,
                resumption_lag_days = excluded.resumption_lag_days,
                still_suspended = excluded.still_suspended,
                reliability_score = excluded.reliability_score,
                score_label = excluded.score_label,
                last_calculated = excluded.last_calculated
        """, (s['airline_id'], s['uptime_pct'], s['suspension_lag_days'],
              s['resumption_lag_days'], s['still_suspended'],
              s['reliability_score'], s['score_label']))

    conn.commit()
    conn.close()

    print(f"✓ Calculated scores for {len(scores)} airlines")
    scored = [s for s in scores if s['reliability_score'] is not None]
    if scored:
        avg = sum(s['reliability_score'] for s in scored) / len(scored)
        print(f"  Average reliability: {avg:.1f}/100")
        best = max(scored, key=lambda x: x['reliability_score'] or 0)
        worst = min(scored, key=lambda x: x['reliability_score'] or 100)
        print(f"  Best: {best['reliability_score']}/100  |  Worst: {worst['reliability_score']}/100")


if __name__ == '__main__':
    calculate_scores()
