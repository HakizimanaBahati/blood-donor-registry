from rest_framework.response import Response
from rest_framework.views import APIView


class MeView(APIView):
    """Returns the role the backend resolved from the verified token + profile table."""

    def get(self, request):
        user = request.user
        return Response(
            {
                "id": str(user.id),
                "full_name": user.full_name,
                "role": user.role,
                "hospital_id": str(user.hospital_id) if user.hospital_id else None,
            }
        )


class LogoutView(APIView):
    """Django is stateless; Supabase handles token revocation on the client side."""

    def post(self, request):
        return Response(
            {
                "message": (
                    "Django has no server-side session to destroy. Call "
                    "supabase.auth.signOut() in the frontend and discard the access token."
                )
            }
        )
