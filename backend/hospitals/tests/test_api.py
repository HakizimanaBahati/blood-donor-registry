from uuid import uuid4

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from common.test_helpers import ADMIN_ID, HOSPITAL_ONE, HOSPITAL_ONE_ID, auth_headers


class HospitalAPITests(APITestCase):
    def test_admin_can_list(self):
        response = self.client.get(reverse("hospital-list"), **auth_headers(ADMIN_ID))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["count"], 3)

    def test_hospital_cannot_list(self):
        response = self.client.get(reverse("hospital-list"), **auth_headers(HOSPITAL_ONE_ID))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_and_update(self):
        response = self.client.post(
            reverse("hospital-list"),
            {"name": "[TEST] New Hospital", "location": "Testville", "phone": "+15550999009"},
            format="json",
            **auth_headers(ADMIN_ID),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        url = reverse("hospital-detail", args=[response.data["id"]])
        response = self.client.patch(
            url, {"location": "Updatedville"}, format="json", **auth_headers(ADMIN_ID)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["location"], "Updatedville")

    def test_hospital_cannot_create_or_update(self):
        response = self.client.post(
            reverse("hospital-list"),
            {"name": "[TEST] Illegal Hospital"},
            format="json",
            **auth_headers(HOSPITAL_ONE_ID),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.patch(
                reverse("hospital-detail", args=[HOSPITAL_ONE]),
                {"name": "[TEST] Changed"},
                format="json",
                **auth_headers(HOSPITAL_ONE_ID),
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_hospital_can_view_own_but_not_other_hospital(self):
        own = self.client.get(
            reverse("hospital-detail", args=[HOSPITAL_ONE]), **auth_headers(HOSPITAL_ONE_ID)
        )
        self.assertEqual(own.status_code, status.HTTP_200_OK)
        other = self.client.get(
            reverse("hospital-detail", args=[uuid4()]), **auth_headers(HOSPITAL_ONE_ID)
        )
        self.assertEqual(other.status_code, status.HTTP_404_NOT_FOUND)
