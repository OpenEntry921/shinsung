#!/bin/sh
set -eu
umask 077
python manage.py migrate --noinput
# Explicit opt-in for a synthetic-only development service. The command refuses
# production, real rosters and conflicting accounts before modifying member data.
if [ "${DEMO_LOGIN_ENABLED:-false}" = "true" ]; then
    python manage.py seed_demo --enable-login
fi
python manage.py bootstrap_roles
python manage.py collectstatic --noinput
# SQLite: one synchronous worker; use a supported PostgreSQL migration before scaling.
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 1 --timeout 30 --error-logfile -
