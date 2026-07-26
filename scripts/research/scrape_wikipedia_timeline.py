"""
Extract airline status data from Wikipedia Ben Gurion Airport page.
Saves structured data + fetches historical snapshots with rate limiting.
"""
import json, re, sys, os, time
import urllib.request, urllib.parse
from datetime import datetime

WIKI_API = "https://en.wikipedia.org/w/api.php"
PAGE = "Ben Gurion Airport"
HEADERS = {'User-Agent': 'fly2israel-research/0.1 (airline-tracker-project)'}

OUT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'research')
os.makedirs(OUT_DIR, exist_ok=True)


def wiki_call(params):
    """Call Wikipedia API with rate limiting."""
    params['format'] = 'json'
    url = WIKI_API + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        time.sleep(2.5)  # Rate limit: 1 call per 2.5 seconds
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  ⚠ {e}", file=sys.stderr)
        return None


def extract_airlines_from_html(html):
    """Extract airline names + notes from parsed Wikipedia HTML."""
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
            
            # Extract suspension/resumption notes from destination text
            notes = ''
            parens = re.findall(r'\(([^)]*)\)', dest)
            for p in parens:
                if any(w in p.lower() for w in ['suspend','resume','until','begin','all','seasonal']):
                    notes += p + '; '
            
            result[name] = {
                'present': True,
                'notes': notes.strip('; '),
                'destinations': dest[:200],
            }
        return result
    return {}


def fetch_current_snapshot():
    """Get the current airline list from the Ben Gurion page."""
    print("Fetching current Ben Gurion Airport page...")
    data = wiki_call({'action': 'parse', 'page': PAGE, 'prop': 'text'})
    if not data:
        return {}
    html = data['parse']['text']['*']
    airlines = extract_airlines_from_html(html)
    print(f"  → {len(airlines)} airlines found")
    
    # Save
    snapshot = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'airlines': airlines,
        'source': 'Wikipedia Ben Gurion Airport page'
    }
    with open(os.path.join(OUT_DIR, 'snapshot_current.json'), 'w') as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    
    return airlines


def get_historical_revision_ids():
    """Get revision IDs for key dates (quarterly since Oct 2023)."""
    target_dates = []
    for year in range(2023, 2027):
        for month in [1, 4, 7, 10]:
            d = datetime(year, month, 1)
            if d >= datetime(2023, 10, 1) and d <= datetime.now():
                target_dates.append(d)
    
    # Get all revision timestamps
    print(f"\nFetching revision history ({len(target_dates)} target dates)...")
    
    revision_map = {}
    rvcontinue = None
    
    while True:
        params = {
            'action': 'query',
            'prop': 'revisions',
            'titles': PAGE,
            'rvlimit': '500',
            'rvprop': 'ids|timestamp',
            'rvdir': 'newer',  # Oldest first
        }
        if rvcontinue:
            params['rvcontinue'] = rvcontinue
        
        data = wiki_call(params)
        if not data:
            break
        
        pages = data.get('query', {}).get('pages', {})
        if not pages:
            break
        
        for rev in list(pages.values())[0].get('revisions', []):
            ts = rev['timestamp']
            revid = rev['revid']
            
            # Check if this revision matches any target date
            for td in target_dates:
                td_str = td.strftime('%Y-%m-%d')
                if td_str not in revision_map:
                    # We want first revision ON or AFTER this date
                    if ts >= td_str:
                        revision_map[td_str] = revid
        
        cont = data.get('continue', {})
        rvcontinue = cont.get('rvcontinue')
        if not rvcontinue:
            break
    
    print(f"  Found {len(revision_map)} matching revisions")
    return revision_map


def fetch_historical_snapshots(revision_map):
    """Fetch airline data for each historical revision."""
    for date_str in sorted(revision_map.keys()):
        rev_id = revision_map[date_str]
        out_file = os.path.join(OUT_DIR, f'snapshot_{date_str}.json')
        if os.path.exists(out_file):
            continue
        
        print(f"\n📄 {date_str} (rev {rev_id})...", end=' ', flush=True)
        data = wiki_call({'action': 'parse', 'oldid': str(rev_id), 'prop': 'text'})
        if not data:
            print("FAILED")
            continue
        
        html = data['parse']['text']['*']
        airlines = extract_airlines_from_html(html)
        print(f"{len(airlines)} airlines")
        
        snapshot = {
            'date': date_str,
            'revision_id': rev_id,
            'airlines': airlines,
        }
        with open(out_file, 'w') as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Saved to {OUT_DIR}/")


def build_comparison():
    """Compare snapshots to find status changes."""
    import glob
    files = sorted(glob.glob(os.path.join(OUT_DIR, 'snapshot_*.json')))
    
    our_airlines = [
        'El Al', 'Arkia', 'Israir', 'Delta Air Lines', 'United Airlines',
        'American Airlines', 'Lufthansa', 'Swiss', 'Austrian Airlines',
        'Air France', 'KLM', 'British Airways', 'Ryanair', 'Wizz Air',
        'easyJet', 'Emirates', 'Etihad', 'Flydubai', 'Turkish Airlines',
        'Royal Jordanian', 'EgyptAir', 'Ethiopian Airlines', 'Air India',
        'Korean Air', 'Cathay Pacific', 'Hainan Airlines', 'SAS',
        'Finnair', 'LOT', 'TAROM', 'Bulgaria Air', 'airBaltic',
        'Azerbaijan Airlines', 'Vueling', 'Iberia', 'Air Europa',
        'Bluebird Airways', 'Cyprus Airways', 'TUS Airways',
        'Uzbekistan Airways', 'Sundor'
    ]
    
    snapshots = {}
    for f in files:
        with open(f) as fh:
            data = json.load(fh)
            snapshots[data['date']] = data['airlines']
    
    dates = sorted(snapshots.keys())
    print(f"\n\n{'='*90}")
    print("AIRLINE TIMELINE FROM WIKIPEDIA SNAPSHOTS")
    print(f"{'='*90}")
    
    for name in our_airlines:
        timeline = []
        for dt in dates:
            airs = snapshots[dt]
            found = None
            for key in airs:
                if name.split()[0].lower() in key.lower():
                    found = airs[key]
                    break
            if found:
                notes = found.get('notes', '')
                if 'suspend' in notes.lower():
                    timeline.append('🛑')
                elif 'resume' in notes.lower():
                    timeline.append('🔜')
                else:
                    timeline.append('✅')
            else:
                timeline.append('⬜')
        
        print(f"\n{name:30s} {' '.join(timeline)}")


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else 'current'
    
    if action == 'current':
        fetch_current_snapshot()
    elif action == 'history':
        revs = get_historical_revision_ids()
        fetch_historical_snapshots(revs)
        build_comparison()
    elif action == 'compare':
        build_comparison()
    else:
        print("Usage: python3 scrape_wikipedia_timeline.py [current|history|compare]")


if __name__ == '__main__':
    main()
