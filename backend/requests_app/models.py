import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from authentication.models import Profile
from common.constants import BLOOD_TYPES, REQUEST_STATUSES
from donors.models import Donor
from hospitals.models import Hospital


class BloodRequest(models.Model):
    """Read-only Django projection of public.requests (owned by SQL migrations)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    hospital = models.ForeignKey(Hospital, db_column="hospital_id", on_delete=models.CASCADE)
    blood_type = models.CharField(max_length=3, choices=BLOOD_TYPES)
    units = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10000)]
    )
    status = models.CharField(max_length=20, choices=REQUEST_STATUSES, default="pending")
    notes = models.TextField(null=True, blank=True)
    donor = models.ForeignKey(
        Donor,
        db_column="donor_id",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blood_requests",
    )
    requester_profile = models.ForeignKey(
        Profile,
        db_column="requester_profile_id",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_requests",
    )
    created_at = models.DateTimeField(editable=False)
    updated_at = models.DateTimeField(editable=False)

    class Meta:
        managed = False
        db_table = "requests"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.blood_type} x{self.units} ({self.status})"
