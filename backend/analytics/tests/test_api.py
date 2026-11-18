from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from common.constants import BLOOD_TYPE_VALUES
from common.test_helpers import (
    ADMIN_ID,
    HOSPITAL_ONE_ID,
    auth_headers,
    create_donor,
    unique_phone,
)
from donors.models import Donor


class AnalyticsAPITests(APITestCase):
    def test_analytics_requires_authentication(self):
        response = self.client.get(reverse("analytics-blood-types"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_counts_are_derived_from_database(self):
        response = self.client.get(
            reverse("analytics-blood-types"), **auth_headers(ADMIN_ID)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), BLOOD_TYPE_VALUES)
        self.assertEqual(
            response.data["O+"], Donor.objects.filter(blood_type="O+").count()
        )

        create_donor(name="[TEST] Analytics Counter", blood_type="AB-", phone=unique_phone())
        response = self.client.get(
            reverse("analytics-blood-types"), **auth_headers(ADMIN_ID)
        )
        self.assertEqual(response.data["AB-"], Donor.objects.filter(blood_type="AB-").count())

    def test_hospital_can_read_analytics(self):
        response = self.client.get(
            reverse("analytics-blood-types"), **auth_headers(HOSPITAL_ONE_ID)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_summary_scopes_requests_for_hospital(self):
        response = self.client.get(
            reverse("analytics-summary"), **auth_headers(HOSPITAL_ONE_ID)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["total_donors"], 10)
        self.assertIn("eligible_donors", response.data)
        self.assertTrue(
            all(
                request["hospital_id"] == "11111111-1111-4111-8111-111111111111"
                for request in response.data["recent_requests"]
            )
        )
