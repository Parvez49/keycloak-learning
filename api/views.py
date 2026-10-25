from rest_framework.decorators import (
    api_view,
    permission_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from api.permissions import (
    HasAdminRole,
    HasCustomerOrAdminRole,
)


@api_view(["GET"])
@permission_classes([AllowAny])
def public_view(request):
    return Response({
        "message": "This is a public endpoint.",
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    claims = request.auth

    return Response({
        "message": "Authentication successful.",
        "user": {
            "django_username": request.user.username,
            "keycloak_subject": claims["sub"],
            "keycloak_username": claims.get("preferred_username"),
            "email": claims.get("email"),
            "issuer": claims["iss"],
            "audience": claims["aud"],
            "roles": claims.get("realm_access", {}).get("roles", []),
        },
    })


@api_view(["GET"])
@permission_classes([
    IsAuthenticated,
    HasCustomerOrAdminRole,
])
def orders_view(request):
    return Response({
        "message": "You can access orders.",
        "orders": [
            {
                "id": 1,
                "product": "Laptop",
                "status": "processing",
            },
            {
                "id": 2,
                "product": "Keyboard",
                "status": "delivered",
            },
        ],
        "authenticated_user": request.user.username,
    })


@api_view(["GET"])
@permission_classes([
    IsAuthenticated,
    HasAdminRole,
])
def admin_reports_view(request):
    return Response({
        "message": "Welcome to the admin reports endpoint.",
        "report": {
            "total_orders": 150,
            "pending_orders": 25,
            "completed_orders": 125,
        },
    })
