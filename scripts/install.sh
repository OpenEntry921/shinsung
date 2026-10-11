#!/bin/sh
set -eu
cd /workspace/shinsung
python -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -r requirements.txt
APP_MODE=development .venv/bin/python manage.py migrate --noinput
APP_MODE=development .venv/bin/python manage.py bootstrap_roles
APP_MODE=development .venv/bin/python manage.py check
