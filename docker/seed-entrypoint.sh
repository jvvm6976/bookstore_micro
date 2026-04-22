#!/bin/bash
# Seed data entrypoint - chạy seed data một lần duy nhất
# Được gọi từ docker-compose.yml sau khi tất cả services khởi động

set -e

SEED_FLAG="/tmp/.seed_data_completed"
SEED_SCRIPT="/app/seed-final.py"

echo "=========================================="
echo "  ECOMMERCE SEED DATA INITIALIZATION"
echo "=========================================="

# Chờ tất cả services sẵn sàng
echo "[*] Waiting for services to be ready..."
sleep 10

# Kiểm tra xem seed data đã chạy chưa
if [ -f "$SEED_FLAG" ]; then
    echo "[✓] Seed data already completed. Skipping..."
    exit 0
fi

# Chạy seed data
if [ -f "$SEED_SCRIPT" ]; then
    echo "[*] Running seed data script..."
    python "$SEED_SCRIPT"
    
    # Tạo flag file để đánh dấu seed data đã chạy
    touch "$SEED_FLAG"
    echo "[✓] Seed data completed successfully!"
else
    echo "[!] Seed script not found at $SEED_SCRIPT"
    exit 1
fi

echo "=========================================="
exit 0
