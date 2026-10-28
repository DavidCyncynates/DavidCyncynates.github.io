"""Validate research records and create the portable preliminary database.

This builds a local snapshot. It does not fetch, publish, or schedule anything.
"""
import argparse
from collections import Counter
from datetime import date, datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import sqlite3
from urllib.parse import urlparse, urlsplit, urlunsplit, parse_qsl, urlencode

from catalog_status import display_state, cutoff

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
RESEARCH = DATA / 'research'
ALIASES = {'university-of-chicago': 'chicago',
           'institute-of-physics-bhubaneswar': 'iop-bhubaneswar',
           'tata-institute-fundamental-research': 'tifr-mumbai'}


def read(name):
    return json.loads((RESEARCH / name).read_text())


def write(name, data):
    (DATA / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def normalized_fields(fields):
    terms = ' | '.join(fields).casefold()
    rules = {
        'theory': ('theory', 'theoretical', 'string', 'quantum field', 'lattice'),
        'experiment': ('experiment',),
        'cosmology': ('cosmolog',),
        'astroparticle': ('astroparticle', 'astro-particle', 'particle astrophysics'),
        'astrophysics': ('astrophys', 'astronomy'),
        'gravity': ('gravit', 'relativity'),
        'instrumentation': ('instrument', 'detector'),
        'nuclear': ('nuclear', 'heavy-ion', 'heavy ion'),
        'quantum-information': ('quantum information', 'quantum computation'),
        'ai-methods': ('artificial intelligence', 'machine learning'),
        'broad-physics': ('broad physics', 'all areas of physics'),
    }
    return [tag for tag, patterns in rules.items() if any(p in terms for p in patterns)]


def clean_url(url):
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.netloc:
        raise ValueError('Expected a public HTTP(S) source URL: ' + url)
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                       if not k.startswith('utm_')])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def build(now):
    jobs = []
    for path in sorted(RESEARCH.glob('*-jobs.json')):
        jobs.extend(json.loads(path.read_text()))
    assert len({j['id'] for j in jobs}) == len(jobs), 'Duplicate job IDs'
    resolutions = read('review-resolutions.json') if (RESEARCH / 'review-resolutions.json').exists() else {}
    locations = read('locations.json') if (RESEARCH / 'locations.json').exists() else {}
    for j in jobs:
        j.update(resolutions.get(j['id'], {}))
    sources = {s['id']: s for s in read('discovery-sources.json')}
    source_id_by_url = {}
    for s in sources.values():
        s['url'] = clean_url(s['url'])
        source_id_by_url[s['url']] = s['id']
    institutions = {}

    def add_source(url, kind, institution_id=None, metadata=None):
        url = clean_url(url)
        sid = source_id_by_url.get(url, 'source-' + hashlib.sha256(url.encode()).hexdigest()[:12])
        if sid not in sources:
            sources[sid] = dict(id=sid, url=url, kind=kind, institutionIds=[],
                                discoveredOn='2026-10-28', lastFullScan=None,
                                checkState='source-discovered', cadenceDays=7)
            source_id_by_url[url] = sid
        sources[sid].setdefault('institutionIds', [])
        if kind != 'advertisement':
            sources[sid]['kind'] = kind
        sources[sid].setdefault('roles', [])
        if kind not in sources[sid]['roles']:
            sources[sid]['roles'].append(kind)
        if institution_id and institution_id not in sources[sid]['institutionIds']:
            sources[sid]['institutionIds'].append(institution_id)
        if metadata:
            sources[sid].update({k: v for k, v in metadata.items()
                                if k not in ('url', 'kind', 'id', 'institutionIds')})
        return sid

    for j in jobs:
        j['institutionId'] = ALIASES.get(j['institutionId'], j['institutionId'])
        assert j['cycle'] == '2026-2027'
        assert j['verification'] in ('verified', 'needs-review')
        assert j['kind'] in ('formal-vacancy', 'expression-of-interest', 'fellowship-hosting')
        assert j['scope'] in ('core', 'adjacent', 'broad-physics')
        assert j['sourceUrls'] and j['cycleEvidence']
        date.fromisoformat(j['checkedOn'])
        j['sourceUrls'] = list(dict.fromkeys(clean_url(u) for u in j['sourceUrls']))
        j['fieldTags'] = normalized_fields(j['fields'])
        for d in j['deadlines']:
            date.fromisoformat(d['date'])
            assert d['kind'] in ('hard', 'priority', 'review-start', 'listed', 'eoi')
            d['sourceUrl'] = clean_url(d['sourceUrl'])
            assert d['sourceUrl'] in j['sourceUrls'], (j['id'], 'deadline source missing')
            d['cutoffAt'] = cutoff(d).isoformat()
        j['snapshotState'] = display_state(j, now)
        j['location'] = locations.get(j['institutionId'], {'latitude': None, 'longitude': None, 'precision': None,
                         'verification': 'not-geocoded', 'sourceUrl': None})
        institution_id = j['institutionId']
        inst = institutions.setdefault(institution_id, dict(
            id=institution_id, name=j['institutionName'], countryCode=j['countryCode'],
            city=j['city'], aliases=[], profile=None, profileSourceUrl=None,
            officialClassifications=[], sourceIds=[], localSearchTerms=[], notes=[]))
        if j['institutionName'] != inst['name']:
            inst['aliases'].append(j['institutionName'])
        j['sourceIds'] = [add_source(u, 'advertisement', institution_id,
                            {'lastEvidenceCheck': j['checkedOn']}) for u in j['sourceUrls']]
        for s in j.pop('institutionSources', []):
            sid = add_source(s['url'], s['kind'], institution_id,
                             {'linkVerified': s.get('verified', False)})
            if sid not in inst['sourceIds']:
                inst['sourceIds'].append(sid)

    for row in read('international-sources.json'):
        inst = institutions.setdefault(row['id'], dict(
            id=row['id'], name=row['name'], countryCode=row['countryCode'], city=row['city'],
            aliases=[], officialClassifications=[], sourceIds=[]))
        inst.update({k: row[k] for k in ('profile', 'profileSourceUrl', 'localSearchTerms', 'notes')})
        for s in row['sourcePages']:
            sid = add_source(s['url'], s['kind'], row['id'], s)
            if sid not in inst['sourceIds']:
                inst['sourceIds'].append(sid)

    carnegie = read('classifications.json')
    by_name = {c['institutionName']: c for c in carnegie}
    for inst in institutions.values():
        match_name = 'Ohio State University' if inst['name'] == 'The Ohio State University' else inst['name']
        if match_name in by_name:
            inst['officialClassifications'] = [by_name[match_name]]
        if inst['id'] == 'scripps-pitzer-natural-sciences':
            inst['officialClassifications'] = [by_name['Scripps College'], by_name['Pitzer College']]
            inst['notes'].append('Joint department: each college retains its own official classification. Do not treat the consortium as a Carnegie institution.')
        inst.setdefault('profile', None)
        inst.setdefault('profileSourceUrl', None)
        inst.setdefault('localSearchTerms', [])
        inst.setdefault('notes', [])
        inst['sourceIds'] = sorted(set(inst['sourceIds']))
        inst['location'] = locations.get(inst['id'], {'latitude': None, 'longitude': None, 'verification': 'not-geocoded'})
        if inst['countryCode'] != 'US' and inst['location'].get('profile'):
            profile = inst['location']['profile']
            inst['profileCategory'] = 'international-university' if profile == 'university' else 'research-institute'
            inst['profile'] = 'University' if profile == 'university' else 'Research institute / laboratory'
            inst['profileSourceUrl'] = inst['location']['profileSourceUrl']
        inst['coverageState'] = 'partial-record-verification' if any(j['institutionId'] == inst['id'] for j in jobs) else 'source-discovered'
        inst['lastFullScan'] = None
    jobs.sort(key=lambda j: (j['institutionName'], j['title']))
    institutions = sorted(institutions.values(), key=lambda i: i['name'])
    sources = sorted(sources.values(), key=lambda s: s['id'])
    assert len({s['url'] for s in sources}) == len(sources), 'Duplicate source URLs'
    metadata = {
        'schemaVersion': 1, 'title': 'HEP faculty opportunities: 2026–27 catalog',
        'cycle': '2026-2027', 'generatedAt': now.isoformat(), 'stage': 'initial-public-catalog',
        'seedMethod': 'Available recent findings from an existing daily-search conversation, followed by independent source verification and initial international source expansion.',
        'privacy': 'Personal application priorities, referee coordination, private documents and chat transcripts are not included.',
        'cyclePolicy': 'Evidence must connect an advertisement to applications during the 2026–27 cycle; appointment year alone is insufficient. Unresolved cycle leads remain in review.',
        'coverageLimits': ['This is an initial catalog, not an exhaustive global survey.', 'The starting leads emphasize theory, cosmology and North American institutions.', 'Experimental HEP and institutions outside North America need systematic backfill.', 'Source discovery is not a completed vacancy scan.', 'City-level coordinates are approximate, not verified campus buildings. International profiles are descriptive, not US equivalents.'],
        'counts': {'jobs': len(jobs), 'verifiedJobs': sum(j['verification'] == 'verified' for j in jobs),
                   'reviewJobs': sum(j['verification'] != 'verified' for j in jobs),
                   'defaultEligibleAtSnapshot': sum(j['snapshotState']['defaultEligible'] for j in jobs),
                   'institutions': len(institutions), 'sources': len(sources),
                   'jobCountries': len({j['countryCode'] for j in jobs}),
                   'institutionCountries': len({i['countryCode'] for i in institutions}),
                   'jobsByScope': dict(Counter(j['scope'] for j in jobs))},
        'licensing': {'locations': 'GeoNames city coordinates: CC BY 4.0; NCES/IPEDS campus points: US government data; official institution coordinates retain source attribution. See each location record.', 'classificationMetadata': 'Carnegie data: CC BY-NC-SA 4.0. Attribution and source URLs are retained in each classification record; no blanket MIT or CC BY license is applied to these imported data.',
                      'advertisements': 'Short factual descriptions and links only; original advertisements retain their existing rights.'},
        'maintenance': {'cadencePlanned': 'weekly', 'scheduled': True, 'schedule': 'Monday 11:00 Europe/Rome', 'automationId': 'refresh-hep-faculty-job-map',
                        'note': 'The existing daily-search task was read as a source and has not been modified.'},
        'snapshotWarning': 'Status is calculated at generatedAt. Re-evaluate deadlines at display time; never use a stale snapshot as a permanent closed/open flag.',
    }
    catalog = dict(metadata=metadata, institutions=institutions, jobs=jobs, sources=sources)
    write('catalog.json', catalog)
    write('jobs.json', jobs)
    write('institutions.json', institutions)
    write('sources.json', sources)
    build_sqlite(catalog)
    build_report(catalog)
    return metadata['counts']


def build_sqlite(catalog):
    output = DATA / 'catalog.sqlite'
    temp = DATA / 'catalog.sqlite.tmp'
    if temp.exists():
        temp.unlink()
    con = sqlite3.connect(temp)
    con.execute('PRAGMA foreign_keys=ON')
    con.executescript('''
      CREATE TABLE metadata (key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
      CREATE TABLE institutions (id TEXT PRIMARY KEY, name TEXT NOT NULL, country_code TEXT NOT NULL, city TEXT, record_json TEXT NOT NULL);
      CREATE TABLE sources (id TEXT PRIMARY KEY, url TEXT NOT NULL, kind TEXT NOT NULL, record_json TEXT NOT NULL);
      CREATE TABLE institution_sources (institution_id TEXT REFERENCES institutions(id), source_id TEXT REFERENCES sources(id), PRIMARY KEY(institution_id,source_id));
      CREATE TABLE jobs (id TEXT PRIMARY KEY, institution_id TEXT NOT NULL REFERENCES institutions(id), title TEXT NOT NULL, cycle TEXT NOT NULL, kind TEXT NOT NULL, scope TEXT NOT NULL, verification TEXT NOT NULL, checked_on TEXT NOT NULL, record_json TEXT NOT NULL);
      CREATE TABLE job_sources (job_id TEXT REFERENCES jobs(id), source_id TEXT REFERENCES sources(id), PRIMARY KEY(job_id,source_id));
      CREATE TABLE deadlines (job_id TEXT REFERENCES jobs(id), ordinal INTEGER NOT NULL, date TEXT NOT NULL, kind TEXT NOT NULL, time TEXT, timezone TEXT, stage TEXT, source_url TEXT NOT NULL, description TEXT NOT NULL, PRIMARY KEY(job_id,ordinal));
      CREATE INDEX jobs_by_institution ON jobs(institution_id);
      CREATE INDEX deadlines_by_date ON deadlines(date);
    ''')
    for k, v in catalog['metadata'].items():
        con.execute('INSERT INTO metadata VALUES (?,?)', (k, json.dumps(v, ensure_ascii=False)))
    for i in catalog['institutions']:
        con.execute('INSERT INTO institutions VALUES (?,?,?,?,?)', (i['id'], i['name'], i['countryCode'], i['city'], json.dumps(i, ensure_ascii=False)))
    for s in catalog['sources']:
        con.execute('INSERT INTO sources VALUES (?,?,?,?)', (s['id'], s['url'], s['kind'], json.dumps(s, ensure_ascii=False)))
    for i in catalog['institutions']:
        con.executemany('INSERT INTO institution_sources VALUES (?,?)', [(i['id'], s) for s in i['sourceIds']])
    for j in catalog['jobs']:
        con.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?)', (j['id'], j['institutionId'], j['title'], j['cycle'], j['kind'], j['scope'], j['verification'], j['checkedOn'], json.dumps(j, ensure_ascii=False)))
        con.executemany('INSERT INTO job_sources VALUES (?,?)', [(j['id'], s) for s in j['sourceIds']])
        for n, d in enumerate(j['deadlines']):
            con.execute('INSERT INTO deadlines VALUES (?,?,?,?,?,?,?,?,?)', (j['id'], n, d['date'], d['kind'], d.get('time'), d.get('timezone'), d.get('stage'), d['sourceUrl'], d['description']))
    assert not con.execute('PRAGMA foreign_key_check').fetchall()
    assert con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    con.commit()
    con.close()
    temp.replace(output)


def build_report(catalog):
    esc = html.escape
    m = catalog['metadata']
    institutions = {i['id']: i for i in catalog['institutions']}
    cards = []
    for j in catalog['jobs']:
        dates = ''.join('<li><a href="' + esc(d['sourceUrl'], quote=True) + '">' + esc(d['date']) + '</a> · ' + esc(d['kind']) + '<br><span>' + esc(d['description']) + '</span></li>' for d in j['deadlines']) or '<li>No verified date</li>'
        cls = institutions[j['institutionId']]['officialClassifications']
        class_label = '; '.join(c['institutionName'] + ': ' + (c['designation'] if c['designation'] != 'none' else 'No Carnegie research designation') + ' (2025)' for c in cls)
        state = j['snapshotState']
        notes = ''.join('<li>' + esc(note) + '</li>' for note in j['notes'])
        links = ' · '.join('<a href="' + esc(url, quote=True) + '">Source ' + str(n + 1) + '</a>' for n, url in enumerate(j['sourceUrls']))
        review_label = ' · needs review' if state['reviewRequired'] and state['status'] != 'needs-review' else ''
        cards.append('<article data-status="' + ('review' if state['reviewRequired'] else 'checked') + '"><div class="label">' + esc(j['countryCode'] + ' · ' + j['scope'] + ' · ' + j['kind']) + '</div><h2>' + esc(j['institutionName']) + '</h2><p class="title">' + esc(j['title']) + '</p><p>' + esc(j['summary']) + '</p><p class="state">' + esc(state['status'].replace('-', ' ')) + review_label + '</p><ul>' + dates + '</ul><p class="small">' + esc(class_label) + '</p><details><summary>Evidence and notes</summary><p>' + links + '</p><p>' + esc(j['cycleEvidence']) + '</p><ul>' + notes + '</ul><p>Last checked: ' + esc(j['checkedOn']) + '</p></details></article>')
    directory = []
    sources = {s['id']: s for s in catalog['sources']}
    for i in catalog['institutions']:
        links = ' · '.join('<a href="' + esc(sources[s]['url'], quote=True) + '">' + esc(sources[s]['kind']) + '</a>' for s in i['sourceIds']) or 'Source directory still to expand'
        directory.append('<tr><td>' + esc(i['name']) + '</td><td>' + esc(i['countryCode']) + '</td><td>' + links + '</td></tr>')
    counts = m['counts']
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HEP faculty catalog · 2026–27 seed</title><style>
      :root{color-scheme:light dark;--bg:#f3f1eb;--ink:#27332f;--muted:#60716b;--line:#d5dbd3;--card:#fffefa;--accent:#2a655e}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,sans-serif}main{max-width:1120px;margin:auto;padding:40px 24px}h1{font-size:28px;font-weight:600;line-height:1.3}h2{font-size:19px;margin:8px 0}a{color:var(--accent);text-underline-offset:3px}p{margin:10px 0}.intro{max-width:850px}.small,.label,li span{font-size:13px;color:var(--muted)}.label{text-transform:uppercase;letter-spacing:.06em}.state{font-weight:600}.title{font-weight:500}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,330px),1fr));gap:20px;margin-top:28px}article{background:var(--card);padding:22px;border:1px solid var(--line);border-radius:10px}article ul{padding-left:20px}li{margin:8px 0}summary{cursor:pointer;color:var(--accent)}table{border-collapse:collapse;width:100%;margin:20px 0}td,th{padding:12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}nav{display:flex;gap:16px;flex-wrap:wrap}input{font:inherit;padding:10px 12px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--ink);width:min(100%,500px);margin-top:20px}footer{margin-top:32px;border-top:1px solid var(--line);padding-top:20px}@media(prefers-color-scheme:dark){:root{--bg:#232221;--ink:#e4e3de;--muted:#aaa9a1;--line:#454641;--card:#2c2c29;--accent:#a8c8bd}}
      </style><main><div class="label">Preliminary database · 2026–2027 application cycle</div><h1>High-energy physics faculty opportunities</h1><div class="intro"><p>''' + str(counts['jobs']) + ' advertised searches and leads · ' + str(counts['verifiedJobs']) + ' verified records · ' + str(counts['reviewJobs']) + ' awaiting review · ' + str(counts['institutions']) + ''' institutions in the source directory.</p><p>This is the complete readable catalog. <a href="./">Explore the world map</a>. It includes adjacent astrophysics and broad physics searches. Closed and uncertain records remain visible here for inspection. The interactive map hides passed hard deadlines and unresolved records by default.</p><p>Snapshot: ''' + esc(m['generatedAt']) + '''. Dates below distinguish hard deadlines, priority dates and the start of review. Check the linked advertisement before applying; a passed priority date does not establish that a search has closed.</p><nav><a href="./">World map</a><a href="data/catalog.json">Complete JSON database</a><a href="data/catalog.sqlite">SQLite database</a><a href="#directory">Institution directory</a></nav><label for="search" class="small">Filter this review catalog</label><br><input id="search" type="search" placeholder="Institution, field, deadline or review note…"></div><div class="grid">''' + ''.join(cards) + '''</div><h2 id="directory">Institution source directory</h2><p>These are discovery starting points. No institution has yet received a complete cycle-wide vacancy scan.</p><table><thead><tr><th>Institution</th><th>Country</th><th>Sources</th></tr></thead><tbody>''' + ''.join(directory) + '''</tbody></table><footer><p>Carnegie classification metadata: American Council on Education and Carnegie Foundation, 2025 Carnegie Classifications. Source metadata used under <a href="https://carnegieclassifications.acenet.edu/data-center/">CC BY-NC-SA 4.0</a>; campus-level source references are retained in the database. Other advertisements retain their existing rights.</p><p>Coverage is preliminary and weighted toward theory and North America. Locations are approximate campus or city points. Wider experimental and global coverage remains in progress. The existing personal daily-search task has not been changed.</p></footer></main><script>document.querySelector('#search').addEventListener('input',e=>{const q=e.target.value.toLocaleLowerCase().trim();document.querySelectorAll('article').forEach(a=>a.hidden=!a.textContent.toLocaleLowerCase().includes(q))});</script></html>'''
    (ROOT / 'catalog.html').write_text(page)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--as-of', help='Explicit ISO timestamp including timezone; defaults to now')
    args = parser.parse_args()
    now = datetime.fromisoformat(args.as_of) if args.as_of else datetime.now(timezone.utc)
    if now.tzinfo is None:
        parser.error('--as-of must include a timezone')
    print(json.dumps(build(now), indent=2))
