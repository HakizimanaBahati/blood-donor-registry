from rest_framework import generics

from requests_app.models import BloodRequest
from requests_app.serializers import BloodRequestSerializer


class ScopedRequestQuerysetMixin:
    """Admins see every request; hospitals only see their own hospital's requests."""

    def get_queryset(self):
        user = self.request.user
        queryset = BloodRequest.objects.select_related("hospital", "donor")
        if user.is_admin:
            return queryset
        return queryset.filter(hospital_id=user.hospital_id)


class BloodRequestListCreateView(ScopedRequestQuerysetMixin, generics.ListCreateAPIView):
    serializer_class = BloodRequestSerializer


class BloodRequestDetailView(ScopedRequestQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BloodRequestSerializer
    lookup_field = "pk"
