# Matches the 3.11.7 used in development. Pinned to a minor version on
# purpose: a silent jump to a new Python across a redeploy is exactly the
# kind of change that should be a deliberate edit.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# curl is here for the compose healthcheck and nothing else. psycopg2-binary
# ships wheels with libpq bundled, so no build toolchain is required; if you
# ever swap it for source psycopg2, this is where libpq-dev and gcc go.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# Dependencies in their own layer, so application edits don't reinstall them.
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

# Static files are collected at BUILD time, not on boot. On a platform that
# sleeps idle instances, anything in the entrypoint is paid again on every
# cold start, and on a 0.1-CPU instance collectstatic is the slowest step.
#
# The throwaway values are needed only to satisfy import-time checks: settings
# requires SECRET_KEY (>= 32 bytes, since it is also the JWT key fallback) and
# AUTH_TRUSTED_ORIGINS whenever DEBUG is False, and DEBUG must be False here
# for CompressedManifestStaticFilesStorage to be selected at all. They sign
# and authorise nothing, are never read at runtime, and are overridden by the
# real environment on boot -- which must set both for real.
RUN SECRET_KEY=build-only-never-used-at-runtime-padding-to-50-chars DEBUG=False \
    AUTH_TRUSTED_ORIGINS=https://build-only.invalid \
    python manage.py collectstatic --noinput

# Run as a non-root user. Nothing in the app writes to the image at runtime.
RUN chmod +x /app/entrypoint.sh \
 && useradd --create-home --uid 10001 app \
 && mkdir -p /app/staticfiles \
 && chown -R app:app /app
USER app

# Documentation only -- compose uses `expose:`, never `ports:`, so this port
# is reachable from the proxy on the internal network and from nowhere else.
# See the TRUST_PROXY_SSL_HEADER note in the deploy runbook for why.
EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
