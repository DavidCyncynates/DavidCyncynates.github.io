import copy
from datetime import datetime, timedelta, timezone
import unittest

from refresh_ledger import initialize, plan_checks, record_run, sync_catalog
from validate_catalog import validate_catalog

NOW = datetime(2026, 10, 28, 15, tzinfo=timezone.utc)


def catalog():
    return dict(metadata=dict(cycle='2026-2027', generatedAt=NOW.isoformat()),
                institutions=[dict(id='test-u', name='Test University', countryCode='US', sourceIds=['source-a'])],
                sources=[dict(id='source-a', url='https://university.example/jobs', kind='recruitment',
                              institutionIds=['test-u'], cadenceDays=7, lastEvidenceCheck='2026-10-28')],
                jobs=[dict(id='faculty-a', institutionId='test-u', title='Faculty in particle theory',
                           summary='A faculty vacancy.', fields=['particle theory'], scope='core',
                           kind='formal-vacancy', cycle='2026-2027', cycleEvidence='Employer advertises the 2026–27 application cycle.',
                           verification='verified', checkedOn='2026-10-28', openUntilFilled=True,
                           sourceUrls=['https://university.example/jobs'], sourceIds=['source-a'], deadlines=[])])


def report(outcome='complete', at=NOW + timedelta(days=7), run_id='run-1', source_id='source-a'):
    return dict(runId=run_id, startedAt=(at - timedelta(minutes=5)).isoformat(), finishedAt=at.isoformat(),
                checks=[dict(sourceId=source_id, checkedAt=at.isoformat(), outcome=outcome,
                             summary='Read the advertised faculty list.' if outcome != 'failed' else 'HTTP 503; no vacancy inference.',
                             evidenceUrls=['https://university.example/jobs'] if outcome in ('complete', 'partial') else [],
                             coverage='All pages of the 2026–27 faculty search list.', paginationComplete=True)])


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.catalog = catalog()
        self.ledger = initialize(self.catalog, NOW)

    def test_seed_does_not_invent_scan_or_freshness(self):
        source = self.ledger['sources']['source-a']
        self.assertEqual(source['catalogEvidenceDate'], '2026-10-28')
        self.assertIsNone(source['lastFullScanAt'])
        self.assertIsNone(source['lastSuccessfulCheckAt'])
        self.assertEqual(self.ledger['runs'], [])

    def test_failure_preserves_prior_success_and_all_job_facts(self):
        success = record_run(self.ledger, report(), NOW + timedelta(days=7))
        failed = record_run(success, report('failed', NOW + timedelta(days=14), 'run-2'), NOW + timedelta(days=14))
        self.assertEqual(failed['jobs'], success['jobs'])
        self.assertEqual(failed['sources']['source-a']['lastFullScanAt'], success['sources']['source-a']['lastFullScanAt'])
        self.assertEqual(failed['sources']['source-a']['lastSuccessfulCheckAt'], success['sources']['source-a']['lastSuccessfulCheckAt'])
        self.assertEqual(failed['sources']['source-a']['consecutiveFailures'], 1)
        self.assertEqual(len(failed['sources']['source-a']['attempts']), 2)

    def test_partial_check_is_not_complete_scan(self):
        result = record_run(self.ledger, report('partial'), NOW + timedelta(days=7))
        self.assertIsNotNone(result['sources']['source-a']['lastSuccessfulCheckAt'])
        self.assertIsNone(result['sources']['source-a']['lastFullScanAt'])

    def test_complete_requires_actual_coverage(self):
        r = report()
        r['checks'][0]['paginationComplete'] = False
        with self.assertRaises(ValueError):
            record_run(self.ledger, r, NOW + timedelta(days=7))

    def test_duplicate_run_is_idempotent_but_cannot_rewrite_history(self):
        once = record_run(self.ledger, report(), NOW + timedelta(days=7))
        self.assertEqual(once, record_run(once, report(), NOW + timedelta(days=7)))
        with self.assertRaises(ValueError):
            record_run(once, report('failed'), NOW + timedelta(days=7))

    def test_skipped_source_does_not_advance_rotation_clock(self):
        result = record_run(self.ledger, report('skipped'), NOW + timedelta(days=7))
        self.assertIsNone(result['sources']['source-a']['lastAttemptAt'])

    def test_failed_check_cannot_close_or_reclassify_existing_job(self):
        failed = record_run(self.ledger, report('failed'), NOW + timedelta(days=7))
        changed = copy.deepcopy(self.catalog)
        changed['jobs'][0].update(verification='needs-review', checkedOn='2026-11-04')
        claim = [dict(jobId='faculty-a', sourceIds=['source-a'], checkedOn='2026-11-04', summary='Inaccessible source.')]
        with self.assertRaises(ValueError):
            sync_catalog(failed, changed, NOW + timedelta(days=7), claim)
        self.assertEqual(failed['jobs'], self.ledger['jobs'])

    def test_missing_jobs_are_rejected_not_deleted(self):
        self.catalog['jobs'] = []
        with self.assertRaises(ValueError):
            sync_catalog(self.ledger, self.catalog, NOW)

    def test_supported_revision_appends_old_facts_and_requires_new_evidence(self):
        result = record_run(self.ledger, report(), NOW + timedelta(days=7))
        self.catalog['jobs'][0].update(checkedOn='2026-11-04', explicitClosed=True, closureSourceUrl='https://university.example/jobs')
        evidence = [dict(jobId='faculty-a', sourceIds=['source-a'], checkedOn='2026-11-04', summary='Employer explicitly marks vacancy filled.')]
        synced = sync_catalog(result, self.catalog, NOW + timedelta(days=7), evidence)
        versions = synced['jobs']['faculty-a']['versions']
        self.assertEqual(len(versions), 2)
        self.assertNotIn('explicitClosed', versions[0]['record'])
        self.assertTrue(versions[1]['record']['explicitClosed'])
        self.catalog['jobs'][0]['summary'] = 'Another change without a new check.'
        with self.assertRaises(ValueError):
            sync_catalog(synced, self.catalog, NOW + timedelta(days=8), [])

    def test_new_source_is_discovered_without_fake_frontier(self):
        self.catalog['sources'].append(dict(id='source-new', url='https://example.edu/jobs', kind='recruitment'))
        result = sync_catalog(self.ledger, self.catalog, NOW)
        self.assertIsNone(result['sources']['source-new']['lastFullScanAt'])
        self.assertEqual(result['jobs'], self.ledger['jobs'])

    def test_sources_only_cannot_import_unsupported_job_change(self):
        self.catalog['sources'].append(dict(id='source-new', url='https://example.edu/jobs', kind='recruitment'))
        self.catalog['jobs'][0]['verification'] = 'needs-review'
        result = sync_catalog(self.ledger, self.catalog, NOW, sources_only=True)
        self.assertIn('source-new', result['sources'])
        self.assertEqual(result['jobs'], self.ledger['jobs'])
        self.assertIsNone(result['sources']['source-new']['lastSuccessfulCheckAt'])

    def test_source_id_cannot_reuse_another_url(self):
        self.catalog['sources'][0]['url'] = 'https://new.example/jobs'
        self.catalog['jobs'][0]['sourceUrls'] = ['https://new.example/jobs']
        with self.assertRaises(ValueError):
            sync_catalog(self.ledger, self.catalog, NOW)

    def test_rotation_failure_does_not_starve_unchecked_sources(self):
        for sid in ['source-b', 'source-c']:
            self.catalog['sources'].append(dict(id=sid, url='https://example.edu/' + sid, kind='recruitment'))
        ledger = sync_catalog(self.ledger, self.catalog, NOW)
        first = plan_checks(ledger, self.catalog, NOW, 1)
        self.assertEqual(first['rotating'][0]['sourceId'], 'source-b')
        ledger = record_run(ledger, report('failed', NOW + timedelta(days=7), source_id='source-b'), NOW + timedelta(days=7))
        second = plan_checks(ledger, self.catalog, NOW + timedelta(days=7), 1)
        self.assertEqual(second['rotating'][0]['sourceId'], 'source-c')
        self.assertEqual(second['retry'][0]['sourceId'], 'source-b')
        self.assertEqual(second['weeklyRequired'][0]['sourceId'], 'source-a')


class ValidationTests(unittest.TestCase):
    def test_unverified_coordinates_cannot_be_plotted(self):
        c = catalog()
        c['jobs'][0]['location'] = dict(latitude=40, longitude=-70, verification='approximate', sourceUrl='https://example.edu/campus')
        self.assertTrue(any('verified before plotting' in e for e in validate_catalog(c, NOW)))

    def test_map_ready_requires_verified_location_but_seed_can_wait(self):
        self.assertEqual(validate_catalog(catalog(), NOW), [])
        self.assertTrue(any('no verified map location' in e for e in validate_catalog(catalog(), NOW, True)))
        c = catalog()
        c['institutions'][0]['location'] = dict(latitude=40, longitude=-70, verification='verified', sourceUrl='https://example.edu/campus')
        self.assertEqual(validate_catalog(c, NOW, True), [])

    def test_source_id_and_evidence_url_must_match(self):
        c = catalog()
        c['jobs'][0]['sourceUrls'] = ['https://unrelated.example/job']
        self.assertTrue(any('disagree' in e for e in validate_catalog(c, NOW)))

    def test_invalid_deadline_and_future_evidence_fail(self):
        c = catalog()
        c['jobs'][0]['checkedOn'] = '2027-01-01'
        c['jobs'][0]['deadlines'] = [dict(date='2026-02-30', kind='hard', timezone='Not/AZone', description='Apply by date', sourceUrl='https://university.example/jobs')]
        errors = validate_catalog(c, NOW)
        self.assertTrue(any('in the future' in e for e in errors))
        self.assertTrue(any('invalid IANA timezone' in e for e in errors))
        self.assertTrue(any('invalid value' in e for e in errors))


if __name__ == '__main__':
    unittest.main()
