# Configuración externa de Google Cloud

Este documento describe la configuración que hay que dejar hecha en **Google Cloud Console** para que el login con Google y las conexiones de datos (GA4 + Search Console) funcionen en un entorno dado (local, dev, prod). No cubre el código — solo la parte externa que vive fuera del repo.

Cada entorno (dev, prod) usa su **propio proyecto de Google Cloud** y su **propio par de credenciales OAuth** — no se comparten entre entornos. Ver "División dev/prod" más abajo.

## 1. Proyecto de Google Cloud

Crea (o reutiliza) un proyecto en [Google Cloud Console](https://console.cloud.google.com). El nombre visible del proyecto (display name) no importa y se puede cambiar en cualquier momento desde `IAM & Admin` → `Settings` sin afectar al funcionamiento — el identificador real es el **Project ID**, que es inmutable.

Antes de reutilizar un proyecto existente, comprueba que esté vacío o que sepas exactamente qué contiene — no lo dejes en manos de que "parece vacío".

## 2. Habilitar las APIs necesarias

`APIs & Services` → `Library`, y activa:

| API | Para qué |
|---|---|
| **Google Analytics Admin API** | Listar cuentas/propiedades GA4 (`analyticsadmin.googleapis.com`) |
| **Google Analytics Data API** | Informes GA4 (`analyticsdata.googleapis.com`) |
| **Google Search Console API** | Datos de Search Console (`www.googleapis.com/webmasters/v3`) |

No hace falta activar ninguna API para el login (usa endpoints públicos de `accounts.google.com` que no requieren habilitación).

## 3. Pantalla de consentimiento OAuth

`APIs & Services` → `OAuth consent screen` (Google Auth Platform):

- **Tipo de usuario**: `External` — obligatorio, es login de clientes, no una herramienta interna restringida al workspace propio.
- **Modo**: `Testing` mientras no esté verificada por Google (limita el login a usuarios de prueba añadidos explícitamente; pasar a producción requiere el proceso de verificación de Google si se usan scopes sensibles).

### Scopes (`Google Auth Platform` → `Data Access`)

| Scope | Uso |
|---|---|
| `openid` | Login |
| `.../auth/userinfo.email` | Login |
| `.../auth/userinfo.profile` | Login |
| `.../auth/webmasters.readonly` | Conexión de datos — Search Console |
| `.../auth/analytics.readonly` | Conexión de datos — GA4 |

## 4. Cliente OAuth

`APIs & Services` → `Credentials` → `Create Credentials` → `OAuth client ID`:

- **Application type**: `Web application`
- **Authorized redirect URIs** — exactamente estas dos, una por flujo (login y conexión de datos son flujos separados con callbacks distintos, ver `CLAUDE.md`):
  ```
  https://<host>/api/v1/google/callback
  https://<host>/api/v1/connections/google/callback
  ```
  Sustituye `<host>` por el dominio del backend en ese entorno (ej. `dev.aishophelper.ai`, o `localhost:8080` en local).

Al crear el cliente, Google muestra el **Client ID** y el **Client Secret** — cópialos, el secret completo no se vuelve a mostrar después.

## 5. Variables de entorno

Estas son las variables de entorno necesarias en cada entorno (dev, prod). Cómo y dónde se inyectan es cosa de la infraestructura de cada entorno, no de este repo:

```env
GOOGLE_CLIENT_ID=<client id del paso 4>
GOOGLE_CLIENT_SECRET=<client secret del paso 4>
GOOGLE_LOGIN_REDIRECT_URI=https://<host>/api/v1/google/callback
GOOGLE_LOGIN_SUCCESS_URL=https://<frontend host>/login/success
GOOGLE_LOGIN_ERROR_URL=https://<frontend host>/login/failure
GOOGLE_CONNECTION_REDIRECT_URI=https://<host>/api/v1/connections/google/callback
```

`GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` son opcionales a nivel de arranque de la app (no rompe el boot si faltan), pero sin ellos el login/conexión con Google falla en tiempo de petición con `invalid_request` de Google.

## 6. Verificación rápida

```
GET /api/v1/google/login
```
Debe devolver un `auth_url` con `client_id` no vacío. Si `client_id` viene vacío, la variable de entorno no está seteada en ese entorno.

## División dev/prod

Cada entorno tiene su propio proyecto de Google Cloud, y por tanto su propio cliente OAuth y sus propias credenciales — nunca se reutiliza el mismo Client ID/Secret entre dev y prod. Esto es una decisión explícita, no un detalle de implementación: mezclar entornos en un solo proyecto de Google mezclaría también usuarios de prueba, cuotas y (si se verifica la app) la revisión de Google.
