#!/usr/bin/env bash
# Render build script. Set this as the "Build Command" in your Render service.
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py compilemessages --locale=ko
python manage.py migrate
python manage.py ensure_superuser
python manage.py ensure_forum
