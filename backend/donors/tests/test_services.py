from datetime import date, timedelta

from django.test import SimpleTestCase

from donors.services import calculate_eligibility

TODAY = date(2026, 1, 1)


class EligibilityServiceTests(SimpleTestCase):
    def check(self, days_ago, expected):
        last = None if days_ago is None else TODAY - timedelta(days=days_ago)
        return calculate_eligibility(last, today=TODAY), expected

    def test_ten_days_ago_is_ineligible_with_80_days_remaining(self):
        info, _ = self.check(10, False)
        self.assertFalse(info.eligible)
        self.assertEqual(info.days_since_last_donation, 10)
        self.assertEqual(info.days_until_eligible, 80)
        self.assertEqual(info.eligibility_badge, "ineligible")
        self.assertIn("80 more days", info.eligibility_message)

    def test_thirty_days_ago_is_ineligible(self):
        info, _ = self.check(30, False)
        self.assertFalse(info.eligible)
        self.assertEqual(info.days_until_eligible, 60)

    def test_89_days_ago_is_ineligible(self):
        info, _ = self.check(89, False)
        self.assertFalse(info.eligible)
        self.assertEqual(info.days_until_eligible, 1)
        self.assertIn("1 more day", info.eligibility_message)

    def test_exactly_90_days_ago_is_eligible(self):
        info, _ = self.check(90, True)
        self.assertTrue(info.eligible)
        self.assertEqual(info.days_until_eligible, 0)
        self.assertEqual(info.eligibility_badge, "eligible")

    def test_120_days_ago_is_eligible(self):
        info, _ = self.check(120, True)
        self.assertTrue(info.eligible)
        self.assertEqual(info.days_since_last_donation, 120)

    def test_no_donation_history_is_eligible_but_marked_preliminary(self):
        info, _ = self.check(None, True)
        self.assertTrue(info.eligible)
        self.assertFalse(info.has_donation_history)
        self.assertIsNone(info.days_since_last_donation)
        self.assertEqual(info.eligibility_badge, "no_history")
        self.assertIn("clinical screening", info.eligibility_message)
