"""
Generate timeline.yaml from Wikipedia snapshot data.
Automatically detects suspension/resumption events from monthly snapshots.
"""
import json, os, sys
from datetime import datetime, timedelta

SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'research')
OUTPUT = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'timeline.yaml')


def load_snapshots():
    """Load all snapshot files."""
    import glob
    files = sorted(glob.glob(os.path.join(SNAPSHOT_DIR, 'snapshot_2*.json')))
    snapshots = {}
    for f in files:
        with open(f) as fh:
            data = json.load(fh)
            snapshots[data['date']] = data['airlines']
    return snapshots


def find_airline(airlines, name):
    """Find airline in snapshot by name prefix."""
    prefix = name.split()[0].lower()
    for key in airlines:
        if prefix in key.lower():
            return airlines[key]
    return None


def guess_date(prev_date, curr_date):
    """Estimate event date as midpoint between two snapshot dates."""
    if isinstance(prev_date, str):
        prev_date = datetime.strptime(prev_date, '%Y-%m-%d')
    if isinstance(curr_date, str):
        curr_date = datetime.strptime(curr_date, '%Y-%m-%d')
    mid = prev_date + (curr_date - prev_date) / 2
    return mid.strftime('%Y-%m-%d')


def classify(airline_data):
    """Classify an airline's status in a snapshot."""
    if airline_data is None:
        return 'absent'
    notes = airline_data.get('notes', '').lower()
    if 'suspend' in notes and 'resume' not in notes:
        return 'suspended'
    elif 'resume' in notes:
        return 'resuming'
    else:
        return 'active'


def generate_timeline():
    snapshots = load_snapshots()
    dates = sorted(snapshots.keys())
    print(f"Loaded {len(dates)} snapshots")

    our_list = [
        ('El Al', 'LY'), ('Arkia', 'IZ'), ('Israir', '6H'),
        ('Delta', 'DL'), ('United Airlines', 'UA'), ('American Airlines', 'AA'),
        ('Lufthansa', 'LH'), ('Swiss', 'LX'), ('Austrian Airlines', 'OS'),
        ('Air France', 'AF'), ('KLM', 'KL'), ('British Airways', 'BA'),
        ('Ryanair', 'FR'), ('Wizz Air', 'W6'), ('easyJet', 'U2'),
        ('Emirates', 'EK'), ('Etihad', 'EY'), ('Flydubai', 'FZ'),
        ('Turkish Airlines', 'TK'), ('Royal Jordanian', 'RJ'), ('EgyptAir', 'MS'),
        ('Ethiopian Airlines', 'ET'), ('Air India', 'AI'),
        ('Korean Air', 'KE'), ('Cathay Pacific', 'CX'), ('Hainan Airlines', 'HU'),
        ('Scandinavian Airlines', 'SK'), ('Finnair', 'AY'),
        ('LOT Polish Airlines', 'LO'), ('TAROM', 'RO'),
        ('Bulgaria Air', 'FB'), ('airBaltic', 'BT'),
        ('Azerbaijan Airlines', 'J2'), ('Vueling', 'VY'),
        ('Iberia', 'IB'), ('Air Europa', 'UX'),
        ('Bluebird Airways', 'BZ'), ('Cyprus Airways', 'CY'),
        ('TUS Airways', 'U8'), ('Uzbekistan Airways', 'HY'),
    ]

    timeline = []

    for name, iata in our_list:
        # Get status at each date
        statuses = []
        for dt in dates:
            ad = find_airline(snapshots[dt], name)
            statuses.append((dt, ad, classify(ad)))

        # Check if never suspended
        suspended_ever = any(s == 'suspended' for _, _, s in statuses)
        # Check if mostly active with just notes
        absent_count = sum(1 for _, _, s in statuses if s == 'absent')
        active_count = sum(1 for _, _, s in statuses if s == 'active')

        # Detect events
        events = []
        for i in range(1, len(statuses)):
            prev_dt, prev_ad, prev_s = statuses[i-1]
            curr_dt, curr_ad, curr_s = statuses[i]

            if prev_s == 'active' and curr_s == 'suspended':
                events.append({
                    'date': guess_date(prev_dt, curr_dt),
                    'event_type': 'suspension',
                    'status_before': 'active',
                    'status_after': 'suspended',
                    'source': 'Wikipedia Ben Gurion Airport page snapshots',
                    'notes': f'Suspended between {prev_dt} and {curr_dt}'
                })
            elif prev_s == 'suspended' and curr_s == 'active':
                events.append({
                    'date': guess_date(prev_dt, curr_dt),
                    'event_type': 'resumption',
                    'status_before': 'suspended',
                    'status_after': 'active',
                    'source': 'Wikipedia Ben Gurion Airport page snapshots',
                    'notes': f'Resumed between {prev_dt} and {curr_dt}'
                })
            elif prev_s == 'active' and curr_s == 'resuming':
                # Resuming = notes say "resumes [date]" but not yet active
                events.append({
                    'date': guess_date(prev_dt, curr_dt),
                    'event_type': 'notice',
                    'status_before': 'active',
                    'status_after': 'active',
                    'source': 'Wikipedia Ben Gurion Airport page snapshots',
                    'notes': f'Scheduled resumption noted between {prev_dt} and {curr_dt}'
                })
            elif prev_s == 'suspended' and curr_s == 'resuming':
                events.append({
                    'date': guess_date(prev_dt, curr_dt),
                    'event_type': 'notice',
                    'status_before': 'suspended',
                    'status_after': 'suspended',
                    'source': 'Wikipedia Ben Gurion Airport page snapshots',
                    'notes': f'Resumption announced between {prev_dt} and {curr_dt}'
                })
            elif prev_s == 'absent' and curr_s != 'absent':
                events.append({
                    'date': guess_date(prev_dt, curr_dt),
                    'event_type': 'resumption',
                    'status_before': 'suspended',
                    'status_after': 'active',
                    'source': 'Wikipedia Ben Gurion Airport page snapshots',
                    'notes': f'Reappeared in table between {prev_dt} and {curr_dt} (was absent)'
                })
            elif prev_s != 'absent' and curr_s == 'absent':
                events.append({
                    'date': guess_date(prev_dt, curr_dt),
                    'event_type': 'suspension',
                    'status_before': 'active',
                    'status_after': 'suspended',
                    'source': 'Wikipedia Ben Gurion Airport page snapshots',
                    'notes': f'Disappeared from table between {prev_dt} and {curr_dt}'
                })

        # Determine if never suspended
        never_suspended = (absent_count < 5 and not suspended_ever and active_count > len(dates) * 0.7)

        entry = {
            'airline': name,
            'iata': iata,
            'never_suspended': never_suspended,
            'events': events,
        }
        timeline.append(entry)

        n = len(events)
        emoji = '✅' if never_suspended else f'{n} events' if n > 0 else '⚠️ no data'
        print(f"  {name:25s} ({iata:2s}): {emoji}")

    # Write timeline.yaml
    with open(OUTPUT, 'w') as f:
        f.write("# fly2israel — Historical Timeline\n")
        f.write(f"# Auto-generated from {len(dates)} Wikipedia snapshots\n")
        f.write(f"# Source: https://en.wikipedia.org/wiki/Ben_Gurion_Airport\n")
        f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("# Dates are midpoints between monthly snapshot observations (±15 days)\n")
        f.write("\ntimeline:\n")
        
        for entry in timeline:
            f.write(f"\n  - airline: \"{entry['airline']}\"\n")
            f.write(f"    iata: \"{entry['iata']}\"\n")
            f.write(f"    never_suspended: {str(entry['never_suspended']).lower()}\n")
            f.write(f"    events:\n")
            if entry['events']:
                for ev in entry['events']:
                    f.write(f"      - date: \"{ev['date']}\"\n")
                    f.write(f"        event_type: \"{ev['event_type']}\"\n")
                    f.write(f"        status_before: \"{ev['status_before']}\"\n")
                    f.write(f"        status_after: \"{ev['status_after']}\"\n")
                    f.write(f"        source: \"{ev['source']}\"\n")
                    f.write(f"        notes: \"{ev['notes']}\"\n")
            else:
                f.write(f"      - date: \"2023-10-07\"\n")
                f.write(f"        event_type: \"maintained\"\n")
                f.write(f"        status_before: \"active\"\n")
                f.write(f"        status_after: \"active\"\n")
                f.write(f"        source: \"Wikipedia Ben Gurion Airport page\"\n")
                f.write(f"        notes: \"Operating consistently through period\"\n")

    print(f"\n✅ Wrote {OUTPUT}")
    total_events = sum(len(e['events']) for e in timeline)
    print(f"   {len(timeline)} airlines, {total_events} total events")


if __name__ == '__main__':
    generate_timeline()
