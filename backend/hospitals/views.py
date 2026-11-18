from rest_framework import generics

from authentication.permissions import IsAdminUser, IsAuthenticatedUser
from hospitals.models import Hospital
from hospitals.serializers import HospitalSerializer


class HospitalListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    queryset = Hospital.objects.all()
    serializer_class = HospitalSerializer


class HospitalDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = HospitalSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return Hospital.objects.all()
        return Hospital.objects.filter(pk=user.hospital_id)

    def get_permissions(self):
        if self.request.method in {"PUT", "PATCH"}:
            return [IsAdminUser()]
        return [IsAuthenticatedUser()]
