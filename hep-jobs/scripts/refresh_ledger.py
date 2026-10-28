"""Offline, append-only evidence ledger and fair source rotation for weekly refreshes.

This program never fetches sources, edits the catalog, closes jobs, or publishes.
"""
import argparse
from collections import defaultdict, deque
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile

from catalog_status import display_state
from validate_catalog import instant, public_url, validate_catalog

ROOT = Path(__file__).resolve().parents[1]
DERIVED_JOB_KEYS = {'snapshotState', 'location', 'fieldTags'}
CENTRAL_KINDS = {'discipline-board', 'application-board', 'collaboration-board',
                 'regional-board', 'society-board', 'national-programme', 'announcement-source'}


def stamp(now):
    return now.astimezone(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def facts(job):
    return {k: deepcopy(v) for k, v in job.items() if k not in DERIVED_JOB_KEYS}


def validate_input(catalog, now):
    errors = validate_catalog(catalog, now)
    if errors:
        raise ValueError('Catalog validation failed:\n' + '\n'.join(errors))


def source_entry(source, catalog, now):
    countries = {i['id']: i['countryCode'] for i in catalog['institutions']}
    return dict(id=source['id'], url=source['url'], kind=source['kind'],
                countryCodes=sorted({countries[i] for i in source.get('institutionIds', [])}),
                cadenceDays=source.get('cadenceDays', 7), inCatalog=True,
                firstRecordedAt=stamp(now), catalogEvidenceDate=source.get('lastEvidenceCheck'),
                seedReportedFullScan=source.get('lastFullScan'),
                lastAttemptAt=None, lastSuccessfulCheckAt=None, lastFullScanAt=None,
                lastFailureAt=None, consecutiveFailures=0, attempts=[])


def version(job, now, evidence=None):
    record = facts(job)
    return dict(recordedAt=stamp(now), checkedOn=job['checkedOn'], recordHash=digest(record),
                evidence=evidence, record=record)


def initialize(catalog, now):
    validate_input(catalog, now)
    return dict(schemaVersion=1, cycle='2026-2027', createdAt=stamp(now), updatedAt=stamp(now),
                seedPolicy='Imported catalog evidence dates are retained as recorded claims. No full source scan or successful fetch is inferred from discovery, job verification, or ledger initialization.',
                sources={s['id']: source_entry(s, catalog, now) for s in catalog['sources']},
                jobs={j['id']: dict(id=j['id'], versions=[version(j, now)]) for j in catalog['jobs']},
                runs=[], syncHistory=[dict(at=stamp(now), kind='seed', catalogHash=digest(catalog), jobs=len(catalog['jobs']), sources=len(catalog['sources']))])


def record_run(ledger, report, now):
    """Record observed checks without changing any job facts or evidence versions."""
    out = deepcopy(ledger)
    run_id = report.get('runId')
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError('A nonempty runId is required')
    if any(r['runId'] == run_id for r in out['runs']):
        prior = next(r for r in out['runs'] if r['runId'] == run_id)
        if prior['reportHash'] == digest(report):
            return out
        raise ValueError('runId already exists with different evidence')
    started, finished = instant(report['startedAt']), instant(report['finishedAt'])
    if not started <= finished <= now:
        raise ValueError('Run dates are reversed or in the future')
    seen = set()
    checks = report.get('checks', [])
    if not isinstance(checks, list):
        raise ValueError('checks must be an array')
    for check in checks:
        sid = check['sourceId']
        if sid not in out['sources'] or sid in seen:
            raise ValueError('Unknown or repeated source in run: ' + sid)
        seen.add(sid)
        source = out['sources'][sid]
        at = instant(check['checkedAt'])
        if not started <= at <= finished:
            raise ValueError('Check timestamp must be within its run')
        if source['lastAttemptAt'] and at < instant(source['lastAttemptAt']):
            raise ValueError('Cannot replace newer source state with an older check')
        outcome = check.get('outcome')
        if outcome not in ('complete', 'partial', 'failed', 'skipped'):
            raise ValueError('Unknown check outcome')
        if not isinstance(check.get('summary'), str) or not check['summary'].strip():
            raise ValueError('Each check needs a factual summary')
        evidence_urls = check.get('evidenceUrls', [])
        if not isinstance(evidence_urls, list) or not all(public_url(u) for u in evidence_urls):
            raise ValueError('Evidence links must be public HTTP(S) URLs')
        if outcome in ('complete', 'partial') and not evidence_urls:
            raise ValueError('Successful checks need the actual pages read')
        if outcome == 'complete' and (not check.get('coverage') or check.get('paginationComplete') is not True):
            raise ValueError('Complete scans need coverage notes and paginationComplete:true')
        event = dict(deepcopy(check), runId=run_id)
        source['attempts'].append(event)
        # Skipping is neither an attempt nor evidence of freshness; its history remains.
        if outcome != 'skipped':
            source['lastAttemptAt'] = stamp(at)
        if outcome in ('complete', 'partial'):
            source['lastSuccessfulCheckAt'] = stamp(at)
            source['consecutiveFailures'] = 0
            if outcome == 'complete':
                source['lastFullScanAt'] = stamp(at)
        elif outcome == 'failed':
            source['lastFailureAt'] = stamp(at)
            source['consecutiveFailures'] += 1
    out['runs'].append(dict(runId=run_id, startedAt=report['startedAt'], finishedAt=report['finishedAt'],
                            reportHash=digest(report), checks=deepcopy(checks), summary=report.get('summary', '')))
    out['updatedAt'] = stamp(now)
    return out


def sync_catalog(ledger, catalog, now, evidence=None, sources_only=False):
    """Append factual revisions only when backed by recorded successful checks.

    Source discovery can be synced before visiting new sources. Missing jobs fail
    closed: keep closed/expired opportunities in the catalog as archive records.
    """
    validate_input(catalog, now)
    out = deepcopy(ledger)
    job_ids = {j['id'] for j in catalog['jobs']}
    missing = set(out['jobs']) - job_ids
    if missing:
        raise ValueError('History-preserving catalog cannot remove jobs: ' + ', '.join(sorted(missing)))
    for s in out['sources'].values():
        s['inCatalog'] = False
    for source in catalog['sources']:
        sid = source['id']
        if sid not in out['sources']:
            # Preserve scan history across a deliberate ID rename for the same URL.
            previous = [s for s in out['sources'].values() if s['url'] == source['url']]
            if previous:
                raise ValueError('Source URL already has a ledger ID; retain it: ' + previous[0]['id'])
            out['sources'][sid] = source_entry(source, catalog, now)
        elif out['sources'][sid]['url'] != source['url']:
            raise ValueError('Source ID cannot be repurposed to a new URL: ' + sid)
        current = out['sources'][sid]
        current.update({k: v for k, v in source_entry(source, catalog, now).items()
                        if k in ('kind', 'countryCodes', 'cadenceDays', 'inCatalog', 'catalogEvidenceDate')})
    if sources_only:
        out['updatedAt'] = stamp(now)
        out['syncHistory'].append(dict(at=stamp(now), kind='source-registration',
                                       sourceRegistryHash=digest(catalog['sources']),
                                       sources=len(catalog['sources'])))
        return out
    claims = evidence or []
    if not isinstance(claims, list) or len({e['jobId'] for e in claims}) != len(claims):
        raise ValueError('Job evidence must be an array with unique jobIds')
    by_job = {e['jobId']: e for e in claims}
    changed = []
    for job in catalog['jobs']:
        jid = job['id']
        prior = out['jobs'].get(jid, {}).get('versions', [])
        if prior and prior[-1]['recordHash'] == digest(facts(job)):
            continue
        claim = by_job.get(jid)
        # A genuinely unresolved new lead can be retained without claiming verification.
        if not prior and job['verification'] == 'needs-review' and not claim:
            out['jobs'][jid] = dict(id=jid, versions=[version(job, now)])
            changed.append(jid)
            continue
        if not claim or not claim.get('summary') or claim.get('checkedOn') != job['checkedOn']:
            raise ValueError('Changed/verified job needs dated evidence: ' + jid)
        if prior and job['checkedOn'] < prior[-1]['checkedOn']:
            raise ValueError('Cannot roll back a job evidence date: ' + jid)
        refs = claim.get('sourceIds', [])
        if not refs or not set(refs).issubset(job['sourceIds']):
            raise ValueError('Job evidence must cite its registered sources: ' + jid)
        for sid in refs:
            s = out['sources'][sid]
            successful = [a for a in s['attempts'] if a['outcome'] in ('complete', 'partial')]
            if not successful:
                raise ValueError('No successful source check for job: ' + jid)
            check = successful[-1]
            checked = instant(check['checkedAt'])
            if checked.date().isoformat() != claim['checkedOn']:
                raise ValueError('Evidence date does not match source check: ' + jid)
            if prior and checked < instant(prior[-1]['recordedAt']):
                raise ValueError('Old source evidence cannot authorize a new revision: ' + jid)
            if s['lastFailureAt'] and instant(s['lastFailureAt']) >= checked:
                raise ValueError('Latest source failure cannot authorize a job revision: ' + jid)
        if job.get('explicitClosed'):
            closure_sources = [s for s in refs if out['sources'][s]['url'] == job.get('closureSourceUrl')]
            if not closure_sources:
                raise ValueError('Closure revision needs a successful check of its closure source: ' + jid)
        out['jobs'].setdefault(jid, dict(id=jid, versions=[]))['versions'].append(version(job, now, claim))
        changed.append(jid)
    out['updatedAt'] = stamp(now)
    out['syncHistory'].append(dict(at=stamp(now), kind='sync', catalogHash=digest(catalog), changedJobIds=changed,
                                   jobs=len(catalog['jobs']), sources=len(catalog['sources'])))
    return out


def plan_checks(ledger, catalog, now, rotation_limit=24):
    """Central boards and live jobs every week; round-robin country directory scan.

    Rotation is ordered by last ATTEMPT, so broken sources cannot starve unchecked
    institutions. Failed sources stay separately visible for retry and escalation.
    """
    if rotation_limit < 1:
        raise ValueError('rotation_limit must be positive')
    active_refs = {sid for j in catalog['jobs'] if not j.get('explicitClosed') and display_state(j, now)['status'] != 'deadline-passed' for sid in j['sourceIds']}
    high = []
    rotating = defaultdict(list)
    retry = []
    overdue = []
    for sid, s in ledger['sources'].items():
        if not s['inCatalog']:
            continue
        last = instant(s['lastAttemptAt']) if s['lastAttemptAt'] else datetime.min.replace(tzinfo=timezone.utc)
        full = instant(s['lastFullScanAt']) if s['lastFullScanAt'] else None
        row = dict(sourceId=sid, url=s['url'], kind=s['kind'], countryCodes=s['countryCodes'],
                   lastAttemptAt=s['lastAttemptAt'], lastFullScanAt=s['lastFullScanAt'])
        if s['consecutiveFailures']:
            retry.append(dict(row, failures=s['consecutiveFailures']))
        if full is None or now - full >= timedelta(days=28):
            overdue.append(sid)
        if s['kind'] in CENTRAL_KINDS or sid in active_refs:
            high.append(row)
        else:
            country = ','.join(s['countryCodes']) or 'GLOBAL'
            rotating[country].append((last, sid, row))
    queues = {k: deque(v[2] for v in sorted(rows)) for k, rows in rotating.items()}
    # Oldest country bucket first, then interleave countries for broad coverage.
    countries = sorted(queues, key=lambda k: (min(x[0] for x in rotating[k]), k))
    selected = []
    while countries and len(selected) < rotation_limit:
        next_countries = []
        for country in countries:
            if len(selected) < rotation_limit:
                selected.append(queues[country].popleft())
            if queues[country]:
                next_countries.append(country)
        countries = next_countries
    return dict(asOf=stamp(now), weeklyRequired=sorted(high, key=lambda s: s['sourceId']),
                rotating=selected, retry=retry, sourcesWithoutFullScanIn28Days=sorted(overdue),
                remainingRotationSources=sum(len(q) for q in queues.values()),
                instruction='Required sources are all weekly checks. Rotation is a minimum, not a coverage claim. Increase its budget to clear directory backlog within four weeks; record incomplete scans honestly. Classification sources need only an official release check, not a vacancy search.')


def atomic_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(handle, 'w') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('init', 'sync', 'record', 'plan'))
    parser.add_argument('--catalog', type=Path, default=ROOT / 'data/catalog.json')
    parser.add_argument('--ledger', type=Path, default=ROOT / 'data/maintenance-ledger.json')
    parser.add_argument('--report', type=Path, help='Run JSON for record; job-evidence array for sync')
    parser.add_argument('--as-of', type=instant)
    parser.add_argument('--rotation-limit', type=int, default=24)
    parser.add_argument('--sources-only', action='store_true', help='sync only: register discovered sources without importing any job changes')
    args = parser.parse_args()
    now = args.as_of or datetime.now(timezone.utc)
    try:
        if args.sources_only and args.command != 'sync':
            raise ValueError('--sources-only is supported only with sync')
        if args.command == 'init':
            if args.ledger.exists():
                raise ValueError('Ledger already exists; use sync to preserve its history')
            result = initialize(json.loads(args.catalog.read_text()), now)
        else:
            ledger = json.loads(args.ledger.read_text())
            if args.command == 'record':
                if not args.report:
                    raise ValueError('record requires --report')
                result = record_run(ledger, json.loads(args.report.read_text()), now)
            else:
                catalog = json.loads(args.catalog.read_text())
                if args.command == 'plan':
                    print(json.dumps(plan_checks(ledger, catalog, now, args.rotation_limit), indent=2))
                    raise SystemExit(0)
                result = sync_catalog(ledger, catalog, now, json.loads(args.report.read_text()) if args.report else None, args.sources_only)
        atomic_write(args.ledger, result)
        print('Ledger ' + args.command + ' completed; catalog unchanged.')
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')
