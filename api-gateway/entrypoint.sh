#!/bin/bash
set -e

echo "Starting api-gateway..."
python manage.py runserver 0.0.0.0:8000
