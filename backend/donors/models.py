import uuid

from django.db import models

from common.constants import BLOOD_TYPES


class Donor(models.Model):
    """Read-only Django projection of public.donors (owned by SQL migrations)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=200)
    blood_type = models.CharField(max_length=3, choices=BLOOD_TYPES)
    last_donation = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=40)
    created_at = models.DateTimeField(editable=False)
    updated_at = models.DateTimeField(editable=False)

    class Meta:
        managed = False
        db_table = "donors"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.blood_type})"
