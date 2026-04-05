#!/bin/bash
set -e
echo "Auth-service: waiting for DB..."
for i in {1..30}; do
    python manage.py migrate --noinput 2>&1 && break || sleep 2
done
echo "Starting auth-service..."
python manage.py runserver 0.0.0.0:8000
