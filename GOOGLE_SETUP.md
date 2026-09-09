# Google Cloud external setup

This document describes the setup that must be in place in **Google Cloud Console** for Google login and
the data connections (GA4 + Search Console) to work in a given environment (local, dev, prod). It does not
cover code — only the external part that lives outside the repo.

Each environment (dev, prod) uses its **own Google Cloud project** and its **own OAuth credential pair** —
they are not shared between environments. See "Dev/prod split" below.

## 1. Google Cloud project

Create (or reuse) a project in [Google Cloud Console](https://console.cloud.google.com). The project's
display name does not matter and can be changed anytime under `IAM & Admin` → `Settings` without affecting
anything — the real identifier is the **Project ID**, which is immutable.

Before reusing an existing project, confirm it is empty or that you know exactly what it contains — do not
rely on it just "looking empty".

## 2. Enable the required APIs

`APIs & Services` → `Library`, and enable:

| API | Purpose |
|---|---|
| **Google Analytics Admin API** | List GA4 accounts/properties (`analyticsadmin.googleapis.com`) |
| **Google Analytics Data API** | GA4 reports (`analyticsdata.googleapis.com`) |
| **Google Search Console API** | Search Console data (`www.googleapis.com/webmasters/v3`) |

No API needs to be enabled for login (it uses public `accounts.google.com` endpoints that require no
enablement).

## 3. OAuth consent screen

`APIs & Services` → `OAuth consent screen` (Google Auth Platform):

- **User type**: `External` — required; this is customer login, not an internal tool restricted to your own
  workspace.
- **Mode**: `Testing` until verified by Google (limits login to explicitly added test users; moving to
  production requires Google's verification process if sensitive scopes are used).

### Scopes (`Google Auth Platform` → `Data Access`)

| Scope | Use |
|---|---|
| `openid` | Login |
| `.../auth/userinfo.email` | Login |
| `.../auth/userinfo.profile` | Login |
| `.../auth/webmasters.readonly` | Data connection — Search Console |
| `.../auth/analytics.readonly` | Data connection — GA4 |

## 4. OAuth client

`APIs & Services` → `Credentials` → `Create Credentials` → `OAuth client ID`:

- **Application type**: `Web application`
- **Authorized redirect URIs** — exactly these two, one per flow (login and data connection are separate
  flows with distinct callbacks, see `CLAUDE.md`):
  ```
  https://<host>/api/v1/google/callback
  https://<host>/api/v1/connections/google/callback
  ```
  Replace `<host>` with the backend domain for that environment (e.g. `dev.aishophelper.ai`, or
  `localhost:8080` locally).

When the client is created, Google shows the **Client ID** and **Client Secret** — copy them; the full
secret is not shown again afterwards.

## 5. Environment variables

These are the environment variables each environment (dev, prod) needs. How and where they are injected is
the concern of each environment's infrastructure, not of this repo:

```env
GOOGLE_CLIENT_ID=<client id from step 4>
GOOGLE_CLIENT_SECRET=<client secret from step 4>
GOOGLE_LOGIN_REDIRECT_URI=https://<host>/api/v1/google/callback
GOOGLE_LOGIN_SUCCESS_URL=https://<frontend host>/login/success
GOOGLE_LOGIN_ERROR_URL=https://<frontend host>/login/failure
GOOGLE_CONNECTION_REDIRECT_URI=https://<host>/api/v1/connections/google/callback
```

`GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` are optional at app startup (the boot does not break if they are
missing), but without them Google login/connection fails at request time with Google's `invalid_request`.

## 6. Quick verification

```
GET /api/v1/google/login
```
Must return an `auth_url` with a non-empty `client_id`. If `client_id` comes back empty, the environment
variable is not set in that environment.

## Dev/prod split

Each environment has its own Google Cloud project, and therefore its own OAuth client and its own
credentials — the same Client ID/Secret is never reused between dev and prod. This is a deliberate decision,
not an implementation detail: mixing environments in a single Google project would also mix test users,
quotas, and (if the app gets verified) Google's review.
