from django.urls import include, path

from analytics.urls import urlpatterns as analytics_urls
from config.health import HealthView
from authentication.urls import urlpatterns as auth_urls
from donors.urls import urlpatterns as donor_urls
from hospitals.urls import urlpatterns as hospital_urls
from requests_app.urls import urlpatterns as request_urls

urlpatterns = [
    path("health", HealthView.as_view(), name="health"),
    path("api/auth/", include(auth_urls)),
    path("api/donors/", include(donor_urls)),
    path("api/hospitals/", include(hospital_urls)),
    path("api/requests/", include(request_urls)),
    path("api/analytics/", include(analytics_urls)),
]
