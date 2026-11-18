from django.urls import path

from analytics.views import DashboardSummaryView, DonorsPerBloodTypeView

urlpatterns = [
    path("donors-per-blood-type/", DonorsPerBloodTypeView.as_view(), name="analytics-blood-types"),
    path("summary/", DashboardSummaryView.as_view(), name="analytics-summary"),
]
