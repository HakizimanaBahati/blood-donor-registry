from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from common.constants import BLOOD_TYPES
from donors.models import Donor
from donors.services import MIN_DAYS_BETWEEN_DONATIONS
from hospitals.models import Hospital
from requests_app.models import BloodRequest
from requests_app.serializers import BloodRequestSerializer


class DonorsPerBloodTypeView(APIView):
    """Database-derived donor counts for every allowed blood type (including zeros)."""

    def get(self, request):
        counts = {code: 0 for code, _ in BLOOD_TYPES}
        for row in Donor.objects.values("blood_type").annotate(total=Count("id")):
            counts[row["blood_type"]] = row["total"]
        return Response(counts)


class DashboardSummaryView(APIView):
    """Counts for the dashboard cards plus the five most recent visible requests."""

    def get(self, request):
        cutoff = timezone.localdate() - timedelta(days=MIN_DAYS_BETWEEN_DONATIONS)
        donors = Donor.objects.all()
        eligible = donors.filter(
            Q(last_donation__isnull=True) | Q(last_donation__lte=cutoff)
        ).count()
        total_donors = donors.count()

        requests = BloodRequest.objects.select_related("hospital", "donor")
        if not request.user.is_admin:
            requests = requests.filter(hospital_id=request.user.hospital_id)

        recent = requests.order_by("-created_at")[:5]
        return Response(
            {
                "total_donors": total_donors,
                "eligible_donors": eligible,
                "ineligible_donors": total_donors - eligible,
                "total_hospitals": Hospital.objects.count(),
                "total_requests": requests.count(),
                "recent_requests": BloodRequestSerializer(
                    recent, many=True, context={"request": request}
                ).data,
            }
        )
