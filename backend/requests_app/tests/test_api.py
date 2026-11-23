from django.db import IntegrityError, connection, transaction
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


NOTES_LIMIT = 1000
OVERSIZE_NOTES = "x" * (NOTES_LIMIT + 1)


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
        # With RLS active (production-like role), the other hospital is not
        # visible to the serializer's PrimaryKeyRelatedField, which rejects it
        # with 400 before the explicit ownership check can return 403. Without
        # RLS (legacy local role), the 403 path is reached. Both deny the write;
        # neither response may advertise a created request.
        self.assertIn(
            response.status_code,
            (status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN),
        )
        self.assertNotIn("id", response.data)

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

    def _assert_notes_validation_error(self, response):
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "validation_error")
        self.assertIn("notes", response.data["error"]["details"])

    def test_r1_post_notes_at_limit_succeeds(self):
        notes = "x" * NOTES_LIMIT
        response = self.client.post(
            reverse("request-list"),
            {"blood_type": "O+", "units": 1, "notes": notes},
            format="json",
            **auth_headers(HOSPITAL_ONE_ID),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["notes"]), NOTES_LIMIT)
        created = BloodRequest.objects.get(pk=response.data["id"])
        self.assertEqual(created.notes, notes)

    def test_r2_post_notes_over_limit_returns_validation_error(self):
        response = self.client.post(
            reverse("request-list"),
            {"blood_type": "O+", "units": 1, "notes": OVERSIZE_NOTES},
            format="json",
            **auth_headers(HOSPITAL_ONE_ID),
        )
        self._assert_notes_validation_error(response)
        self.assertNotIn("id", response.data)
        self.assertFalse(BloodRequest.objects.filter(notes=OVERSIZE_NOTES).exists())

    def test_r3_patch_notes_at_limit_succeeds(self):
        request_obj = create_request()
        notes = "y" * NOTES_LIMIT
        response = self.client.patch(
            reverse("request-detail", args=[request_obj.pk]),
            {"notes": notes},
            format="json",
            **auth_headers(HOSPITAL_ONE_ID),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        request_obj.refresh_from_db()
        self.assertEqual(request_obj.notes, notes)
        self.assertEqual(len(request_obj.notes), NOTES_LIMIT)

    def test_r4_patch_notes_over_limit_preserves_stored_value(self):
        original_notes = "[TEST] original notes"
        request_obj = create_request(notes=original_notes)
        response = self.client.patch(
            reverse("request-detail", args=[request_obj.pk]),
            {"notes": OVERSIZE_NOTES},
            format="json",
            **auth_headers(HOSPITAL_ONE_ID),
        )
        self._assert_notes_validation_error(response)
        request_obj.refresh_from_db()
        self.assertEqual(request_obj.notes, original_notes)

    def test_r5_null_and_blank_notes_remain_valid(self):
        for value, expected in ((None, None), ("", "")):
            with self.subTest(notes=value):
                response = self.client.post(
                    reverse("request-list"),
                    {"blood_type": "O+", "units": 1, "notes": value},
                    format="json",
                    **auth_headers(HOSPITAL_ONE_ID),
                )
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                self.assertEqual(response.data["notes"], expected)

        request_obj = create_request()
        url = reverse("request-detail", args=[request_obj.pk])
        for value, expected in ((None, None), ("", "")):
            with self.subTest(notes=value):
                response = self.client.patch(
                    url,
                    {"notes": value},
                    format="json",
                    **auth_headers(HOSPITAL_ONE_ID),
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                request_obj.refresh_from_db()
                self.assertEqual(request_obj.notes, expected)

    def test_r6_oversize_notes_validation_is_role_independent(self):
        cases = (
            ("hospital", auth_headers(HOSPITAL_ONE_ID), HOSPITAL_ONE),
            ("admin", auth_headers(ADMIN_ID), HOSPITAL_TWO),
        )
        for role, headers, hospital_id in cases:
            with self.subTest(role=role, operation="post"):
                response = self.client.post(
                    reverse("request-list"),
                    {
                        "hospital_id": str(hospital_id),
                        "blood_type": "O+",
                        "units": 1,
                        "notes": OVERSIZE_NOTES,
                    },
                    format="json",
                    **headers,
                )
                self._assert_notes_validation_error(response)

            with self.subTest(role=role, operation="patch"):
                request_obj = create_request(hospital_id=hospital_id)
                response = self.client.patch(
                    reverse("request-detail", args=[request_obj.pk]),
                    {"notes": OVERSIZE_NOTES},
                    format="json",
                    **headers,
                )
                self._assert_notes_validation_error(response)

    def test_r7_database_still_rejects_oversize_notes(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                create_request(notes=OVERSIZE_NOTES)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM public.requests WHERE length(notes) > %s",
                [NOTES_LIMIT],
            )
            self.assertEqual(cursor.fetchone()[0], 0)

    def test_r8_unicode_notes_use_character_count(self):
        response = self.client.post(
            reverse("request-list"),
            {"blood_type": "O+", "units": 1, "notes": "Ω" * NOTES_LIMIT},
            format="json",
            **auth_headers(HOSPITAL_ONE_ID),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["notes"]), NOTES_LIMIT)

        response = self.client.post(
            reverse("request-list"),
            {"blood_type": "O+", "units": 1, "notes": "Ω" * (NOTES_LIMIT + 1)},
            format="json",
            **auth_headers(HOSPITAL_ONE_ID),
        )
        self._assert_notes_validation_error(response)

    def test_r9_oversize_notes_error_envelope_does_not_leak_details(self):
        response = self.client.post(
            reverse("request-list"),
            {"blood_type": "O+", "units": 1, "notes": OVERSIZE_NOTES},
            format="json",
            **auth_headers(HOSPITAL_ONE_ID),
        )
        self._assert_notes_validation_error(response)
        self.assertEqual(
            response.data["error"]["message"],
            "The request contains invalid data.",
        )

        payload = str(response.data).lower()
        forbidden_fragments = (
            "traceback",
            "stack trace",
            "sqlstate",
            "psycopg",
            "constraint",
            "requests_notes_length",
            "select ",
            "insert ",
            "password",
            "secret",
            "token",
        )
        for fragment in forbidden_fragments:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, payload)
