@echo off
REM Migration script for Bookstore Microservices (Windows)

echo Starting migrations for all services...

REM Customer Service
echo Migrating customer-service...
docker compose exec -T customer-service python manage.py migrate --noinput

REM Book Service
echo Migrating book-service...
docker compose exec -T book-service python manage.py migrate --noinput

REM Cart Service
echo Migrating cart-service...
docker compose exec -T cart-service python manage.py migrate --noinput

REM Order Service
echo Migrating order-service...
docker compose exec -T order-service python manage.py migrate --noinput

REM Payment Service
echo Migrating pay-service...
docker compose exec -T pay-service python manage.py migrate --noinput

REM Shipping Service
echo Migrating ship-service...
docker compose exec -T ship-service python manage.py migrate --noinput

REM Staff Service
echo Migrating staff-service...
docker compose exec -T staff-service python manage.py migrate --noinput

REM Comment Rating Service
echo Migrating comment-rate-service...
docker compose exec -T comment-rate-service python manage.py migrate --noinput

REM Catalog Service (SQLite)
echo Migrating catalog-service...
docker compose exec -T catalog-service python manage.py migrate --noinput

REM Manager Service
echo Migrating manager-service...
docker compose exec -T manager-service python manage.py migrate --noinput

REM Recommender AI Service
echo Migrating recommender-ai-service...
docker compose exec -T recommender-ai-service python manage.py migrate --noinput

REM API Gateway (SQLite)
echo Migrating api-gateway...
docker compose exec -T api-gateway python manage.py migrate --noinput

echo All migrations completed!
pause
