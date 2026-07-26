"""
Extract airline status data from Wikipedia Ben Gurion Airport page history.
Uses efficient rvstart to find revisions at specific dates with rate limiting.
"""
import json, re, sys, os, time
import urllib.request, urllib.parse
from datetime import datetime

WIKI_API = "https://en.wikipedia.org/w/api.php"
PAGE = "Ben Gurion Airport"
HEADERS = {'User-Agent': 'fly2israel/0.1 (airline-tracker-research)'}

OUT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'research')
os.makedirs(OUT_DIR, exist_ok=True)

CALL_INTERVAL = 3.0


def api(params):
    params['format'] = 'json'
    url = WIKI_API + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(3):
        try:
            time.sleep(CALL_INTERVAL)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except Exception as e:
            print(f"  attempt {attempt+1}: {e}", file=sys.stderr)
            if attempt < 2:
                time.sleep(10)
    return None


def extract_airlines(html):
    html = re.sub(r'<ref[^>]*>.*?</ref>', '', html, flags=re.DOTALL)
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    tables = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL)
    for table in tables:
        if 'Airlines' not in table or 'Destinations' not in table:
            continue
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table, re.DOTALL)
        result = {}
        for row in rows[1:]:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(cells) < 2:
                continue
            name = re.sub(r'<[^>]+>', ' ', cells[0]).strip()
            name = re.sub(r'\s+', ' ', name).strip()
            name = re.sub(r'\[\d+\]', '', name).strip()
            if not name or name.startswith('!'):
                continue
            dest = re.sub(r'<[^>]+>', ' ', cells[1]).strip()
            dest = re.sub(r'\s+', ' ', dest).strip()
            notes = ''
            parens = re.findall(r'\(([^)]*)\)', dest)
            for p in parens:
                if any(w in p.lower() for w in ['suspend', 'resume', 'until', 'begin', 'all', 'seasonal']):
                    notes += p + '; '
            result[name] = {
                'present': True,
                'notes': notes.strip('; '),
                'destinations': dest[:200],
            }
        return result
    return {}


def find_revision_at(target_date):
    ts = target_date.strftime('%Y-%m-%dT%H:%M:%SZ')
    data = api({
        'action': 'query', 'prop': 'revisions', 'titles': PAGE,
        'rvlimit': '1', 'rvprop': 'ids|timestamp',
        'rvstart': ts, 'rvdir': 'newer',
    })
    if not data:
        return None
    pages = data.get('query', {}).get('pages', {})
    if not pages:
        return None
    revs = list(pages.values())[0].get('revisions', [])
    return revs[0]['revid'] if revs else None


def fetch_snapshot(rev_id):
    data = api({'action': 'parse', 'oldid': str(rev_id), 'prop': 'text'})
    if not data:
        return None
    return extract_airlines(data['parse']['text']['*'])


def run():
    dates = []
    d = datetime(2023, 10, 1)
    while d <= datetime.now():
        dates.append(d)
        m = d.month + 1; y = d.year
        if m > 12: m = 1; y += 1
        d = datetime(y, m, 1)

    print(f"Target: {len(dates)} dates (Oct 2023 - {datetime.now().strftime('%b %Y')})")
    print(f"Rate limit: {CALL_INTERVAL}s/call → ~{len(dates)*2*CALL_INTERVAL/60:.1f} min")
    print()

    all_snapshots = {}

    for i, target_dt in enumerate(dates):
        label = target_dt.strftime('%Y-%m-%d')
        out_file = os.path.join(OUT_DIR, f'snapshot_{label}.json')

        if os.path.exists(out_file):
            with open(out_file) as f:
                snap = json.load(f)
                all_snapshots[label] = snap['airlines']
            print(f"  [{i+1}/{len(dates)}] {label} — cached", flush=True)
            continue

        rev_id = find_revision_at(target_dt)
        if not rev_id:
            print(f"  [{i+1}/{len(dates)}] {label} — no revision", flush=True)
            continue

        airlines = fetch_snapshot(rev_id)
        if not airlines:
            print(f"  [{i+1}/{len(dates)}] {label} — fetch failed", flush=True)
            continue

        all_snapshots[label] = airlines
        with open(out_file, 'w') as f:
            json.dump({'date': label, 'revision_id': rev_id, 'airlines': airlines}, f, indent=2, ensure_ascii=False)

        n = len(airlines)
        print(f"  [{i+1}/{len(dates)}] {label} — {n} airlines (rev {rev_id})", flush=True)

    print(f"\nDone. {len(all_snapshots)} snapshots")

    # Generate timeline comparison
    if len(all_snapshots) < 2:
        print("Need at least 2 snapshots for comparison")
        return

    dates_sorted = sorted(all_snapshots.keys())
    our = [
        'El Al', 'Arkia', 'Israir', 'Delta', 'United Airlines',
        'American Airlines', 'Lufthansa', 'Swiss', 'Austrian Airlines',
        'Air France', 'KLM', 'British Airways', 'Ryanair', 'Wizz Air',
        'easyJet', 'Emirates', 'Etihad', 'Flydubai', 'Turkish Airlines',
        'Royal Jordanian', 'EgyptAir', 'Ethiopian Airlines', 'Air India',
        'Korean Air', 'Cathay Pacific', 'Hainan Airlines', 'SAS',
        'Finnair', 'LOT', 'TAROM', 'Bulgaria Air', 'airBaltic',
        'Azerbaijan Airlines', 'Vueling', 'Iberia', 'Air Europa',
        'Bluebird Airways', 'Cyprus Airways', 'TUS Airways',
        'Uzbekistan Airways',
    ]

    print(f"\n{'='*100}")
    print("TIMELINE — Green=active, Red=suspended, Yellow=resuming, Gray=not listed")
    print(f"{'='*100}")

    for name in our:
        row = []
        for dt in dates_sorted:
            airs = all_snapshots[dt]
            found = None
            for key in airs:
                if name.split()[0].lower() in key.lower():
                    found = airs[key]
                    break
            if found:
                n = found.get('notes', '').lower()
                if 'suspend' in n: row.append('🔴')
                elif 'resume' in n: row.append('🟡')
                else: row.append('🟢')
            else:
                row.append('⚪')
        print(f"{name:30s} {' '.join(row[:12])}  {' '.join(row[12:])}")

    print(f"\n🟢=active  🔴=suspended  🟡=resuming  ⚪=not listed")

    # Save combined
    combined = {'snapshots': all_snapshots, 'dates': dates_sorted, 'airlines': our}
    with open(os.path.join(OUT_DIR, 'combined_timeline.json'), 'w') as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)
    print(f"\nCombined data: {OUT_DIR}/combined_timeline.json")


if __name__ == '__main__':
    run()
