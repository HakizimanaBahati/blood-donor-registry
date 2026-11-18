from datetime import timedelta

from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter

from authentication.permissions import IsAdminUser, IsAuthenticatedUser
from common.constants import BLOOD_TYPE_VALUES
from donors.models import Donor
from donors.serializers import DonorSerializer
from donors.services import MIN_DAYS_BETWEEN_DONATIONS


class DonorQuerySetMixin:
    """Validates and applies query parameters shared by donor list endpoints."""

    def filtered_queryset(self):
        queryset = Donor.objects.all()
        cutoff = timezone.localdate() - timedelta(days=MIN_DAYS_BETWEEN_DONATIONS)
        queryset = queryset.annotate(
            is_eligible=Case(
                When(last_donation__isnull=True, then=Value(1)),
                When(last_donation__lte=cutoff, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )

        params = self.request.query_params
        blood_type = params.get("blood_type")
        if blood_type is not None:
            if blood_type not in BLOOD_TYPE_VALUES:
                raise ValidationError(
                    {
                        "blood_type": (
                            "Invalid blood type. Use one of: " + ", ".join(sorted(BLOOD_TYPE_VALUES))
                        )
                    }
                )
            queryset = queryset.filter(blood_type=blood_type)

        eligible = params.get("eligible")
        if eligible is not None:
            normalized = eligible.strip().lower()
            if normalized not in {"true", "false", "1", "0"}:
                raise ValidationError({"eligible": "Use true or false."})
            queryset = queryset.filter(is_eligible=1 if normalized in {"true", "1"} else 0)

        search = params.get("search", "").strip()
        if search:
            user = getattr(self.request, "user", None)
            if user and user.is_admin:
                queryset = queryset.filter(
                    Q(name__icontains=search) | Q(phone__icontains=search)
                )
            else:
                queryset = queryset.filter(name__icontains=search)

        return queryset


class DonorListCreateView(DonorQuerySetMixin, generics.ListCreateAPIView):
    serializer_class = DonorSerializer
    filter_backends = [OrderingFilter]
    ordering_fields = {
        "name": "name",
        "blood_type": "blood_type",
        "last_donation": "last_donation",
        "created_at": "created_at",
        "eligibility": "is_eligible",
    }
    ordering = ["name"]

    def get_queryset(self):
        return self.filtered_queryset()

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdminUser()]
        return [IsAuthenticatedUser()]


class DonorDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DonorSerializer
    queryset = Donor.objects.all()
    lookup_field = "pk"

    def get_permissions(self):
        if self.request.method in {"PUT", "PATCH", "DELETE"}:
            return [IsAdminUser()]
        return [IsAuthenticatedUser()]
