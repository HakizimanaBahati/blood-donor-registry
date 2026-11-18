from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from common.test_helpers import (
    ADMIN_ID,
    BREAK_IT_DONOR_ID,
    ELIGIBLE_DONOR_ID,
    HOSPITAL_ONE,
    HOSPITAL_ONE_ID,
    HOSPITAL_TWO,
    HOSPITAL_TWO_ID,
    auth_headers,
    create_request,
)
from requests_app.models import BloodRequest


class BloodRequestAPITests(APITestCase):
    def test_unauthenticated_request_returns_401(self):
        response = self.client.get(reverse("request-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_hospital_creates_request_for_own_hospital(self):
        response = self.client.post(
            reverse("request-list"),
            {"blood_type": "O+", "units": 4, "notes": "[TEST] classroom"},
            format="json",
            **auth_headers(HOSPITAL_ONE_ID),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["hospital_id"], str(HOSPITAL_ONE))
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(response.data["requester_profile_id"], str(HOSPITAL_ONE_ID))

    def test_hospital_can_select_eligible_donor(self):
        response = self.client.post(
            reverse("request-list"),
            {"blood_type": "O+", "units": 1, "donor_id": str(ELIGIBLE_DONOR_ID)},
            format="json",
            **auth_headers(HOSPITAL_ONE_ID),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["donor_id"], str(ELIGIBLE_DONOR_ID))

    def test_ineligible_donor_is_rejected_with_400(self):
        response = self.client.post(
            reverse("request-list"),
            {"blood_type": "AB-", "units": 1, "donor_id": str(BREAK_IT_DONOR_ID)},
            format="json",
            **auth_headers(HOSPITAL_ONE_ID),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "ineligible_donor")
        details = response.data["error"]["details"]
        self.assertIn("not eligible", details["message"])
        self.assertEqual(str(details["days_until_eligible"]), "80")
        self.assertEqual(details["eligibility_badge"], "ineligible")

    def test_hospital_cannot_create_for_another_hospital(self):
        response = self.client.post(
            reverse("request-list"),
            {"hospital_id": str(HOSPITAL_TWO), "blood_type": "O+", "units": 1},
            format="json",
            **auth_headers(HOSPITAL_ONE_ID),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_for_explicit_hospital(self):
        response = self.client.post(
            reverse("request-list"),
            {"hospital_id": str(HOSPITAL_TWO), "blood_type": "A+", "units": 2},
            format="json",
            **auth_headers(ADMIN_ID),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["hospital_id"], str(HOSPITAL_TWO))

    def test_admin_must_supply_hospital(self):
        response = self.client.post(
            reverse("request-list"),
            {"blood_type": "A+", "units": 2},
            format="json",
            **auth_headers(ADMIN_ID),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_units_and_blood_type_return_400(self):
        headers = auth_headers(HOSPITAL_ONE_ID)
        self.assertEqual(
            self.client.post(
                reverse("request-list"), {"blood_type": "O+", "units": 0},
                format="json", **headers,
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(
                reverse("request-list"), {"blood_type": "XX", "units": 1},
                format="json", **headers,
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_hospital_sees_only_own_requests(self):
        response = self.client.get(
            reverse("request-list"), {"page_size": 100}, **auth_headers(HOSPITAL_ONE_ID)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(all(r["hospital_id"] == str(HOSPITAL_ONE) for r in response.data["results"]))

    def test_admin_sees_all_requests(self):
        response = self.client.get(
            reverse("request-list"), {"page_size": 100}, **auth_headers(ADMIN_ID)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["count"], 6)

    def test_hospital_cannot_view_another_hospitals_request(self):
        other = create_request(hospital_id=HOSPITAL_TWO)
        response = self.client.get(
            reverse("request-detail", args=[other.pk]), **auth_headers(HOSPITAL_ONE_ID)
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_and_delete_own_request(self):
        request = create_request()
        url = reverse("request-detail", args=[request.pk])
        response = self.client.patch(
            url, {"status": "fulfilled"}, format="json", **auth_headers(HOSPITAL_ONE_ID)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        request.refresh_from_db()
        self.assertEqual(request.status, "fulfilled")

        self.assertEqual(
            self.client.delete(url, **auth_headers(HOSPITAL_ONE_ID)).status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertFalse(BloodRequest.objects.filter(pk=request.pk).exists())

    def test_hospital_cannot_modify_another_hospitals_request(self):
        other = create_request(hospital_id=HOSPITAL_TWO)
        url = reverse("request-detail", args=[other.pk])
        self.assertEqual(
            self.client.patch(
                url, {"units": 99}, format="json", **auth_headers(HOSPITAL_ONE_ID)
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
