#!/bin/bash

# Migration script for Bookstore Microservices

echo "Starting migrations for all services..."

# Customer Service
echo "Migrating customer-service..."
docker compose exec -T customer-service python manage.py migrate --noinput

# Book Service
echo "Migrating book-service..."
docker compose exec -T book-service python manage.py migrate --noinput

# Cart Service
echo "Migrating cart-service..."
docker compose exec -T cart-service python manage.py migrate --noinput

# Order Service
echo "Migrating order-service..."
docker compose exec -T order-service python manage.py migrate --noinput

# Payment Service
echo "Migrating pay-service..."
docker compose exec -T pay-service python manage.py migrate --noinput

# Shipping Service
echo "Migrating ship-service..."
docker compose exec -T ship-service python manage.py migrate --noinput

# Staff Service
echo "Migrating staff-service..."
docker compose exec -T staff-service python manage.py migrate --noinput

# Comment Rating Service
echo "Migrating comment-rate-service..."
docker compose exec -T comment-rate-service python manage.py migrate --noinput

echo "Migrating catalog-service..."
docker compose exec -T catalog-service python manage.py migrate --noinput

# Manager Service
echo "Migrating manager-service..."
docker compose exec -T manager-service python manage.py migrate --noinput

# Recommender AI Service
echo "Migrating recommender-ai-service..."
docker compose exec -T recommender-ai-service python manage.py migrate --noinput

echo "Migrating api-gateway..."
docker compose exec -T api-gateway python manage.py migrate --noinput

echo "All migrations completed!"
