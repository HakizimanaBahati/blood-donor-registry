from django.urls import path

from requests_app.views import BloodRequestDetailView, BloodRequestListCreateView

urlpatterns = [
    path("", BloodRequestListCreateView.as_view(), name="request-list"),
    path("<uuid:pk>/", BloodRequestDetailView.as_view(), name="request-detail"),
]
