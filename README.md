# 🛒 Ecommerce Microservices

A complete e-commerce platform built with Django microservices architecture.

## Tech Stack
- **Backend:** Python 3.10, Django 5.2, Django REST Framework
- **Databases:** PostgreSQL, MySQL
- **Infrastructure:** Docker, Docker Compose
- **Services:** 12 independent microservices

## Services
- **API Gateway** - Main entry point
- **Customer Service** - User management
- **Book Service** - Book data management
- **Product Service** - Catalog management, browsing, and search
- **Cart Service** - Shopping cart
- **Order Service** - Order management
- **Payment Service** - Payment processing
- **Shipping Service** - Delivery tracking
- **Reviews & Ratings** - Customer feedback
- **Recommendations** - AI suggestions
- **Manager Service** - Admin dashboard
- **Staff Service** - Staff management

## Quick Start

### Prerequisites
- **Product Service** - Catalog management, browsing, and search
- Docker Compose 2.0+
- 4GB RAM, 20GB disk

### Setup
```bash
# Navigate to project directory
cd d:\ecommerce-micro05

# Start all services
docker-compose up -d

# Verify services
docker-compose ps
```

### Stop Services
```bash
docker-compose down
```

## Project Structure
```
api_gateway/        - API entry point
book-service/       - Book management
customer-service/   - User accounts
cart-service/       - Shopping cart
order-service/      - Order processing
pay-service/        - Payments
ship-service/       - Shipping
[other services]    - Additional features
```

## Default Ports
- API Gateway: 8000
- Databases: PostgreSQL (5432), MySQL (3307)
- Services: 8001-8009

## Notes
- All services use PostgreSQL/MySQL for data persistence
- Services communicate via REST APIs
- Each service is independently deployable
- Docker Compose orchestrates all containers

# Wait 30 seconds for databases and services to initialize
```

### **Verify It's Running**
```bash
# Check all containers
docker-compose ps

# Test API Gateway
curl http://localhost:8000/api/proxy/books/

# Should return: [] or JSON array (empty list is OK)
```

### **View Logs**
```bash
# Follow logs (Ctrl+C to stop)
docker-compose logs -f

# Check specific service
docker-compose logs customer-service
```

**🎉 Success!** System ready for testing.

---

## 📋 System Architecture

### **12 Services at a Glance**

| # | Service | Port | DB | Purpose |
|---|---------|------|----|---------| 
| 1 | Customer | 8001 | MySQL | User registration, profiles |
| 2 | Book | 8002 | Postgres | Book catalog, metadata |
| 3 | Cart | 8003 | Postgres | Shopping cart operations |
| 4 | Order | 8004 | MySQL | Checkout orchestration |
| 5 | Payment | 8005 | MySQL | Payment processing |
| 6 | Shipping | 8006 | MySQL | Logistics & tracking |
| 7 | Staff | 8007 | MySQL | Employee management |
| 8 | Comment-Rate | 8008 | Postgres | Reviews, ratings, feedback |
| 9 | Product | 8009 | SQLite | Read-only discovery/search |
| 10 | Manager | 8010 | MySQL | Admin dashboard, reports |
| 11 | Recommender | 8011 | Postgres | Recommendations engine |
| 12 | API Gateway | 8000 | None | Request routing |

### **Database Setup**
```
MySQL (port 3307)          PostgreSQL (port 5432)
├── customers              ├── books
├── orders                 ├── carts  
├── payments               ├── comments
├── shipments              ├── recommendations
├── staff                  └── ecommerce_db
└── manager               
```

---

## 🔧 API Endpoints Reference

### **Customer Service (Port 8001)**
```bash
# Register new user (auto-creates cart)
POST /api/customers/
{
  "username": "john",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "password": "secure123!"
}

# Get user profile
GET /api/customers/{id}/

# Update profile  
PUT /api/customers/{id}/
PATCH /api/customers/{id}/

# Delete account
DELETE /api/customers/{id}/
```

### **Book Service (Port 8002)**
```bash
# List all books (paginated, 10 per page)
GET /api/books/
GET /api/books/?page=2&category=programming

# Get single book
GET /api/books/{id}/

# Create book (staff only)
POST /api/books/
{
  "title": "Django for Beginners",
  "author": "William Vincent",
  "category": "programming",
  "price": 49.99,
  "stock": 100,
  "publisher": 1
}

# Update book
PUT /api/books/{id}/
PATCH /api/books/{id}/

# Update price only
PATCH /api/books/{id}/update_price/
{"price": 39.99}

# Delete book
DELETE /api/books/{id}/
```

### **Cart Service (Port 8003)**
```bash
# Get cart contents  
GET /api/carts/{id}/

# Add item to cart
POST /api/carts/{id}/add_item/
{
  "book_id": 1,
  "quantity": 2
}

# Update quantity (0 = remove)
POST /api/carts/{id}/update_item_quantity/
{
  "book_id": 1,
  "quantity": 5
}

# Get cart total
GET /api/carts/{id}/total/

# Clear cart
DELETE /api/carts/{id}/
```

### **Order Service (Port 8004)**
```bash
# Get customer's orders
GET /api/orders/

# Get single order
GET /api/orders/{id}/

# CHECKOUT (main operation - chains multiple services)
POST /api/orders/checkout/
{
  "customer_id": 1,
  "cart_id": 1,
  "shipping_address": "123 Main St, Springfield, IL 62701"
}
Response: {
  "order_id": 1,
  "status": "PAID",
  "total": 99.98,
  "tracking_number": "TRACK-1-1700000000"
}

# Verify purchase (for reviews)
POST /api/orders/verify_purchase/
{
  "customer_id": 1,
  "book_id": 5
}
Response: {"verified": true}
```

### **Payment Service (Port 8005)**
```bash
# Process payment
POST /api/payments/process/
{
  "order_id": 1,
  "amount": 99.98,
  "payment_method": "credit_card"
}

# Check payment status
GET /api/payments/{id}/

# Verify transaction
POST /api/payments/check_status/
{"order_id": 1}

# Refund
POST /api/payments/{id}/refund/
{"reason": "Customer request"}
```

### **Shipping Service (Port 8006)**
```bash
# Create shipment
POST /api/shipments/create_shipment/
{
  "order_id": 1,
  "address": "123 Main St, Springfield, IL",
  "shipping_method": "standard"  # or "express", "overnight"
}

# Get shipment
GET /api/shipments/{id}/

# Track shipment
POST /api/shipments/track/
{"order_id": 1}

# Update status
PATCH /api/shipments/{id}/update_status/
{"status": "IN_TRANSIT"}
```

### **Staff Service (Port 8007)**
```bash
# Create staff account
POST /api/staff/
{
  "username": "alice",
  "email": "alice@ecommerce.com",
  "password": "staff123!",
  "role": "editor",  # admin, editor, viewer
  "department": "Content"
}

# List staff
GET /api/staff/

# Get staff details
GET /api/staff/{id}/

# Check permissions
POST /api/staff/{id}/check_permission/
{"operation": "create_book"}

# Manage books (create/update/delete via staff)
POST /api/staff/{id}/manage_books/
{
  "operation": "create",
  "book_data": {
    "title": "New Title",
    "author": "Author",
    "price": 29.99,
    "category": "fiction",
    "stock": 50
  }
}
```

### **Comment-Rate Service (Port 8008)**
```bash
# Create review (must verify purchase first)
POST /api/comments/
{
  "customer_id": 1,
  "book_id": 5,
  "rating": 5,  # 1-5 stars
  "content": "Amazing book! Highly recommended!"
}

# Get reviews by book
GET /api/comments/by_book/?book_id=5

# Get average rating
GET /api/comments/get_average_rating/?book_id=5
Response: {"average_rating": 4.5, "count": 142}

# Mark review as helpful
POST /api/comments/{id}/helpful/
{"helpful": true}

# Delete review  
DELETE /api/comments/{id}/
```

### **Product Service (Port 8009)**
```bash
# List products
GET /api/products/

# Search by keyword
GET /api/products/?search=programming

# Filter by category / type / brand
GET /api/products/?category=electronics&type=laptop&brand=apple

# Browse by category
GET /api/products/by_category/?category=electronics

# Browse by type
GET /api/products/by_type/?type=mobile

# Browse by brand
GET /api/products/by_brand/?brand=samsung
```

### **Manager Service (Port 8010)**
```bash
# Dashboard overview
GET /api/manager/dashboard/
Response: {
  "total_revenue": 52000,
  "orders_count": 1250,
  "avg_order_value": 41.60,
  "customer_satisfaction": 0.94
}

# Sales report
GET /api/manager/sales_report/

# Inventory report
GET /api/manager/inventory_report/

# Shipping report
GET /api/manager/shipping_report/
```

### **Recommender Service (Port 8011)**
```bash
# Get personalized recommendations
GET /api/recommendations/recommend_for_customer/?customer_id=1
Response: [
  {"id": 10, "title": "Design Patterns", "score": 0.92},
  {"id": 20, "title": "Refactoring", "score": 0.87}
]

# Get similar books
GET /api/recommendations/similar_books/?book_id=5

# Get trending books
GET /api/recommendations/trending_books/
```

### **API Gateway (Port 8000)**
Gateway proxies all requests to backend services:
```bash
# Instead of: POST /api/customers/ on customer-service:8001
# Use: POST /api/proxy/customers/ on gateway:8000

POST /api/proxy/customers/
GET /api/proxy/books/
POST /api/proxy/carts/{id}/add_item/
POST /api/proxy/orders/checkout/
GET /api/proxy/recommendations/...
# ... all other endpoints
```

---

## 📊 Complete Purchase Workflow Example

```bash
# 1️⃣ REGISTER CUSTOMER (auto-creates cart)
curl -X POST http://localhost:8000/api/proxy/customers/ \
-H "Content-Type: application/json" \
-d '{
  "username": "jane",
  "email": "jane@example.com",
  "first_name": "Jane",
  "last_name": "Smith",
  "password": "MyPassword123!"
}'
# Result: customer_id=1, cart_id=1

# 2️⃣ BROWSE PRODUCTS
curl http://localhost:8000/api/proxy/products/?search=programming
# Result: [product1, product2, product3, ...]

# 3️⃣ ADD TO CART
curl -X POST http://localhost:8000/api/proxy/carts/1/add_item/ \
-H "Content-Type: application/json" \
-d '{
  "book_id": 1,
  "quantity": 2
}'
# Result: item added

# 4️⃣ CHECKOUT (chains: payment + shipping)
curl -X POST http://localhost:8000/api/proxy/orders/checkout/ \
-H "Content-Type: application/json" \
-d '{
  "customer_id": 1,
  "cart_id": 1,
  "shipping_address": "456 Oak Ave, New York, NY 10001"
}'
# Result: order_id=1, status=PAID, tracking=TRACK-1-...

# 5️⃣ LEAVE REVIEW (after purchase verified)
curl -X POST http://localhost:8000/api/proxy/comments/ \
-H "Content-Type: application/json" \
-d '{
  "customer_id": 1,
  "book_id": 1,
  "rating": 5,
  "content": "Excellent book! Learned so much."
}'
# Result: review created

# 6️⃣ GET RECOMMENDATIONS
curl http://localhost:8000/api/proxy/recommendations/recommend_for_customer/?customer_id=1
# Result: [similar_book1, similar_book2, ...]

# 7️⃣ CHECK ORDER STATUS
curl http://localhost:8000/api/proxy/orders/1/

# 8️⃣ TRACK SHIPMENT
curl -X POST http://localhost:8000/api/proxy/shipments/track/ \
-H "Content-Type: application/json" \
-d '{"order_id": 1}'
# Result: {"status": "IN_TRANSIT", "tracking": "TRACK-1-...", "location": "Chicago, IL"}
```

---

## 🗄️ Database Access

### **Access MySQL**
```bash
# Via command line
mysql -h localhost -P 3307 -u root -p
# Password: root

# Sample queries
USE ecommerce_db;
SELECT * FROM customers;
SELECT * FROM orders;
```

### **Access PostgreSQL**
```bash
# Via command line  
psql -h localhost -U postgres -d ecommerce_db
# Password: root

# Sample queries
SELECT * FROM books;
SELECT * FROM comments;
SELECT * FROM recommendations;
```

### **Use GUI Tools (Recommended)**
- **DBeaver** (Free, all databases)
  - Download: dbeaver.io
  - Connection → MySQL/PostgreSQL → localhost
  
- **MySQL Workbench** (MySQL only)
  - Download: MySQL official site
  
- **pgAdmin** (PostgreSQL only)
  - Access: http://localhost:5050 (if container included)

---

## 🛠️ Development Commands

### **Container Commands**
```bash
# View all containers
docker-compose ps

# View logs (follow)  
docker-compose logs -f

# View specific service logs
docker-compose logs -f customer-service

# Stop all services
docker-compose stop

# Stop specific service
docker-compose stop customer-service

# Restart service
docker-compose restart customer-service

# Remove everything
docker-compose down -v

# Enter container shell
docker-compose exec customer-service bash

# Run Django command in container
docker-compose exec customer-service python manage.py createsuperuser

# Check port usage
# Windows:
netstat -ano | findstr :8000

# Mac/Linux:
lsof -i :8000
```

### **Django Management**
```bash
# Make migrations
docker-compose exec book-service python manage.py makemigrations

# Run migrations
docker-compose exec book-service python manage.py migrate

# Create superuser
docker-compose exec customer-service python manage.py createsuperuser

# Shell access
docker-compose exec customer-service python manage.py shell
```

### **Testing Endpoints**
```bash
# Using curl (built-in Windows 10+)
curl http://localhost:8000/api/proxy/books/

# Using httpie (install: pip install httpie)
http :8000/api/proxy/books/

# Using Postman
# Create new request → GET → http://localhost:8000/api/proxy/books/

# Using Python
python -c "import requests; print(requests.get('http://localhost:8000/api/proxy/books/').json())"
```

---

## 📁 Project Structure

```
ecommerce-micro05/
├── docker-compose.yml          # Service orchestration
├── QUICK_START.md              # 5-minute setup guide
├── ARCHITECTURE.md             # Detailed architecture
├── README.md                   # This file
│
├── api_gateway/                # Service 12: Request router
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── manage.py
│   ├── requirements.txt
│   ├── api_gateway/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── app/
│   │   ├── views.py           # api_proxy endpoint
│   │   └── urls.py
│   └── templates/
│
├── customer-service/           # Service 1: User management
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── requirements.txt
│   ├── app/
│   │   ├── models.py          # Customer, CustomerProfile
│   │   ├── serializers.py
│   │   ├── views.py           # CustomerViewSet
│   │   └── urls.py
│   └── customer_service/
│
├── book-service/               # Service 2: Book catalog
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── requirements.txt
│   ├── app/
│   │   ├── models.py          # Book, Category, Publisher
│   │   ├── serializers.py
│   │   ├── views.py           # BooksViewSet
│   │   └── urls.py
│   └── book_service/
│
├── cart-service/               # Service 3: Shopping cart
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── requirements.txt
│   ├── app/
│   │   ├── models.py          # Cart, CartItem
│   │   ├── serializers.py
│   │   ├── views.py           # CartViewSet
│   │   └── urls.py
│   └── cart_service/
│
├── order-service/              # Service 4: Order management
│   └── ... (similar structure)
│
├── pay-service/                # Service 5: Payments
│   └── ... (similar structure)
│
├── ship-service/               # Service 6: Shipping
│   └── ... (similar structure)
│
├── staff-service/              # Service 7: Staff management
│   └── ... (similar structure)
│
├── comment-rate-service/       # Service 8: Reviews/ratings
│   └── ... (similar structure)
│
├── manager-service/            # Service 10: Dashboard
│   └── ... (similar structure)
│
├── recommender-ai-service/     # Service 11: Recommendations
│   └── ... (similar structure)
│
└── requirements-all.txt        # All dependencies combined
```

---

## 🧪 Testing the System

### **Health Check Script**
```bash
#!/bin/bash
echo "Testing all services..."

for port in 8000 8001 8002 8003 8004 8005 8006 8007 8008 8009 8010 8011; do
  echo "Testing :$port"
  curl -s http://localhost:$port/api/ | head -20
  echo ""
done
```

### **Postman Collection**
Create requests in Postman for each endpoint:
1. Open Postman
2. Create new Collection "Ecommerce"
3. Add requests for each endpoint
4. Use variables: {{base_url}} = http://localhost:8000/api/proxy

---

## 🔍 Troubleshooting

### **Port Already in Use**
```bash
# Windows: Find process
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Mac/Linux: Find process  
lsof -i :8000
kill -9 <PID>

# Alternative: Change ports in docker-compose.yml
# "8000:8000" → "9000:8000"
```

### **Services Not Communicating**
```bash
# Check if all services are running
docker-compose ps

# Check network
docker network ls
docker network inspect ecommerce-micro05_ecommerce-network

# Inspect service DNS
docker-compose exec customer-service ping book-service

# View full logs
docker-compose logs | grep -i error
```

### **Database Connection Errors**
```bash
# Check MySQL is running
docker-compose logs db-mysql | tail -20

# Check PostgreSQL is running
docker-compose logs db-postgres | tail -20

# Restart databases
docker-compose restart db-mysql db-postgres
docker-compose up -d
```

### **Django Migration Errors**
```bash
# Check migration status
docker-compose exec customer-service python manage.py showmigrations

# Run migrations manually
docker-compose exec customer-service python manage.py migrate --noinput

# Check app migrations
docker-compose exec customer-service python manage.py migrate app
```

### **Empty Response from API**
```bash
# Check service is responding
curl -v http://localhost:8001/api/customers/

# Check logs
docker-compose logs customer-service

# Verify URL format
# Correct: GET http://localhost:8001/api/customers/
# Incorrect: GET http://localhost:8001/api/customers (no trailing slash)
```

---

## 🔐 Security (Production Checklist)

- [ ] Add JWT authentication to API Gateway
- [ ] Implement service-to-service API keys
- [ ] Whitelist CORS origins (don't use *)
- [ ] Add rate limiting per endpoint
- [ ] Use environment variables for secrets
- [ ] Implement HTTPS/TLS
- [ ] Add request validation & sanitization
- [ ] Set up API key rotation
- [ ] Add comprehensive logging
- [ ] Implement circuit breaker pattern
- [ ] Add request timeouts
- [ ] Use secrets management (AWS Secrets, HashiCorp Vault)

---

## 📚 Learning Resources

- **Django Documentation:** https://docs.djangoproject.com/
- **Django REST Framework:** https://www.django-rest-framework.org/
- **Docker Compose:** https://docs.docker.com/compose/
- **PostgreSQL:** https://www.postgresql.org/docs/
- **MySQL:** https://dev.mysql.com/doc/
- **Microservices Patterns:** https://microservices.io/

---

## 🤝 Contributing

To modify or add features:

1. **Branch:** Create feature branch
2. **Code:** Make changes in service directories
3. **Test:** Test locally with docker-compose
4. **Docs:** Update ARCHITECTURE.md if structure changes
5. **Commit:** Push with clear messages

---

## 📞 Support

**Common Issues:**
- Check logs: `docker-compose logs service-name`
- Verify containers: `docker-compose ps`
- Test connectivity: `curl http://localhost:8001/api/...`

**Debug Mode:**
```bash
# View all requests/responses
docker-compose logs -f | grep -i "request\|response\|error"
```

---

## 📄 License

This project is provided as-is for educational and development purposes.

---

## 📊 Performance Metrics (Expected)

- **API Response Time:** 50-200ms (depends on operation)
- **Database Query Time:** 5-50ms
- **Service-to-Service Latency:** 10-30ms
- **Container Startup Time:** 5-10 seconds per service
- **Full System Initialization:** 30-60 seconds

---

## ✅ Checklist Before Going Live

- [ ] All services running (`docker-compose ps` shows all UP)
- [ ] Databases initialized and migrated
- [ ] API Gateway accessible on port 8000
- [ ] Complete workflow tested (register → cart → order → review)
- [ ] All endpoint responses valid JSON
- [ ] Logs checked for errors
- [ ] No port conflicts
- [ ] Database connections verified
- [ ] Services can reach each other
- [ ] Performance acceptable

---

**🎉 You're ready to go!** Start with QUICK_START.md and explore the API endpoints.

**Questions?** Check ARCHITECTURE.md for detailed service descriptions.

---

*Built with ❤️ using Django, DRF, and Docker*
