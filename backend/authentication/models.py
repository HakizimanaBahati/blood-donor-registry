from django.db import models


class Profile(models.Model):
    """Read-only projection of public.profiles.

    The role is authoritative here — it is never taken from a JWT claim. Rows are
    created by the SQL function public.assign_role(), not by this application.
    """

    id = models.UUIDField(primary_key=True)
    full_name = models.CharField(max_length=200)
    role = models.CharField(max_length=20)
    hospital = models.ForeignKey(
        "hospitals.Hospital",
        db_column="hospital_id",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profiles",
    )
    created_at = models.DateTimeField(editable=False)

    class Meta:
        managed = False
        db_table = "profiles"

    def __str__(self):
        return f"{self.full_name} ({self.role})"
