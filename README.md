# Keycloak + React + Django REST Framework Learning Project

A hands-on learning project demonstrating how to integrate **Keycloak (OpenID Connect)** with a **React frontend** and a **Django REST Framework API**.

This guide covers:

- Running Keycloak with Docker Compose
- Creating a realm, users, roles, and OIDC clients
- React login/logout with `keycloak-js` and PKCE
- Validating Keycloak access tokens in Django
- Protecting endpoints with realm-role-based permissions
- Refreshing access tokens before API calls
- Running and testing all services locally

> **Learning setup only:** The credentials and HTTP URLs below are for local development. Do not use these settings as-is in production.

---

## 1. Architecture

```text
Browser
  |
  | 1. Login / logout
  v
React + keycloak-js  <-------------------->  Keycloak
  |                                          |
  | 2. Authorization: Bearer <access token>  | Issues tokens
  v                                          |
Django REST Framework API <-----------------+
  |
  | Verifies JWT signature, issuer,
  | audience, expiration and permissions
  v
Protected API response
```

Keycloak authenticates users. React obtains and sends an **access token** to Django. Django independently validates that token and applies authorization rules.

## 2. Prerequisites

Check that the required tools are installed:

```bash
docker --version
docker compose version
python3 --version
node --version
npm --version
git --version
```

If Docker requires `sudo` on your machine, prefix Docker commands with `sudo`. The examples below assume your user can run Docker directly.

## 3. Project directory

The examples use this location:

```bash
mkdir -p ~/swe/ph/keycloak_learning
cd ~/swe/ph/keycloak_learning
```

Expected structure after completing the guide:

```text
keycloak_learning/
├── docker-compose.yml
├── keycloak-django/
│   ├── .venv/
│   ├── manage.py
│   ├── requirements.txt
│   ├── config/
│   │   ├── settings.py
│   │   └── urls.py
│   └── api/
│       ├── authentication.py
│       ├── permissions.py
│       ├── views.py
│       └── ...
└── keycloak-react/
    ├── package.json
    └── src/
        ├── api/
        │   └── apiClient.js
        ├── keycloak.js
        ├── main.jsx
        └── App.jsx
```

---

# Part A — Set up Keycloak

## 4. Create `docker-compose.yml`

From the project root:

```bash
cd ~/swe/ph/keycloak_learning
nano docker-compose.yml
```

Add:

```yaml
services:
  keycloak:
    image: quay.io/keycloak/keycloak:latest
    container_name: keycloak
    command: start-dev
    environment:
      KC_BOOTSTRAP_ADMIN_USERNAME: admin
      KC_BOOTSTRAP_ADMIN_PASSWORD: admin123
    ports:
      - "8080:8080"
    restart: unless-stopped
```

For repeatable environments, consider pinning a specific Keycloak image version rather than using `latest`.

## 5. Start and manage Keycloak

Start it in the background:

```bash
docker compose up -d
```

Check the container:

```bash
docker compose ps
docker logs -f keycloak
```

Stop viewing logs with `Ctrl+C`; this does not stop the container.

Open the admin console:

- Admin Console: http://localhost:8080/admin/
- Development server: http://localhost:8080/

Sign in with the local bootstrap credentials:

```text
Username: admin
Password: admin123
```

Stop Keycloak:

```bash
docker compose down
```

Start it again:

```bash
docker compose up -d
```

> This simple Compose configuration does not configure a persistent database volume. Do not assume realm configuration will survive container replacement. For long-term local use, configure a persistent database or export realm configuration.

## 6. Create the `learning` realm

In the Keycloak Admin Console:

1. Open the realm selector.
2. Create a realm named `learning`.
3. Select `learning` as the active realm.

The realm issuer should be:

```text
http://localhost:8080/realms/learning
```

Check the OpenID Connect discovery document:

```bash
curl -s http://localhost:8080/realms/learning/.well-known/openid-configuration
```

For readable output, if `jq` is installed:

```bash
curl -s http://localhost:8080/realms/learning/.well-known/openid-configuration | jq
```

## 7. Create realm roles

In the `learning` realm, open **Realm roles** and create:

- `customer`
- `admin`

These are application roles used by the Django API. They are not Keycloak's built-in administrative roles.

## 8. Create users and assign roles

Create or configure these users under **Users**:

### Admin user

```text
Username: parvez
```

Set a password under **Credentials**. For local testing, disable the temporary-password requirement if you do not want to be prompted to change the password.

Under **Role mapping**, assign the `admin` realm role.

### Customer test user

```text
Username: customer1
```

Set a password and assign the `customer` realm role.

Expected role assignments:

| User | Role |
|---|---|
| `parvez` | `admin` |
| `customer1` | `customer` |

Log out and log in again after changing roles so you receive a new access token containing the updated role claims.

## 9. Create the `react-app` client

In the `learning` realm, create an OpenID Connect client:

```text
Client ID: react-app
```

For a browser-based React application, configure the client as a public client:

- Client authentication: **Off**
- Standard flow: **On**
- Direct access grants: **Off**
- Valid redirect URIs: `http://localhost:5173/*`
- Valid post logout redirect URIs: `http://localhost:5173/*`
- Web origins: `http://localhost:5173`

Exact field names may vary by Keycloak version. Avoid broad wildcards in production.

The React adapter uses Authorization Code Flow with PKCE.

## 10. Create the `django-api` audience

Django will validate that access tokens are intended for the API, not just any client.

In Keycloak:

1. Open **Client scopes** and create a scope named `django-api-audience`.
2. Add an **Audience** protocol mapper to this scope.
3. Set the included/custom audience to `django-api`.
4. Configure the mapper to add the audience to the access token.
5. Assign the scope as a **default client scope** to `react-app`.

Check the access token's `aud` claim after logging in. It must include `django-api`, for example:

```json
{
  "aud": ["django-api", "account"]
}
```

The exact set of audiences can vary. Django only requires that `django-api` is present.

---

# Part B — Create the React frontend

## 11. Create the Vite React project

Open a new terminal:

```bash
cd ~/swe/ph/keycloak_learning
npm create vite@latest keycloak-react -- --template react
cd keycloak-react
npm install
npm install keycloak-js
```

Start React:

```bash
npm run dev
```

Vite normally serves the application at:

```text
http://localhost:5173
```

Keep this terminal running.

## 12. Configure `src/keycloak.js`

Create or edit the file:

```bash
nano src/keycloak.js
```

Use:

```javascript
import Keycloak from "keycloak-js";

const keycloak = new Keycloak({
  url: "http://localhost:8080",
  realm: "learning",
  clientId: "react-app",
});

export default keycloak;
```

## 13. Initialize Keycloak in `src/main.jsx`

Initialize Keycloak before rendering the application. The exact contents can differ if your Vite project has already been customized; preserve any existing CSS imports you need.

Example:

```jsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import keycloak from "./keycloak";
import "./index.css";

async function startApp() {
  try {
    await keycloak.init({
      onLoad: "check-sso",
      pkceMethod: "S256",
    });

    ReactDOM.createRoot(document.getElementById("root")).render(
      <React.StrictMode>
        <App />
      </React.StrictMode>,
    );
  } catch (error) {
    console.error("Failed to initialize Keycloak:", error);
    document.getElementById("root").textContent =
      "Unable to initialize authentication.";
  }
}

startApp();
```

`check-sso` checks whether the user already has a Keycloak session. It does not force a login when no session exists.

## 14. Basic login/logout and user information

Example `src/App.jsx`:

```jsx
import keycloak from "./keycloak";

function App() {
  const authenticated = Boolean(keycloak.authenticated);
  const user = keycloak.idTokenParsed;

  if (!authenticated) {
    return (
      <main>
        <h1>Keycloak Learning App</h1>
        <button onClick={() => keycloak.login()}>
          Login
        </button>
      </main>
    );
  }

  return (
    <main>
      <h1>Welcome!</h1>
      <p>You are authenticated through Keycloak.</p>

      <h2>User Information</h2>
      <pre>
        {JSON.stringify(
          {
            username: user?.preferred_username,
            email: user?.email,
            name: user?.name,
            subject: user?.sub,
            issuer: user?.iss,
          },
          null,
          2,
        )}
      </pre>

      <h2>Access Token Roles</h2>
      <pre>
        {JSON.stringify(
          keycloak.tokenParsed?.realm_access?.roles ?? [],
          null,
          2,
        )}
      </pre>

      <button
        onClick={() =>
          keycloak.logout({
            redirectUri: window.location.origin,
          })
        }
      >
        Logout
      </button>
    </main>
  );
}

export default App;
```

This is a minimal example. If you already have a working `App.jsx` with API calls and loading/error states, keep those features instead of replacing the entire file.

---

# Part C — Create the Django REST API

## 15. Create the Django project and virtual environment

Open a new terminal:

```bash
cd ~/swe/ph/keycloak_learning
mkdir keycloak-django
cd keycloak-django

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install django djangorestframework PyJWT cryptography requests

django-admin startproject config .
python manage.py startapp api
```

Save the dependencies:

```bash
pip freeze > requirements.txt
```

Whenever you return to the Django project, activate its environment:

```bash
cd ~/swe/ph/keycloak_learning/keycloak-django
source .venv/bin/activate
```

## 16. Configure `config/settings.py`

Add these apps to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # Existing Django apps...
    "rest_framework",
    "api",
]
```

Add the Keycloak settings near the bottom:

```python
KEYCLOAK_BASE_URL = "http://localhost:8080"
KEYCLOAK_REALM = "learning"
KEYCLOAK_ISSUER = (
    f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_REALM}"
)
KEYCLOAK_JWKS_URL = (
    f"{KEYCLOAK_ISSUER}/protocol/openid-connect/certs"
)
KEYCLOAK_API_AUDIENCE = "django-api"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.authentication.KeycloakAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}
```

These URLs work for the described local Docker setup. In production, configure the public issuer URL and JWKS URL appropriately for your deployment. Do not assume that `localhost` inside one container refers to another container.

## 17. Create `api/authentication.py`

```python
import jwt

from django.conf import settings
from django.contrib.auth import get_user_model

from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError

from rest_framework import authentication, exceptions


User = get_user_model()

# Reuse the client in this Python process.
# Do not put the PyJWKClient object in Django's cache.
jwks_client = PyJWKClient(
    settings.KEYCLOAK_JWKS_URL,
    cache_keys=True,
)


class KeycloakAuthentication(authentication.BaseAuthentication):
    """Authenticate requests using Keycloak JWT access tokens."""

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
                "Invalid or expired access token."
            ) from exc
        except Exception as exc:
            # Log details securely in production; do not expose internals.
            raise exceptions.AuthenticationFailed(
                "Token authentication failed."
            ) from exc

        subject = payload["sub"]

        # Learning example: use a stable local username based on the
        # Keycloak subject. Production applications should model external
        # identities explicitly, keyed by issuer + subject.
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
```

**Why the `PyJWKClient` is a module-level object:** it can reuse its internal key cache without Django trying to pickle the client object. Caching that object using `cache.set()` caused the earlier `cannot pickle '_thread.RLock' object` error.

This is an educational implementation. A production implementation should handle JWKS/network failures explicitly, log failures securely, and use a deliberate external-identity mapping strategy.

## 18. Create `api/permissions.py`

```python
from rest_framework.permissions import BasePermission


class HasCustomerOrAdminRole(BasePermission):
    message = "You need the customer or admin role to access this resource."

    def has_permission(self, request, view):
        claims = request.auth or {}
        roles = claims.get("realm_access", {}).get("roles", [])

        return bool({"customer", "admin"} & set(roles))


class HasAdminRole(BasePermission):
    message = "You need the admin role to access this resource."

    def has_permission(self, request, view):
        claims = request.auth or {}
        roles = claims.get("realm_access", {}).get("roles", [])

        return "admin" in roles
```

These checks expect Keycloak realm roles to appear in the access token under `realm_access.roles`. Verify your actual token before relying on this claim structure.

## 19. Create `api/views.py`

```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from api.permissions import HasAdminRole, HasCustomerOrAdminRole


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
@permission_classes([IsAuthenticated, HasCustomerOrAdminRole])
def orders_view(request):
    # Demo data only: this is NOT a real ownership-filtered order query.
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
@permission_classes([IsAuthenticated, HasAdminRole])
def admin_reports_view(request):
    return Response({
        "message": "Welcome to the admin reports endpoint.",
        "report": {
            "total_orders": 150,
            "pending_orders": 25,
            "completed_orders": 125,
        },
    })
```

The orders endpoint is a role-checking demonstration. A real customer-facing application must also filter order records by ownership so customers cannot read other customers' orders.

## 20. Configure `config/urls.py`

```python
from django.contrib import admin
from django.urls import path

from api.views import (
    admin_reports_view,
    me_view,
    orders_view,
    public_view,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/public/", public_view),
    path("api/me/", me_view),
    path("api/orders/", orders_view),
    path("api/admin/reports/", admin_reports_view),
]
```

## 21. Run database migrations and checks

With the virtual environment activated:

```bash
python manage.py migrate
python manage.py check
python manage.py runserver
```

Django should now be available at:

```text
http://127.0.0.1:8000
```

Keep the terminal running.

---

# Part D — Connect React to Django

## 22. Configure CORS

The React development server runs on port `5173`, while Django runs on port `8000`. These are different origins, so configure CORS for local development.

Install the package in the Django virtual environment:

```bash
cd ~/swe/ph/keycloak_learning/keycloak-django
source .venv/bin/activate
pip install django-cors-headers
pip freeze > requirements.txt
```

Add `"corsheaders"` to `INSTALLED_APPS` in `config/settings.py`:

```python
INSTALLED_APPS = [
    "corsheaders",
    # Existing Django apps...
    "rest_framework",
    "api",
]
```

Place `CorsMiddleware` near the top of `MIDDLEWARE`, before `CommonMiddleware`:

```python
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    # Keep the existing middleware entries below.
]
```

Do not delete the rest of Django's default middleware.

Add:

```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
]
```

Restart Django after changing settings.

CORS is a browser policy, not a replacement for authentication or authorization.

## 23. Create `src/api/apiClient.js`

In the React project:

```bash
cd ~/swe/ph/keycloak_learning/keycloak-react
mkdir -p src/api
nano src/api/apiClient.js
```

Add:

```javascript
import keycloak from "../keycloak";

const API_BASE_URL = "http://127.0.0.1:8000";

export async function apiRequest(
  path,
  { method = "GET", headers = {}, body } = {},
) {
  if (!keycloak.authenticated) {
    throw new Error("You must log in before calling this API.");
  }

  // Refresh if the access token will expire within 30 seconds.
  await keycloak.updateToken(30);

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: {
      ...headers,
      Authorization: `Bearer ${keycloak.token}`,
      ...(body !== undefined && !(body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
    },
    body:
      body === undefined
        ? undefined
        : body instanceof FormData
          ? body
          : JSON.stringify(body),
  });

  const contentType = response.headers.get("content-type");
  const data = contentType?.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message =
      typeof data === "object" && data !== null
        ? data.detail || `API request failed: ${response.status}`
        : `API request failed: ${response.status}`;

    throw new Error(message);
  }

  return data;
}
```

This helper refreshes the token before a request if it is close to expiring. If refreshing fails, the request fails rather than sending a known-expired token. Production apps should also implement consistent handling for refresh failures and API 401 responses.

## 24. Add a Django API button to React

In `src/App.jsx`, import:

```jsx
import { useState } from "react";
import { apiRequest } from "./api/apiClient";
```

Inside the `App` component, add:

```jsx
const [apiResult, setApiResult] = useState(null);
const [apiError, setApiError] = useState("");
const [loading, setLoading] = useState(false);

async function loadCurrentUser() {
  setLoading(true);
  setApiError("");
  setApiResult(null);

  try {
    const data = await apiRequest("/api/me/");
    setApiResult(data);
  } catch (error) {
    setApiError(error.message);
  } finally {
    setLoading(false);
  }
}
```

Add the following JSX to the authenticated part of your UI:

```jsx
<section>
  <h2>Django API</h2>

  <button onClick={loadCurrentUser} disabled={loading}>
    {loading ? "Loading..." : "Call Django API"}
  </button>

  {apiError && <p role="alert">API Error: {apiError}</p>}

  {apiResult && (
    <pre>{JSON.stringify(apiResult, null, 2)}</pre>
  )}
</section>
```

Keep the existing login/logout UI and make sure hooks are declared at the top level of the component, before any conditional returns.

---

# Part E — Run all services

## 25. Start Keycloak, Django, and React

You need three terminal windows/tabs.

### Terminal 1 — Keycloak

```bash
cd ~/swe/ph/keycloak_learning
docker compose up -d
docker compose logs -f keycloak
```

### Terminal 2 — Django

```bash
cd ~/swe/ph/keycloak_learning/keycloak-django
source .venv/bin/activate
python manage.py runserver
```

### Terminal 3 — React

```bash
cd ~/swe/ph/keycloak_learning/keycloak-react
npm run dev
```

Open:

```text
http://localhost:5173
```

Log in as `parvez` and click **Call Django API**.

Expected successful response:

```json
{
  "message": "Authentication successful.",
  "user": {
    "django_username": "keycloak_<keycloak-subject>",
    "keycloak_subject": "<keycloak-subject>",
    "keycloak_username": "parvez",
    "email": "email@email.com",
    "issuer": "http://localhost:8080/realms/learning",
    "audience": ["django-api", "account"],
    "roles": ["admin"]
  }
}
```

Values such as the subject, email, audience order, and roles will vary based on your actual Keycloak user and token.

---

# Part F — Test the API

## 26. Test the public endpoint

```bash
curl -i http://127.0.0.1:8000/api/public/
```

Expected: `200 OK`.

## 27. Test a protected endpoint without a token

```bash
curl -i http://127.0.0.1:8000/api/me/
```

Expected: `401 Unauthorized`.

## 28. Test using an access token

For local debugging, you can copy the access token from the browser developer console. Do not share it, save it in Git, or put it in a URL.

Paste it into the terminal without echoing it:

```bash
read -rsp "Paste access token: " ACCESS_TOKEN
echo
```

Test the profile:

```bash
curl -i http://127.0.0.1:8000/api/me/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

Test orders:

```bash
curl -i http://127.0.0.1:8000/api/orders/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

Test the admin endpoint:

```bash
curl -i http://127.0.0.1:8000/api/admin/reports/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

Clear the variable when finished:

```bash
unset ACCESS_TOKEN
```

## 29. Expected role-based access results

| Request | Expected result |
|---|---|
| No token → `/api/public/` | `200 OK` |
| No token → `/api/me/` | `401 Unauthorized` |
| Customer token → `/api/orders/` | `200 OK` |
| Admin token → `/api/orders/` | `200 OK` |
| Customer token → `/api/admin/reports/` | `403 Forbidden` |
| Admin token → `/api/admin/reports/` | `200 OK` |
| Invalid or expired token → protected endpoint | `401 Unauthorized` |

If a valid token gets `403` on the admin endpoint, check that its access-token claims include:

```json
{
  "realm_access": {
    "roles": ["admin"]
  }
}
```

If the role is missing, inspect Keycloak role assignments and client scopes/mappers.

---

# Part G — Token refresh

## 30. Understand the refresh process

- The access token is sent to Django.
- The refresh token is used by the Keycloak client adapter to request fresh tokens.
- The frontend should not send the refresh token to Django.
- `keycloak.updateToken(30)` asks the adapter to refresh the access token when it is due to expire within 30 seconds.
- If the Keycloak session has ended and refresh fails, handle the error and ask the user to sign in again.

For a manual learning test, you can call:

```javascript
const refreshed = await keycloak.updateToken(-1);
console.log("Token refreshed:", refreshed);
```

`-1` forces a refresh attempt. Do not force a refresh for every normal API request.

For production, use HTTPS, review browser token-storage risks, and handle refresh errors and expired sessions consistently.

---

# Troubleshooting

## Keycloak container is not ready

```bash
docker compose ps
docker compose logs --tail=200 keycloak
```

## Django cannot connect to Keycloak

Check the discovery endpoint:

```bash
curl -i http://localhost:8080/realms/learning/.well-known/openid-configuration
```

The configured issuer must exactly match the token's `iss` claim.

## `InvalidAudienceError` or audience mismatch

Inspect the access token's `aud` claim and confirm that it includes `django-api`. Check the audience mapper and ensure it is assigned to `react-app` as a default client scope. Log in again to obtain a fresh token.

## `cannot pickle '_thread.RLock' object`

Do not put the `PyJWKClient` object into Django's cache using `cache.set()`. Reuse a module-level client or implement a deliberate cache for serializable JWKS/key data.

## CORS error in the browser

Verify that:

- React is using `http://localhost:5173`.
- Django allows `http://localhost:5173` in `CORS_ALLOWED_ORIGINS`.
- `CorsMiddleware` appears before `CommonMiddleware`.
- Django has been restarted after settings changes.

CORS fixes do not make an invalid token valid.

## Customer gets `403 Forbidden`

This is expected for `/api/admin/reports/` when the customer does not have the `admin` role. If a user should have admin access, verify the role assignment and the role claim in a newly issued access token.

## Django returns `Token authentication failed`

Check the Django terminal for the underlying error. Verify Keycloak is reachable at the configured JWKS URL and that the token's signature, issuer, audience, and expiry are valid. Do not expose detailed internal errors in production API responses.

---

# Security notes before production

This repository is a local learning implementation, not a production-ready identity integration.

Before deploying:

- Replace all demo credentials and pin dependency/container versions.
- Use HTTPS and appropriately configured trusted hosts and origins.
- Keep signing-key verification enabled and validate issuer, audience, expiry, and allowed algorithms.
- Handle JWKS/network errors explicitly; do not leak internal exception messages.
- Configure stable external identity mapping using issuer + subject.
- Do not trust usernames, email addresses, or frontend role checks as authorization.
- Apply object-level authorization and data ownership checks.
- Use least-privilege roles and review role mappings.
- Do not log or commit access/refresh tokens or secrets.
- Use a deliberate Keycloak database/persistence configuration and backups.
- Review session expiry, logout, refresh-token, and browser storage policies.
- Use production-grade Django settings, logging, monitoring, and deployment infrastructure.

## Useful references

- Keycloak documentation: https://www.keycloak.org/documentation
- Keycloak JavaScript adapter: https://www.keycloak.org/securing-apps/javascript-adapter
- Django documentation: https://docs.djangoproject.com/
- Django REST Framework: https://www.django-rest-framework.org/
- PyJWT documentation: https://pyjwt.readthedocs.io/

---

## Quick-start summary

After the initial setup is complete, start the services as follows.

**Terminal 1:**

```bash
cd ~/swe/ph/keycloak_learning
docker compose up -d
```

**Terminal 2:**

```bash
cd ~/swe/ph/keycloak_learning/keycloak-django
source .venv/bin/activate
python manage.py runserver
```

**Terminal 3:**

```bash
cd ~/swe/ph/keycloak_learning/keycloak-react
npm run dev
```

Then open `http://localhost:5173`, sign in with Keycloak, and test the protected Django API.
