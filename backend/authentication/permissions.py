from rest_framework.permissions import BasePermission


class IsAuthenticatedUser(BasePermission):
    """Request carries a verified Supabase token with a registry profile."""

    message = "Authentication is required."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and getattr(user, "is_authenticated", False))


class IsAdminUser(BasePermission):
    message = "This action is restricted to administrators."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and getattr(user, "is_authenticated", False) and user.is_admin)


class IsHospitalUser(BasePermission):
    message = "This action is restricted to hospital accounts."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            user
            and getattr(user, "is_authenticated", False)
            and user.is_hospital
            and user.hospital_id is not None
        )
