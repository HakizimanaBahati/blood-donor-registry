from django.urls import path

from authentication.dev_login import DevLoginView
from authentication.views import LogoutView, MeView

urlpatterns = [
    path("dev-login/", DevLoginView.as_view(), name="auth-dev-login"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
]
