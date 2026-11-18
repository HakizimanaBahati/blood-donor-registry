from dataclasses import dataclass
from uuid import UUID

from django.core.exceptions import ValidationError

from authentication.models import Profile


@dataclass(frozen=True)
class AppUser:
    id: UUID
    full_name: str
    role: str
    hospital_id: UUID | None
    is_authenticated: bool = True

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_hospital(self) -> bool:
        return self.role == "hospital"


def app_user_from_profile(profile: Profile) -> AppUser:
    return AppUser(
        id=profile.id,
        full_name=profile.full_name,
        role=profile.role,
        hospital_id=profile.hospital_id,
    )


def get_app_user(subject: str) -> AppUser | None:
    """Resolve the application identity from a verified Supabase user id."""
    try:
        profile = (
            Profile.objects.select_related("hospital")
            .filter(pk=subject)
            .first()
        )
    except (ValidationError, ValueError):
        return None
    if profile is None or profile.role not in {"admin", "hospital"}:
        return None
    return app_user_from_profile(profile)
