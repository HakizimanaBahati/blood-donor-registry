from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from common.test_helpers import (
    ADMIN_ID,
    BREAK_IT_DONOR_ID,
    ELIGIBLE_DONOR_ID,
    HOSPITAL_ONE_ID,
    auth_headers,
    create_donor,
    unique_phone,
)
from donors.models import Donor


class DonorAPITests(APITestCase):
    def test_list_requires_authentication(self):
        response = self.client.get(reverse("donor-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "authentication_failed")

    def test_hospital_can_list_donors_with_server_eligibility_fields(self):
        response = self.client.get(reverse("donor-list"), **auth_headers(HOSPITAL_ONE_ID))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["count"], 10)
        donor = response.data["results"][0]
        for field in (
            "eligible",
            "has_donation_history",
            "days_since_last_donation",
            "days_until_eligible",
            "eligibility_message",
            "eligibility_badge",
        ):
            self.assertIn(field, donor)
        self.assertIn(donor["eligibility_badge"], {"eligible", "ineligible", "no_history"})

    def test_filter_by_blood_type(self):
        response = self.client.get(
            reverse("donor-list"), {"blood_type": "O+"}, **auth_headers(HOSPITAL_ONE_ID)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data["count"], 0)
        self.assertTrue(all(item["blood_type"] == "O+" for item in response.data["results"]))

    def test_invalid_blood_type_returns_400(self):
        response = self.client.get(
            reverse("donor-list"), {"blood_type": "XX"}, **auth_headers(HOSPITAL_ONE_ID)
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "validation_error")

    def test_eligible_filter(self):
        response = self.client.get(
            reverse("donor-list"), {"eligible": "true", "page_size": 100},
            **auth_headers(HOSPITAL_ONE_ID),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(all(item["eligible"] for item in response.data["results"]))

    def test_invalid_eligible_value_returns_400(self):
        response = self.client.get(
            reverse("donor-list"), {"eligible": "maybe"}, **auth_headers(HOSPITAL_ONE_ID)
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sorting_and_pagination_work_together(self):
        response = self.client.get(
            reverse("donor-list"),
            {"blood_type": "O+", "eligible": "true", "ordering": "-name", "page_size": 1},
            **auth_headers(HOSPITAL_ONE_ID),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertIsNotNone(response.data["next"])
        self.assertIn("count", response.data)

    def test_admin_can_create_donor(self):
        payload = {
            "name": "[TEST] Created By Admin",
            "blood_type": "B-",
            "phone": unique_phone(),
            "last_donation": None,
        }
        response = self.client.post(
            reverse("donor-list"), payload, format="json", **auth_headers(ADMIN_ID)
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["blood_type"], "B-")
        self.assertTrue(response.data["eligible"])
        self.assertEqual(response.data["eligibility_badge"], "no_history")
        self.assertTrue(Donor.objects.filter(pk=response.data["id"]).exists())

    def test_hospital_cannot_create_donor(self):
        response = self.client.post(
            reverse("donor-list"),
            {"name": "[TEST] Nope", "blood_type": "O+", "phone": unique_phone()},
            format="json",
            **auth_headers(HOSPITAL_ONE_ID),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_phone_returns_400(self):
        response = self.client.post(
            reverse("donor-list"),
            {"name": "[TEST] Bad Phone", "blood_type": "O+", "phone": "abc"},
            format="json",
            **auth_headers(ADMIN_ID),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone", response.data["error"]["details"])

    def test_duplicate_normalised_phone_returns_400(self):
        payload = {
            "name": "[TEST] Duplicate",
            "blood_type": "O+",
            "phone": "+1 (555) 010-2001",
        }
        response = self.client.post(
            reverse("donor-list"), payload, format="json", **auth_headers(ADMIN_ID)
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_future_last_donation_returns_400(self):
        from datetime import date, timedelta

        response = self.client.post(
            reverse("donor-list"),
            {
                "name": "[TEST] Future",
                "blood_type": "O+",
                "phone": unique_phone(),
                "last_donation": date.today() + timedelta(days=1),
            },
            format="json",
            **auth_headers(ADMIN_ID),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_patch_and_delete(self):
        donor = create_donor(name="[TEST] Before")
        url = reverse("donor-detail", args=[donor.pk])
        response = self.client.patch(
            url, {"name": "[TEST] After"}, format="json", **auth_headers(ADMIN_ID)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        donor.refresh_from_db()
        self.assertEqual(donor.name, "[TEST] After")

        response = self.client.delete(url, **auth_headers(ADMIN_ID))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_hospital_cannot_patch_or_delete(self):
        donor = create_donor()
        url = reverse("donor-detail", args=[donor.pk])
        self.assertEqual(
            self.client.patch(
                url, {"name": "[TEST] Hack"}, format="json", **auth_headers(HOSPITAL_ONE_ID)
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.delete(url, **auth_headers(HOSPITAL_ONE_ID)).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_missing_donor_returns_404(self):
        response = self.client.get(
            reverse("donor-detail", args=["00000000-0000-4000-8000-000000000000"]),
            **auth_headers(HOSPITAL_ONE_ID),
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "not_found")

    def test_phone_redaction_for_hospital(self):
        ineligible = self.client.get(
            reverse("donor-detail", args=[BREAK_IT_DONOR_ID]), **auth_headers(HOSPITAL_ONE_ID)
        )
        self.assertEqual(ineligible.status_code, status.HTTP_200_OK)
        self.assertFalse(ineligible.data["eligible"])
        self.assertEqual(ineligible.data["days_until_eligible"], 80)
        self.assertIsNone(ineligible.data["phone"])

        eligible = self.client.get(
            reverse("donor-detail", args=[ELIGIBLE_DONOR_ID]), **auth_headers(HOSPITAL_ONE_ID)
        )
        self.assertEqual(eligible.status_code, status.HTTP_200_OK)
        self.assertTrue(eligible.data["eligible"])
        self.assertIsNotNone(eligible.data["phone"])

        admin = self.client.get(
            reverse("donor-detail", args=[BREAK_IT_DONOR_ID]), **auth_headers(ADMIN_ID)
        )
        self.assertIsNotNone(admin.data["phone"])
