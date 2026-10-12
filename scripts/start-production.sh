#!/bin/sh
set -eu
umask 077
python manage.py migrate --noinput
if [ "${APP_MODE:-production}" = "development" ]; then
    python manage.py seed_demo
fi
python manage.py bootstrap_roles
python manage.py collectstatic --noinput
# SQLite: one synchronous worker; use a supported PostgreSQL migration before scaling.
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 1 --timeout 30 --error-logfile -
