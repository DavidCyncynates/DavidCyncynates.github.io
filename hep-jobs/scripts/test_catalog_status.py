import unittest
from datetime import datetime, timezone
from catalog_status import display_state


def job(deadlines, **kwargs):
    return dict(verification='verified', deadlines=deadlines, **kwargs)


class DeadlineTests(unittest.TestCase):
    def state(self, j, now):
        return display_state(j, datetime.fromisoformat(now))

    def test_exact_hard_cutoff(self):
        j = job([dict(date='2026-11-15', time='23:59', timezone='America/Los_Angeles', kind='hard')])
        self.assertTrue(self.state(j, '2026-11-16T07:58:00+00:00')['defaultEligible'])
        self.assertFalse(self.state(j, '2026-11-16T07:59:00+00:00')['defaultEligible'])

    def test_date_only_survives_its_stated_day(self):
        j = job([dict(date='2026-11-01', kind='hard')])
        self.assertTrue(self.state(j, '2026-11-02T11:59:00+00:00')['defaultEligible'])
        self.assertFalse(self.state(j, '2026-11-02T12:00:00+00:00')['defaultEligible'])

    def test_priority_date_does_not_close_job(self):
        j = job([dict(date='2026-10-01', kind='priority')], openUntilFilled=True)
        s = self.state(j, '2026-10-28T12:00:00+00:00')
        self.assertTrue(s['defaultEligible'])
        self.assertEqual(s['status'], 'review-or-priority-date-passed')

    def test_later_national_deadline_cannot_reopen_host_eoi(self):
        j = job([dict(date='2026-10-16', kind='eoi', stage='host-eoi'), dict(date='2026-12-10', kind='hard', stage='national-application')])
        s = self.state(j, '2026-10-28T12:00:00+00:00')
        self.assertFalse(s['defaultEligible'])
        self.assertEqual(s['status'], 'deadline-passed')

    def test_soft_host_eoi_remains_visible_before_national_deadline(self):
        j = job([dict(date='2026-10-25', kind='priority', stage='host-eoi'), dict(date='2026-12-10', kind='hard', stage='national-application')])
        s = self.state(j, '2026-10-28T12:00:00+00:00')
        self.assertTrue(s['defaultEligible'])
        self.assertIsNone(s['nextMilestone'])

    def test_national_deadline_eventually_closes_soft_host_eoi(self):
        j = job([dict(date='2026-10-25', kind='priority', stage='host-eoi'), dict(date='2026-12-10', time='14:00', timezone='Europe/Madrid', kind='hard', stage='national-application', closesStage=False)])
        self.assertTrue(self.state(j, '2026-12-10T12:59:00+00:00')['defaultEligible'])
        self.assertFalse(self.state(j, '2026-12-10T13:00:00+00:00')['defaultEligible'])

    def test_review_and_closure_override_dates(self):
        j = job([dict(date='2027-01-01', kind='hard')])
        j['verification'] = 'needs-review'
        self.assertFalse(self.state(j, '2026-10-28T12:00:00+00:00')['defaultEligible'])
        j['explicitClosed'] = True
        self.assertEqual(self.state(j, '2026-10-28T12:00:00+00:00')['status'], 'closed')

    def test_listed_date_does_not_imply_hard_closure(self):
        j = job([dict(date='2026-10-01', kind='listed')])
        self.assertTrue(self.state(j, '2026-10-28T12:00:00+00:00')['defaultEligible'])

    def test_no_date_remains_honestly_unknown(self):
        self.assertEqual(self.state(job([]), '2026-10-28T12:00:00+00:00')['status'], 'date-unconfirmed')

    def test_superseded_deadline_cannot_hide_extension(self):
        j = job([dict(date='2026-10-01', kind='hard', active=False), dict(date='2026-12-01', kind='hard')])
        self.assertTrue(self.state(j, '2026-10-28T12:00:00+00:00')['defaultEligible'])

if __name__ == '__main__':
    unittest.main()
