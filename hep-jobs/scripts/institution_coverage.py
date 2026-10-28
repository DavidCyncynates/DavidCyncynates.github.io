"""Project dated institution reviews from the append-only source evidence.

A completed review is bounded by its recorded vacancy lists and search scope.
Reading an individual advertisement cannot establish directory coverage.
"""
from datetime import timedelta

from validate_catalog import instant


def institution_coverage(inst, sources, ledger, reviews, now):
    by_source = {s['id']: s for s in sources}
    history = ledger.get('sources', {})
    rows = [r for r in reviews if r['institutionId'] == inst['id']]
    previous = None
    for row in rows:
        at = instant(row['checkedAt'])
        if at > now or (previous is not None and at <= previous):
            raise ValueError(inst['id'] + ': review dates must be historical and increasing')
        previous = at
        if row['outcome'] not in ('complete', 'partial', 'blocked') or not row.get('coverage') or not row.get('summary'):
            raise ValueError(inst['id'] + ': incomplete institution review')
        refs = row.get('evidence', [])
        if not refs:
            raise ValueError(inst['id'] + ': review needs recorded source attempts')
        checked = {}
        for ref in refs:
            sid = ref['sourceId']
            if sid in checked:
                raise ValueError(inst['id'] + ': repeated evidence source ' + sid)
            if sid not in history or (sid in by_source and inst['id'] not in by_source[sid].get('institutionIds', [])):
                raise ValueError(inst['id'] + ': unrelated review source ' + sid)
            attempts = history.get(sid, {}).get('attempts', [])
            found = [a for a in attempts if instant(a['checkedAt']) == instant(ref['checkedAt'])]
            if not found or instant(ref['checkedAt']) > at:
                raise ValueError(inst['id'] + ': review evidence is not in the ledger')
            checked[sid] = found[-1]
        required = row.get('requiredSourceIds', [])
        if row['outcome'] == 'complete':
            if not required or not set(required).issubset(checked):
                raise ValueError(inst['id'] + ': complete review needs vacancy-list evidence')
            if not all(checked[s]['outcome'] == 'complete' and checked[s].get('scopeType') == 'vacancy-list'
                       and checked[s].get('paginationComplete') is True for s in required):
                raise ValueError(inst['id'] + ': advertisements or partial lists cannot establish complete coverage')
            for sid in required:
                newer = [a for a in history[sid]['attempts'] if a['outcome'] != 'skipped'
                         and instant(checked[sid]['checkedAt']) < instant(a['checkedAt']) <= at]
                if newer:
                    raise ValueError(inst['id'] + ': complete review cites superseded source evidence')
        if not set(row.get('directorySourceIds', [])).issubset(history):
            raise ValueError(inst['id'] + ': unknown directory source in review')

    def scan_time(row):
        refs = row['evidence']
        if row['outcome'] == 'complete':
            # All required lists must be fresh. A new assessment cannot renew
            # an older fetch, and the oldest required list bounds coverage.
            refs = [r for r in refs if r['sourceId'] in row['requiredSourceIds']]
            return min(refs, key=lambda r: instant(r['checkedAt']))['checkedAt']
        return max(refs, key=lambda r: instant(r['checkedAt']))['checkedAt']

    full = [r for r in rows if r['outcome'] == 'complete']
    result = dict(state='pending', checkedAt=None, lastFullScanAt=scan_time(full[-1]) if full else None,
                  coverage=None, summary=None, limitations=[], evidenceUrls=[])
    if rows:
        latest = rows[-1]
        result.update(state=latest['outcome'], checkedAt=scan_time(latest), reviewedAt=latest['checkedAt'], coverage=latest['coverage'],
                      summary=latest['summary'], limitations=list(latest.get('limitations', [])),
                      evidenceUrls=list(dict.fromkeys(history[r['sourceId']]['url'] for r in latest['evidence'])))
        if result['state'] == 'complete':
            new_sources = set(inst['sourceIds']) - set(latest.get('directorySourceIds', []))
            incomplete = []
            for sid in latest['requiredSourceIds']:
                attempts = [a for a in history[sid]['attempts'] if a['outcome'] != 'skipped']
                last = max(attempts, key=lambda a: instant(a['checkedAt']))
                latest_list_complete = (last['outcome'] == 'complete'
                                        and last.get('scopeType') == 'vacancy-list'
                                        and last.get('paginationComplete') is True)
                if instant(last['checkedAt']) > instant(latest['checkedAt']) and not latest_list_complete:
                    incomplete.append(sid)
            retired = set(latest['requiredSourceIds']) - set(by_source)
            if new_sources or incomplete or retired:
                result['state'] = 'partial'
                result['limitations'].append('Changed directory sources or subsequent incomplete checks require another review.')
            elif now - instant(result['lastFullScanAt']) > timedelta(days=28):
                result['state'] = 'stale'
                result['limitations'].append('The last completed scan is over four weeks old.')
    else:
        attempts = [a for sid in inst['sourceIds'] for a in history.get(sid, {}).get('attempts', [])
                    if a['outcome'] != 'skipped']
        if attempts:
            last = max(attempts, key=lambda a: instant(a['checkedAt']))
            result.update(state='partial' if any(a['outcome'] in ('complete', 'partial') for a in attempts) else 'blocked',
                          checkedAt=last['checkedAt'], summary='Source checks recorded; institution review not yet completed.')
    return result
