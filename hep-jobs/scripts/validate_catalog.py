"""Offline publication checks. This validates evidence structure, not its truth."""
import argparse
from datetime import date, datetime, time, timezone
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from catalog_status import display_state

ROOT = Path(__file__).resolve().parents[1]


def instant(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timestamp needs an explicit timezone')
    return result.astimezone(timezone.utc)


def public_url(value):
    if not isinstance(value, str):
        return False
    p = urlsplit(value)
    return p.scheme in ('http', 'https') and bool(p.hostname) and not p.username and not p.password and p.hostname not in ('localhost', '127.0.0.1', '::1')


def validate_catalog(catalog, now=None, require_map_ready=False):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Validation time needs an explicit timezone')
    errors = []

    def require(condition, message):
        if not condition:
            errors.append(message)

    def parsed(value, parser, label):
        try:
            return parser(value)
        except (ValueError, TypeError, AttributeError, KeyError):
            errors.append(label + ': invalid value ' + repr(value))

    def records(key):
        rows = catalog.get(key)
        if not isinstance(rows, list):
            errors.append(key + ': expected an array')
            return {}
        out = {}
        for row in rows:
            if not isinstance(row, dict):
                errors.append(key + ': expected objects')
                continue
            rid = row.get('id', '')
            require(isinstance(rid, str) and bool(re.fullmatch(r'[a-z0-9][a-z0-9-]*', rid)), key + ': invalid ID ' + repr(rid))
            if not isinstance(rid, str):
                continue
            require(rid not in out, key + ': duplicate ID ' + rid)
            out[rid] = row
        return out

    metadata = catalog.get('metadata', {})
    require(metadata.get('cycle') == '2026-2027', 'metadata: incorrect application cycle')
    generated = parsed(metadata.get('generatedAt'), instant, 'metadata.generatedAt')
    if generated:
        require(generated <= now, 'metadata.generatedAt is in the future')
    sources, institutions, jobs = (records(k) for k in ('sources', 'institutions', 'jobs'))
    urls = set()
    for sid, source in sources.items():
        url = source.get('url')
        require(public_url(url), sid + ': source URL must be public HTTP(S)')
        if isinstance(url, str):
            require(url not in urls, sid + ': duplicate source URL')
            urls.add(url)
        require(isinstance(source.get('kind'), str) and bool(source.get('kind')), sid + ': missing source kind')
        require(isinstance(source.get('cadenceDays', 7), int) and source.get('cadenceDays', 7) > 0, sid + ': invalid cadence')
        for iid in source.get('institutionIds', []):
            require(iid in institutions, sid + ': unknown institution ' + str(iid))

    def source_refs(record, label, required=False):
        refs = record.get('sourceIds', [])
        require(isinstance(refs, list) and (bool(refs) or not required), label + ': missing source IDs')
        if not isinstance(refs, list):
            return []
        require(len(refs) == len(set(refs)), label + ': duplicate source IDs')
        for sid in refs:
            require(sid in sources, label + ': unknown source ' + str(sid))
        return refs

    def location(record, label):
        loc = record.get('location') or {}
        lat, lon = loc.get('latitude'), loc.get('longitude')
        if lat is None and lon is None:
            return False
        numeric = all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (lat, lon))
        require(numeric, label + ': coordinates must be a finite pair')
        if numeric:
            require(-90 <= lat <= 90 and -180 <= lon <= 180, label + ': coordinates outside geographic bounds')
        require(loc.get('verification') == 'verified', label + ': coordinates must be verified before plotting')
        require(public_url(loc.get('sourceUrl')), label + ': coordinates need a public source URL')
        return numeric and -90 <= lat <= 90 and -180 <= lon <= 180 and loc.get('verification') == 'verified' and public_url(loc.get('sourceUrl'))

    for iid, inst in institutions.items():
        source_refs(inst, iid)
        location(inst, iid)
        require(bool(inst.get('name')), iid + ': missing institution name')
        require(bool(re.fullmatch('[A-Z]{2}', inst.get('countryCode', ''))), iid + ': invalid country code')

    for jid, job in jobs.items():
        refs = source_refs(job, jid, required=True)
        source_urls = job.get('sourceUrls', [])
        require(isinstance(source_urls, list) and bool(source_urls), jid + ': missing source URLs')
        require(all(public_url(u) for u in source_urls), jid + ': non-public evidence URL')
        require({sources[s]['url'] for s in refs if s in sources} == set(source_urls), jid + ': source IDs and source URLs disagree')
        require(job.get('institutionId') in institutions, jid + ': unknown institution')
        require(job.get('cycle') == '2026-2027' and bool(job.get('cycleEvidence')), jid + ': missing cycle evidence')
        require(job.get('verification') in ('verified', 'needs-review'), jid + ': invalid verification')
        require(job.get('scope') in ('core', 'adjacent', 'broad-physics'), jid + ': invalid physics scope')
        require(job.get('kind') in ('formal-vacancy', 'expression-of-interest', 'fellowship-hosting'), jid + ': invalid appointment kind')
        require(bool(job.get('title')) and bool(job.get('summary')) and bool(job.get('fields')), jid + ': missing description or physics fields')
        checked = parsed(job.get('checkedOn'), date.fromisoformat, jid + '.checkedOn')
        if checked:
            require(checked <= now.date(), jid + ': evidence date is in the future')
        require(job.get('openUntilFilled') in (True, False, None), jid + ': invalid openUntilFilled')
        for key in ('explicitClosed',):
            require(key not in job or isinstance(job[key], bool), jid + ': ' + key + ' must be boolean')
        if job.get('explicitClosed'):
            require(job.get('closureSourceUrl') in source_urls, jid + ': closure requires a cited source')
        deadline_ok = True
        for d in job.get('deadlines', []):
            label = jid + ': deadline'
            if not parsed(d.get('date'), date.fromisoformat, label):
                deadline_ok = False
            require(d.get('kind') in ('hard', 'priority', 'review-start', 'listed', 'eoi'), label + ': invalid kind')
            require(d.get('sourceUrl') in source_urls, label + ': evidence source absent from job sources')
            require(bool(d.get('description')), label + ': missing meaning of deadline')
            if d.get('time'):
                clock = parsed(d['time'], time.fromisoformat, label + '.time')
                require(clock is None or clock.tzinfo is None, label + ': put timezone in the separate timezone field')
            if d.get('timezone'):
                try:
                    ZoneInfo(d['timezone'])
                except (KeyError, TypeError, ValueError):
                    errors.append(label + ': invalid IANA timezone')
                    deadline_ok = False
            for key in ('active', 'closesStage', 'closesOpportunity'):
                require(key not in d or isinstance(d[key], bool), label + ': ' + key + ' must be boolean')
        own_location = location(job, jid)
        if deadline_ok and job.get('verification') in ('verified', 'needs-review'):
            try:
                state = display_state(job, now)
                if require_map_ready and state['defaultEligible']:
                    fallback = institutions.get(job.get('institutionId'), {}).get('location', {})
                    require(own_location or (fallback.get('verification') == 'verified' and fallback.get('latitude') is not None and fallback.get('longitude') is not None), jid + ': eligible job has no verified map location')
                snapshot = job.get('snapshotState')
                if snapshot and generated:
                    expected = display_state(job, generated)
                    require(snapshot == expected, jid + ': snapshotState disagrees with evidence at generatedAt; rebuild catalog')
            except (ValueError, KeyError, TypeError):
                errors.append(jid + ': deadline status cannot be evaluated')
    return errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=ROOT / 'data/catalog.json')
    parser.add_argument('--as-of', type=instant)
    parser.add_argument('--require-map-ready', action='store_true')
    args = parser.parse_args()
    errors = validate_catalog(json.loads(args.catalog.read_text()), args.as_of, args.require_map_ready)
    if errors:
        parser.exit(1, '\n'.join(errors) + '\n')
    print('Catalog validation passed.' )
