from datetime import date, timedelta
from uuid import UUID

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from common.test_helpers import HOSPITAL_ONE, create_donor, unique_phone
from donors.models import Donor
from hospitals.models import Hospital
from requests_app.models import BloodRequest


class DomainModelTests(TestCase):
    def test_donor_creation(self):
        donor = create_donor(name="[TEST] Model Donor", blood_type="AB-")
        donor.full_clean()
        self.assertEqual(Donor.objects.get(pk=donor.pk).blood_type, "AB-")

    def test_invalid_blood_type_rejected_by_model_validation(self):
        donor = Donor(
            name="[TEST] Bad Type",
            blood_type="XX",
            phone=unique_phone(),
            last_donation=None,
        )
        with self.assertRaises(ValidationError):
            donor.full_clean()

    def test_missing_required_donor_fields_rejected(self):
        donor = Donor(name="", blood_type="O+", phone=unique_phone())
        with self.assertRaises(ValidationError):
            donor.full_clean()

    def test_valid_blood_request(self):
        request = BloodRequest(
            id=UUID("d0000000-0000-4000-8000-000000000001"),
            hospital=Hospital.objects.get(pk=HOSPITAL_ONE),
            blood_type="O+",
            units=3,
            status="pending",
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        request.full_clean()
        self.assertEqual(request.hospital.name, "[TEST] City General Hospital")

    def test_invalid_units_rejected_by_model_validation(self):
        request = BloodRequest(
            id=UUID("d0000000-0000-4000-8000-000000000002"),
            hospital=Hospital.objects.get(pk=HOSPITAL_ONE),
            blood_type="O+",
            units=0,
            status="pending",
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            request.full_clean()

    def test_foreign_key_relationship_to_hospital(self):
        request = BloodRequest(
            id=UUID("d0000000-0000-4000-8000-000000000003"),
            hospital=Hospital.objects.get(pk=HOSPITAL_ONE),
            blood_type="A+",
            units=1,
            status="pending",
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        self.assertEqual(request.hospital_id, HOSPITAL_ONE)

    def test_last_donation_accepts_date_objects(self):
        donor = create_donor(last_donation=date.today() - timedelta(days=10))
        self.assertIsInstance(donor.last_donation, date)
