import jwt

from django.conf import settings
from django.contrib.auth import get_user_model

from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError

from rest_framework import authentication, exceptions


User = get_user_model()

# Keep the JWKS client in memory.
# Do not store the client object in Django's cache.
jwks_client = PyJWKClient(
    settings.KEYCLOAK_JWKS_URL,
    cache_keys=True,
)


class KeycloakAuthentication(authentication.BaseAuthentication):
    """
    Authenticate requests using Keycloak JWT access tokens.
    """

    def authenticate(self, request):
        authorization = authentication.get_authorization_header(
            request
        ).split()

        if not authorization:
            return None

        if authorization[0].lower() != b"bearer":
            return None

        if len(authorization) != 2:
            raise exceptions.AuthenticationFailed(
                "Invalid Authorization header."
            )

        try:
            token = authorization[1].decode("utf-8")

            signing_key = jwks_client.get_signing_key_from_jwt(token).key

            payload = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                issuer=settings.KEYCLOAK_ISSUER,
                audience=settings.KEYCLOAK_API_AUDIENCE,
                options={
                    "require": [
                        "exp",
                        "iat",
                        "iss",
                        "sub",
                        "aud",
                    ],
                },
            )

        except InvalidTokenError as exc:
            raise exceptions.AuthenticationFailed(
                f"Invalid or expired access token: {exc}"
            ) from exc

        except Exception as exc:
            # Temporary debugging detail. Remove internal error details
            # from API responses before deploying to production.
            print("KEYCLOAK AUTH ERROR:", repr(exc))
            raise exceptions.AuthenticationFailed(
                f"Token authentication failed: {exc}"
            ) from exc

        subject = payload["sub"]

        user, _ = User.objects.get_or_create(
            username=f"keycloak_{subject}",
            defaults={
                "first_name": payload.get("given_name", ""),
                "last_name": payload.get("family_name", ""),
                "email": payload.get("email", ""),
            },
        )

        return user, payload

    def authenticate_header(self, request):
        return "Bearer"
