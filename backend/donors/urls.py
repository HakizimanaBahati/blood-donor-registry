from django.urls import path

from donors.views import DonorDetailView, DonorListCreateView

urlpatterns = [
    path("", DonorListCreateView.as_view(), name="donor-list"),
    path("<uuid:pk>/", DonorDetailView.as_view(), name="donor-detail"),
]
