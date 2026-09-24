"""
Django settings for config project.

Environment-driven. Every knob below reads from the process environment,
falling back to a development-safe default only when DEBUG is on (or the
test runner is active). Production fails closed: a missing SECRET_KEY with
DEBUG=False raises at import rather than booting insecurely.

Copy `.env.example` to `.env` for local development.
"""

import os
import sys
from datetime import timedelta
from pathlib import Path

import dj_database_url
from csp.constants import NONE, SELF
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load `backend/.env` if present. Real environment variables always win, so
# a container/PaaS config is never overridden by a stray checked-out file.
load_dotenv(BASE_DIR / '.env')


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def env_bool(name, default=False):
    """
    Tolerant boolean parsing. An exact `== 'True'` compare silently reads
    `true`, `1`, and `True ` (trailing whitespace is endemic in .env files)
    as False, which produces baffling environments.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=()):
    """Comma-separated env var -> list of stripped, non-empty strings."""
    raw = os.environ.get(name)
    if raw is None:
        return list(default)
    return [item.strip() for item in raw.split(',') if item.strip()]


def env_int(name, default):
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        raise ImproperlyConfigured(f'{name} must be an integer, got {raw!r}.')


# True while `manage.py test` is running. Used only to let the suite boot on a
# clean checkout that has no .env — never to relax a production default.
RUNNING_TESTS = 'test' in sys.argv


# ---------------------------------------------------------------------------
# Core security settings
# ---------------------------------------------------------------------------

# Defaults to False: a deployment that forgets to set DEBUG gets the safe
# value. Local development sets DEBUG=True in .env (see .env.example).
DEBUG = env_bool('DEBUG', False)

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG or RUNNING_TESTS:
        # Development-only. Never used when DEBUG is off outside the suite.
        SECRET_KEY = 'django-insecure-dev-only-key-do-not-use-in-production'
    else:
        raise ImproperlyConfigured(
            'SECRET_KEY must be set when DEBUG is False. Generate one with:\n'
            '  python -c "from django.core.management.utils import '
            'get_random_secret_key; print(get_random_secret_key())"'
        )

ALLOWED_HOSTS = env_list('ALLOWED_HOSTS')
if not ALLOWED_HOSTS and (DEBUG or RUNNING_TESTS):
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']


# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    # Enables refresh-token revocation. Without this app installed,
    # BLACKLIST_AFTER_ROTATION below is silently a no-op.
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'csp',
    'subscriptions',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Directly below SecurityMiddleware, per WhiteNoise's documented position.
    # Django itself only serves static files when DEBUG is on, so without this
    # a DEBUG=False deployment renders /admin/ unstyled -- collectstatic writes
    # the files and then nothing hands them out. The reverse proxy could serve
    # STATIC_ROOT instead, but doing it here keeps the container self-contained
    # and correct even when run without the proxy (one-off management commands,
    # local `docker compose up` smoke tests).
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # As high as possible, and above CommonMiddleware, so CORS headers are
    # attached even to responses earlier middleware short-circuits
    # (redirects, 4xx) -- otherwise the browser reports those as opaque CORS
    # failures instead of the actual status.
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'csp.middleware.CSPMiddleware',
]

# The SPA's origin(s). Falls back to the Vite/CRA dev ports so a local
# checkout works without configuration; production must set FRONTEND_ORIGIN.
CORS_ALLOWED_ORIGINS = env_list('FRONTEND_ORIGIN')
if not CORS_ALLOWED_ORIGINS and (DEBUG or RUNNING_TESTS):
    CORS_ALLOWED_ORIGINS = ['http://localhost:5173', 'http://localhost:3000']

# The refresh-token cookie (below) is an ambient credential, but it is only
# ever meant to travel same-origin -- the SPA reaches the API through a
# same-site proxy. Keeping this False guarantees no *cross*-origin request can
# ever carry it, whatever FRONTEND_ORIGIN says.
CORS_ALLOW_CREDENTIALS = False

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

# DATABASE_URL is honoured for real now. Previously .env.example advertised
# the knob while settings hardcoded SQLite, so the file lied about itself.
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{(BASE_DIR / 'db.sqlite3').as_posix()}",
        conn_max_age=env_int('DB_CONN_MAX_AGE', 600),
        conn_health_checks=True,
    )
}


AUTH_USER_MODEL = 'subscriptions.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ---------------------------------------------------------------------------
# Cache (backs DRF throttling)
# ---------------------------------------------------------------------------

# LocMemCache is per-process: with more than one worker each holds its own
# throttle counters, so the effective rate is (workers x limit). Set REDIS_URL
# before any multi-worker deploy.
REDIS_URL = os.environ.get('REDIS_URL', '').strip()
if REDIS_URL:
    # A Redis outage should degrade throttling, not 500 every request in the
    # API. Django's built-in RedisCache has no option for that -- django-redis
    # has IGNORE_EXCEPTIONS, but the built-in backend forwards unrecognised
    # OPTIONS keys into redis.ConnectionPool.from_url(), which rejects them
    # with a TypeError on first cache access. config.cache implements the
    # behaviour instead; see the module docstring for the fail-open tradeoff.
    _redis_backend = 'config.cache.ResilientRedisCache'
    CACHES = {
        'default': {
            'BACKEND': _redis_backend,
            'LOCATION': REDIS_URL,
        },
        # Login lockout counters live in their own alias so throttle traffic
        # and lockout state can never evict one another. See the LocMem
        # branch below for why that matters.
        'lockout': {
            'BACKEND': _redis_backend,
            'LOCATION': REDIS_URL,
            'KEY_PREFIX': 'lockout',
        },
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'clearspend-default',
        },
        # Separate alias, and a ceiling far above LocMemCache's default of
        # 300. Sharing one cache let a flood of failed logins against junk
        # addresses cull a real account's lockout counter back to zero --
        # every distinct address submitted creates its own entry, and
        # eviction does not distinguish lockout state from throttle state.
        'lockout': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'clearspend-lockout',
            'OPTIONS': {'MAX_ENTRIES': 10000, 'CULL_FREQUENCY': 10},
        },
    }


# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        # Subclass of SimpleJWT's JWTAuthentication that additionally checks
        # the user's token_version, giving us revocation of *access* tokens.
        'subscriptions.authentication.VersionedJWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': '20/min',
        'user': '120/min',
        # Dedicated bucket for credential submission. Kept separate from
        # `anon` so it can be tightened without also throttling token
        # refreshes, which share the anon bucket and would otherwise start
        # failing for everyone behind shared NAT.
        'login': '10/min',
    },
    'DEFAULT_PAGINATION_CLASS': 'subscriptions.pagination.DefaultPagination',
    'PAGE_SIZE': env_int('API_PAGE_SIZE', 100),
}

if not DEBUG:
    # DRF's browsable API renders an interactive HTML surface over every
    # endpoint. Useful in development, not something to expose in production.
    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = (
        'rest_framework.renderers.JSONRenderer',
    )

# DRF derives the client IP from REMOTE_ADDR, walking back NUM_PROXIES hops
# through X-Forwarded-For. Getting this wrong breaks throttling in one of two
# directions: left at 0 behind a load balancer, every anonymous client shares
# the balancer's single bucket; set too high (or if XFF is trusted blindly),
# an attacker spoofs the header and becomes unlimited distinct clients.
# Set it to the exact number of proxies that append to XFF in front of Django.
# Always publish the value -- never guard on truthiness. DRF's own default is
# None, not 0, and BaseThrottle.get_ident branches on `is not None`: with the
# key absent it uses the *entire* X-Forwarded-For header as the throttle
# identity, so any client mints unlimited buckets just by varying the header.
# Publishing 0 explicitly means REMOTE_ADDR only, which is what the comment
# above actually promises.
REST_FRAMEWORK['NUM_PROXIES'] = env_int('NUM_PROXIES', 0)
NUM_PROXIES = REST_FRAMEWORK['NUM_PROXIES']

# Diagnostic, off by default. When on, GET /api/currencies/ logs every
# request header that could carry the client IP, alongside the identity DRF's
# throttles currently derive, so the right NUM_PROXIES / trusted header can be
# read off real traffic (see COOKIE_AUTH_PLAN.md, Phase 0). IPs are personal
# data: switch it on, send a few requests, switch it off.
LOG_CLIENT_IP_HEADERS = env_bool('LOG_CLIENT_IP_HEADERS', False)


# ---------------------------------------------------------------------------
# Simple JWT
# ---------------------------------------------------------------------------

# Decoupled from SECRET_KEY on purpose. Because SimpleJWT falls back to
# SECRET_KEY when SIGNING_KEY is unset, rotating the Django key would log out
# every user in the same breath. Splitting them makes SECRET_KEY rotation a
# non-event and turns JWT_SIGNING_KEY rotation into a deliberate
# "invalidate every outstanding token" lever.
JWT_SIGNING_KEY = os.environ.get('JWT_SIGNING_KEY') or SECRET_KEY

# Retired signing keys, still accepted for *verification* only (new tokens are
# always signed with JWT_SIGNING_KEY). To rotate without logging anyone out:
# move the old key here, set a new JWT_SIGNING_KEY, and remove the old one
# after REFRESH_TOKEN_HOURS. To log everyone out instead, rotate and leave
# this empty. See subscriptions/tokens.py::RotatingKeyTokenBackend.
JWT_PREVIOUS_SIGNING_KEYS = env_list('JWT_PREVIOUS_SIGNING_KEYS')

# HS256 is only as strong as its key; a short one can be brute-forced
# offline from any single captured token, after which an attacker can mint
# tokens for every user. 32 bytes matches the hash output size (RFC 7518
# 3.2). Enforced in production only, so the dev fallback key still boots.
JWT_MIN_KEY_BYTES = 32


def validate_jwt_key(name, key):
    if len(key.encode()) < JWT_MIN_KEY_BYTES:
        raise ImproperlyConfigured(
            f'{name} must be at least {JWT_MIN_KEY_BYTES} bytes '
            '(JWT_SIGNING_KEY falls back to SECRET_KEY when unset). '
            'Generate one with get_random_secret_key().'
        )


if not (DEBUG or RUNNING_TESTS):
    validate_jwt_key('JWT_SIGNING_KEY', JWT_SIGNING_KEY)
    for _key in JWT_PREVIOUS_SIGNING_KEYS:
        validate_jwt_key('JWT_PREVIOUS_SIGNING_KEYS', _key)

SIMPLE_JWT = {
    # Pinned rather than inherited from the library default, so an upgrade
    # or a stray edit can't widen what verification accepts. Decoding passes
    # exactly this one algorithm to PyJWT, which rejects `none` and any
    # HS/RS confusion.
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': JWT_SIGNING_KEY,
    # Stamped on every token and required on every decode. Cheap insurance
    # against a token minted for some other service that happens to share
    # a key (e.g. a copied .env) being accepted here.
    'ISSUER': os.environ.get('JWT_ISSUER', 'clearspend'),
    'AUDIENCE': os.environ.get('JWT_AUDIENCE', 'clearspend-api'),
    # Verifies via RotatingKeyTokenBackend (overlapping keys) instead of
    # SimpleJWT's single-key module-level backend.
    'AUTH_TOKEN_CLASSES': ('subscriptions.tokens.VersionedAccessToken',),
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=env_int('ACCESS_TOKEN_MINUTES', 15)),
    # Sets the outer bound on every compromise window in the threat model:
    # a stolen refresh token is usable for this long. Tunable so it can be
    # shortened without a code change.
    'REFRESH_TOKEN_LIFETIME': timedelta(hours=env_int('REFRESH_TOKEN_HOURS', 24)),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# Grace period during which a just-rotated refresh token is still accepted.
# Without it, two browser tabs refreshing in the same instant race: the loser
# gets a blacklisted-token error and logs the user out of every tab, because
# localStorage is shared. The frontend also holds a cross-tab lock
# (lib/api.js); this is the server-side backstop for when that lock is
# unavailable. Set to 0 to disable and get strict single-use semantics.
REFRESH_REUSE_GRACE_SECONDS = env_int('REFRESH_REUSE_GRACE_SECONDS', 10)

# Refresh token as an HttpOnly cookie (COOKIE_AUTH_PLAN.md, Phase 1).
# HttpOnly keeps it out of reach of page script; SameSite=Strict keeps it off
# cross-site requests; the path confines it to the endpoints that consume it
# instead of riding along on every API call. No Domain attribute, so the
# browser scopes it to the host it actually sees -- the frontend host, since
# /api is reached through a same-site proxy rewrite.
REFRESH_COOKIE_NAME = 'clearspend_refresh'
REFRESH_COOKIE_PATH = '/api/auth/'
REFRESH_COOKIE_SAMESITE = 'Strict'
REFRESH_COOKIE_SECURE = env_bool('REFRESH_COOKIE_SECURE', not DEBUG)

# Transition switch. While True, the refresh token is also returned in JSON
# and accepted from the request body, so the frontend that predates the
# cookie keeps working across the deploy. Turn off once the cookie-based
# frontend has been live for REFRESH_TOKEN_HOURS (Phase 3).
REFRESH_TOKEN_IN_BODY = env_bool('REFRESH_TOKEN_IN_BODY', True)

# Browser origins allowed to call the auth endpoints, checked against the
# Origin header. This is the login-CSRF defence (a cookie-setting endpoint a
# foreign page could otherwise POST to) and a second layer on refresh/logout.
# Separate from FRONTEND_ORIGIN, which stays blank on a same-origin deploy
# because it drives CORS. Required in production: an empty list would reject
# every browser login, so fail at boot rather than at the first user.
AUTH_TRUSTED_ORIGINS = env_list('AUTH_TRUSTED_ORIGINS')
if not AUTH_TRUSTED_ORIGINS:
    if DEBUG or RUNNING_TESTS:
        AUTH_TRUSTED_ORIGINS = ['http://localhost:5173', 'http://localhost:3000']
    else:
        raise ImproperlyConfigured(
            'AUTH_TRUSTED_ORIGINS must be set when DEBUG is False -- the '
            "SPA's public origin(s), e.g. https://clear-spend-swart.vercel.app"
        )


# ---------------------------------------------------------------------------
# External services
# ---------------------------------------------------------------------------

EXCHANGE_RATE_API_BASE_URL = os.environ.get(
    'EXCHANGE_RATE_API_BASE_URL',
    'https://api.frankfurter.dev',
)

# Rates feed straight into the money path, so the transport must be
# authenticated. Enforced at boot rather than at fetch time so a misconfigured
# deploy fails loudly instead of quietly ingesting MITM-able numbers.
if not EXCHANGE_RATE_API_BASE_URL.startswith('https://'):
    raise ImproperlyConfigured(
        'EXCHANGE_RATE_API_BASE_URL must use https:// -- exchange rates are '
        f'an input to financial calculations. Got: {EXCHANGE_RATE_API_BASE_URL!r}'
    )

# Reject a synced rate that moved more than this fraction from the stored
# value (0.20 = 20%). Guards against provider glitches and unit changes in a
# way an absolute range check cannot: IDR/USD is ~16,000, so a 100x error
# still lands inside any plausible fixed window.
EXCHANGE_RATE_MAX_DEVIATION = float(os.environ.get('EXCHANGE_RATE_MAX_DEVIATION', '0.20'))

# Age past which a stored rate is reported in the projections `warnings`
# array instead of being served as though it were current.
EXCHANGE_RATE_STALE_AFTER_DAYS = env_int('EXCHANGE_RATE_STALE_AFTER_DAYS', 7)


# ---------------------------------------------------------------------------
# Authentication hardening
# ---------------------------------------------------------------------------

# Per-account lockout. Counted against the submitted email rather than the
# client IP: an IP-keyed lockout punishes NAT'd offices and mobile carriers
# while a distributed attacker walks straight past it.
LOGIN_FAILURE_LIMIT = env_int('LOGIN_FAILURE_LIMIT', 8)
LOGIN_FAILURE_WINDOW_SECONDS = env_int('LOGIN_FAILURE_WINDOW_SECONDS', 900)

# Hard ceiling on rows a single account can create. The projections endpoint
# iterates every active subscription, so without a cap one account can grow
# its own request cost without bound.
MAX_SUBSCRIPTIONS_PER_USER = env_int('MAX_SUBSCRIPTIONS_PER_USER', 500)
MAX_CATEGORIES_PER_USER = env_int('MAX_CATEGORIES_PER_USER', 100)


# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

STATIC_URL = 'static/'
# Required for collectstatic; without it DEBUG=False renders /admin/ unstyled.
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise's compressed+hashed backend. Hashed filenames are what make the
# far-future cache headers safe, and the manifest makes a missing static file
# a build-time error rather than a silent 404 in production.
#
# Deliberately not applied under DEBUG or the test runner: the manifest backend
# requires collectstatic to have run, and raising on a missing entry would
# break `runserver` and `manage.py test` on a clean checkout.
if not (DEBUG or RUNNING_TESTS):
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ---------------------------------------------------------------------------
# Content Security Policy
# ---------------------------------------------------------------------------

# This host serves JSON, plus /admin/ and (in DEBUG) the browsable API. A
# document served from here should never be able to load third-party script
# or be framed. The SPA ships its own, stricter policy at build time --
# see frontend/vite.config.js.
CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        'default-src': [SELF],
        'script-src': [SELF],
        'style-src': [SELF],
        'img-src': [SELF, 'data:'],
        'font-src': [SELF],
        'connect-src': [SELF],
        'object-src': [NONE],
        'base-uri': [NONE],
        'form-action': [SELF],
        'frame-ancestors': [NONE],
    },
}


# ---------------------------------------------------------------------------
# Transport security (production only)
# ---------------------------------------------------------------------------

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # HSTS ramp. Start at an hour and raise it only once you have confirmed
    # every hostname is served over TLS -- the header is honoured by browsers
    # for its full duration and cannot be recalled. INCLUDE_SUBDOMAINS and
    # PRELOAD are opt-in because on a shared platform domain
    # (*.onrender.com, *.vercel.app) they affect sibling tenants and are
    # effectively irreversible.
    SECURE_HSTS_SECONDS = env_int('SECURE_HSTS_SECONDS', 3600)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
    SECURE_HSTS_PRELOAD = env_bool('SECURE_HSTS_PRELOAD', False)

# DANGER: only enable when Django is unreachable except through a proxy that
# *overwrites* X-Forwarded-Proto on every request. If any path reaches the
# app directly, a client can send `X-Forwarded-Proto: https` on a plaintext
# request and Django will believe it: SECURE_SSL_REDIRECT becomes a no-op and
# Secure cookies get written over HTTP. Not inferred from DEBUG -- it must be
# an explicit statement about the deployment topology.
if env_bool('TRUST_PROXY_SSL_HEADER', False):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

# Without an explicit config, DEBUG=False routes ERROR to mail_admins -- and
# with ADMINS unset that means 500s go nowhere at all. A console handler at
# least reaches the platform log drain.
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').strip().upper()

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        # Authentication events: logins, failures, lockouts, revocations.
        'clearspend.security': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'subscriptions': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
    },
}
