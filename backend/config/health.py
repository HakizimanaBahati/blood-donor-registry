from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Unauthenticated liveness probe for local monitoring and smoke tests."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"status": "ok"})
