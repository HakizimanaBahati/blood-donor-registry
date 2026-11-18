import uuid

from django.db import models


class Hospital(models.Model):
    """Read-only projection of public.hospitals (managed by Supabase SQL migrations)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=200, null=True, blank=True)
    phone = models.CharField(max_length=40, null=True, blank=True)
    created_at = models.DateTimeField(editable=False)

    class Meta:
        managed = False
        db_table = "hospitals"
        ordering = ["name"]

    def __str__(self):
        return self.name
