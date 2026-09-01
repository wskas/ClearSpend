#!/bin/sh
# Boot sequence for the web container.
#
# migrate runs here rather than in the image build because the build has no
# database. This is safe for the single-web-service topology this deploy
# targets; if you ever scale to multiple replicas, move migrate into a
# one-off `docker compose run --rm web python manage.py migrate` step in the
# release process so two containers cannot race the migration lock.
set -e

echo "==> Applying migrations"
python manage.py migrate --noinput

# collectstatic is NOT here -- it runs at image build time (see Dockerfile).
# On a platform that sleeps idle instances, anything in this script is paid
# again on every cold start, and collectstatic is by far the slowest step.

# Platforms that assign a port (Render, Heroku, Cloud Run) require the process
# to bind $PORT, or the service is never detected as live and the deploy fails.
# The :-8000 default keeps docker-compose, where the port is fixed, unchanged.
echo "==> Starting gunicorn"
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-60}" \
    --access-logfile - \
    --error-logfile -
