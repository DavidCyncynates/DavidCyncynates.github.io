import unittest
from copy import deepcopy
from datetime import datetime, timezone

from institution_coverage import institution_coverage


class InstitutionCoverageTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 28, 18, tzinfo=timezone.utc)
        self.at = '2026-10-28T17:00:00+00:00'
        self.inst = {'id': 'uni', 'sourceIds': ['board']}
        self.sources = [{'id': 'board', 'url': 'https://example.edu/jobs', 'institutionIds': ['uni']}]
        self.check = dict(checkedAt=self.at, outcome='complete', scopeType='vacancy-list', paginationComplete=True)
        self.ledger = {'sources': {'board': {'url': 'https://example.edu/jobs', 'attempts': [self.check], 'lastFailureAt': None}}}
        self.review = dict(institutionId='uni', checkedAt='2026-10-28T17:10:00+00:00', outcome='complete',
                           coverage='Physics faculty listings, all two pages.', summary='One relevant search.',
                           requiredSourceIds=['board'], directorySourceIds=['board'], limitations=[],
                           evidence=[dict(sourceId='board', checkedAt=self.at)])

    def project(self, reviews=None):
        return institution_coverage(self.inst, self.sources, self.ledger,
                                    [self.review] if reviews is None else reviews, self.now)

    def test_completed_list_has_dated_scope(self):
        result = self.project()
        self.assertEqual(result['state'], 'complete')
        self.assertEqual(result['lastFullScanAt'], self.at)
        self.assertEqual(result['coverage'], self.review['coverage'])

    def test_advertisement_does_not_establish_directory_scan(self):
        self.check['scopeType'] = 'advertisement'
        with self.assertRaises(ValueError):
            self.project()

    def test_partial_or_unpaginated_list_cannot_be_complete(self):
        for key, value in [('outcome', 'partial'), ('paginationComplete', False)]:
            with self.subTest(key=key):
                old = self.check[key]
                self.check[key] = value
                with self.assertRaises(ValueError):
                    self.project()
                self.check[key] = old

    def test_review_requires_real_recorded_attempt(self):
        self.review['evidence'][0]['checkedAt'] = '2026-10-28T17:01:00+00:00'
        with self.assertRaises(ValueError):
            self.project()

    def test_later_failure_keeps_history_but_reopens_gap(self):
        self.ledger['sources']['board']['lastFailureAt'] = '2026-10-28T17:20:00+00:00'
        self.ledger['sources']['board']['attempts'].append(dict(checkedAt='2026-10-28T17:20:00+00:00', outcome='failed'))
        result = self.project()
        self.assertEqual(result['state'], 'partial')
        self.assertEqual(result['lastFullScanAt'], self.at)

    def test_later_partial_check_reopens_coverage_gap(self):
        self.ledger['sources']['board']['attempts'].append(dict(checkedAt='2026-10-28T17:20:00+00:00', outcome='partial', scopeType='vacancy-list'))
        self.assertEqual(self.project()['state'], 'partial')

    def test_later_complete_advertisement_reopens_directory_gap(self):
        self.ledger['sources']['board']['attempts'].append(dict(
            checkedAt='2026-10-28T17:20:00+00:00', outcome='complete',
            scopeType='advertisement', paginationComplete=True))
        result = self.project()
        self.assertEqual(result['state'], 'partial')
        self.assertEqual(result['lastFullScanAt'], self.at)

    def test_new_assessment_cannot_refresh_old_source_evidence(self):
        self.check['checkedAt'] = '2026-08-01T17:00:00+00:00'
        self.review['evidence'][0]['checkedAt'] = self.check['checkedAt']
        result = self.project()
        self.assertEqual(result['state'], 'stale')
        self.assertEqual(result['lastFullScanAt'], self.check['checkedAt'])

    def test_failure_before_review_cannot_be_ignored(self):
        self.ledger['sources']['board']['attempts'].append(dict(checkedAt='2026-10-28T17:05:00+00:00', outcome='failed'))
        with self.assertRaises(ValueError):
            self.project()

    def test_new_directory_source_needs_review(self):
        self.inst['sourceIds'].append('new-board')
        result = self.project()
        self.assertEqual(result['state'], 'partial')

    def test_retired_source_keeps_historical_review(self):
        self.sources = []
        self.inst['sourceIds'] = []
        result = self.project()
        self.assertEqual(result['state'], 'partial')
        self.assertEqual(result['lastFullScanAt'], self.at)

    def test_old_complete_scan_becomes_due(self):
        self.now = datetime(2026, 11, 27, tzinfo=timezone.utc)
        self.assertEqual(self.project()['state'], 'stale')

    def test_ad_only_history_is_partial_without_explicit_review(self):
        self.check.update(outcome='partial', scopeType='advertisement')
        self.assertEqual(self.project([])['state'], 'partial')

    def test_failed_attempt_is_not_successful_coverage(self):
        self.check['outcome'] = 'failed'
        result = self.project([])
        self.assertEqual(result['state'], 'blocked')
        self.assertIsNone(result['lastFullScanAt'])

    def test_no_attempt_is_pending(self):
        self.ledger['sources'] = {}
        self.assertEqual(self.project([])['state'], 'pending')

    def test_reversed_history_rejected(self):
        newer = deepcopy(self.review)
        newer['checkedAt'] = '2026-10-28T17:15:00+00:00'
        with self.assertRaises(ValueError):
            self.project([newer, self.review])


if __name__ == '__main__':
    unittest.main()
