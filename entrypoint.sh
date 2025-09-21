#!/bin/sh
set -e
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser --noinput || true
exec python manage.py runserver 0.0.0.0:8000
