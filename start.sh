#!/bin/bash

# Bookstore Microservices - Quick Startup Script for Linux/Mac

set -e  # Exit on error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Clear screen
clear

echo ""
echo "=============================================================="
echo "  BOOKSTORE MICROSERVICES - STARTUP SCRIPT"
echo "=============================================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}[ERROR] Docker is not installed${NC}"
    echo "Please install Docker from: https://www.docker.com/products/docker-desktop"
    exit 1
fi

echo -e "${GREEN}[OK] Docker found:${NC}"
docker --version
echo ""

# Check if Docker is running
if ! docker ps &> /dev/null; then
    echo -e "${RED}[ERROR] Docker is not running${NC}"
    echo "Please start Docker and try again"
    exit 1
fi

echo -e "${GREEN}[OK] Docker is running${NC}"
echo ""

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}[ERROR] Docker Compose is not installed${NC}"
    echo "Please install Docker Compose"
    exit 1
fi

echo -e "${GREEN}[OK] Docker Compose found:${NC}"
docker-compose --version
echo ""

# Change to script directory
cd "$SCRIPT_DIR"
echo "[INFO] Working directory: $SCRIPT_DIR"
echo ""

# Menu
echo "Choose an option:"
echo ""
echo "  1. Clean & Start (removes old containers, fresh build)"
echo "  2. Start (quick start with existing images)"
echo "  3. Stop (stop all services)"
echo "  4. Restart (restart all services)"
echo "  5. View Logs (follow logs from all services)"
echo "  6. Test System (run connectivity test)"
echo "  7. Status (show container status)"
echo "  8. Shell (enter service shell)"
echo "  9. Database MySQL (connect to MySQL)"
echo " 10. Database PostgreSQL (connect to PostgreSQL)"
echo " 11. Remove All (delete all containers/volumes)"
echo ""

read -p "Enter choice (1-11): " choice

case $choice in
    1)
        echo ""
        echo -e "${YELLOW}[1/3] Removing old containers...${NC}"
        docker-compose down -v
        echo -e "${GREEN}[OK] Old containers removed${NC}"
        echo ""
        
        echo -e "${YELLOW}[2/3] Building images (this may take 3-5 minutes)...${NC}"
        docker-compose build --no-cache
        echo -e "${GREEN}[OK] Images built${NC}"
        echo ""
        
        echo -e "${YELLOW}[3/3] Starting services...${NC}"
        docker-compose up -d
        echo -e "${GREEN}[OK] Services started${NC}"
        echo ""
        
        echo -e "${YELLOW}Waiting for services to initialize (30 seconds)...${NC}"
        sleep 30
        echo ""
        
        echo -e "${GREEN}[SUCCESS] System is ready!${NC}"
        echo ""
        echo "Next steps:"
        echo "  1. Check status: docker-compose ps"
        echo "  2. View logs: docker-compose logs -f"
        echo "  3. Test API: curl http://localhost:8000/api/proxy/books/"
        echo "  4. Read QUICK_START.md for more information"
        ;;
        
    2)
        echo ""
        echo -e "${YELLOW}Starting services...${NC}"
        docker-compose up -d
        echo -e "${GREEN}[OK] Services started${NC}"
        echo ""
        
        echo -e "${YELLOW}Waiting for services (20 seconds)...${NC}"
        sleep 20
        echo -e "${GREEN}[OK] Services should be ready${NC}"
        ;;
        
    3)
        echo ""
        echo -e "${YELLOW}Stopping all services...${NC}"
        docker-compose stop
        echo -e "${GREEN}[OK] All services stopped${NC}"
        ;;
        
    4)
        echo ""
        echo -e "${YELLOW}Restarting all services...${NC}"
        docker-compose restart
        echo -e "${GREEN}[OK] Services restarted${NC}"
        echo ""
        echo -e "${YELLOW}Waiting for services (10 seconds)...${NC}"
        sleep 10
        ;;
        
    5)
        echo ""
        echo -e "${YELLOW}[INFO] Showing live logs (Ctrl+C to stop)${NC}"
        echo ""
        docker-compose logs -f
        ;;
        
    6)
        echo ""
        echo -e "${YELLOW}Testing system connectivity...${NC}"
        echo ""
        
        # Test API Gateway
        echo -n "Testing API Gateway (port 8000)... "
        if curl -s http://localhost:8000/api/proxy/books/ > /dev/null 2>&1; then
            echo -e "${GREEN}[OK]${NC}"
        else
            echo -e "${RED}[FAILED]${NC}"
        fi
        
        # Test services
        echo -n "Testing Customer Service (port 8001)... "
        if curl -s http://localhost:8001/api/customers/ > /dev/null 2>&1; then
            echo -e "${GREEN}[OK]${NC}"
        else
            echo -e "${RED}[FAILED]${NC}"
        fi
        
        echo -n "Testing Book Service (port 8002)... "
        if curl -s http://localhost:8002/api/books/ > /dev/null 2>&1; then
            echo -e "${GREEN}[OK]${NC}"
        else
            echo -e "${RED}[FAILED]${NC}"
        fi
        
        echo -n "Testing Cart Service (port 8003)... "
        if curl -s http://localhost:8003/api/carts/ > /dev/null 2>&1; then
            echo -e "${GREEN}[OK]${NC}"
        else
            echo -e "${RED}[FAILED]${NC}"
        fi
        
        echo -n "Testing Order Service (port 8004)... "
        if curl -s http://localhost:8004/api/orders/ > /dev/null 2>&1; then
            echo -e "${GREEN}[OK]${NC}"
        else
            echo -e "${RED}[FAILED]${NC}"
        fi
        
        echo ""
        echo -e "${GREEN}[INFO] Test complete${NC}"
        ;;
        
    7)
        echo ""
        echo -e "${YELLOW}Container Status:${NC}"
        echo ""
        docker-compose ps
        ;;
        
    8)
        echo ""
        read -p "Enter service name (e.g., customer-service): " service
        echo ""
        echo -e "${YELLOW}Entering shell for $service...${NC}"
        echo "Type 'exit' to exit shell"
        echo ""
        docker-compose exec "$service" bash
        ;;
        
    9)
        echo ""
        echo "MySQL Connection Details:"
        echo "  Host: localhost"
        echo "  Port: 3307"
        echo "  User: root"
        echo "  Password: root"
        echo "  Database: bookstore_db"
        echo ""
        if command -v mysql &> /dev/null; then
            echo -e "${YELLOW}Connecting...${NC}"
            mysql -h localhost -P 3307 -u root -p
        else
            echo -e "${YELLOW}MySQL client not installed${NC}"
            echo "Use GUI tool like DBeaver or MySQL Workbench to connect"
        fi
        ;;
        
    10)
        echo ""
        echo "PostgreSQL Connection Details:"
        echo "  Host: localhost"
        echo "  Port: 5432"
        echo "  User: postgres"
        echo "  Password: root"
        echo "  Database: bookstore_db"
        echo ""
        if command -v psql &> /dev/null; then
            echo -e "${YELLOW}Connecting...${NC}"
            psql -h localhost -U postgres -d bookstore_db
        else
            echo -e "${YELLOW}psql not installed${NC}"
            echo "Use GUI tool like DBeaver or pgAdmin to connect"
        fi
        ;;
        
    11)
        echo ""
        echo -e "${RED}[WARNING] This will delete all containers and local data!${NC}"
        read -p "Type 'yes' to confirm: " confirm
        
        if [ "$confirm" = "yes" ]; then
            echo ""
            echo -e "${YELLOW}Removing all containers and volumes...${NC}"
            docker-compose down -v
            echo -e "${GREEN}[OK] All removed${NC}"
        else
            echo -e "${YELLOW}[CANCELLED] Nothing was removed${NC}"
        fi
        ;;
        
    *)
        echo -e "${RED}[ERROR] Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
