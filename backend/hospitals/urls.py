from django.urls import path

from hospitals.views import HospitalDetailView, HospitalListCreateView

urlpatterns = [
    path("", HospitalListCreateView.as_view(), name="hospital-list"),
    path("<uuid:pk>/", HospitalDetailView.as_view(), name="hospital-detail"),
]
