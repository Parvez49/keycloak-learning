from rest_framework.permissions import BasePermission


class HasCustomerOrAdminRole(BasePermission):
    """
    Allow users with either the customer or admin realm role.
    """

    message = "You need the customer or admin role to access this resource."

    def has_permission(self, request, view):
        claims = request.auth or {}

        realm_access = claims.get("realm_access", {})
        roles = realm_access.get("roles", [])

        return bool({"customer", "admin"} & set(roles))


class HasAdminRole(BasePermission):
    """
    Allow only users with the admin realm role.
    """

    message = "You need the admin role to access this resource."

    def has_permission(self, request, view):
        claims = request.auth or {}

        realm_access = claims.get("realm_access", {})
        roles = realm_access.get("roles", [])

        return "admin" in roles
