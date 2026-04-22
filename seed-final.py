"""
Seed script hoàn chỉnh - Tất cả services
- 7-10 sản phẩm mỗi loại, mỗi sản phẩm có hình ảnh riêng
- Comments/Ratings chỉ cho sản phẩm đã mua, với order_id
- Addresses cho customers
- Shipping address trong orders
Chạy: python seed-final.py
"""
import requests, random, uuid, time, re
from datetime import date, timedelta

# Services URLs (từ docker-compose.yml)
AUTH_SVC  = "http://auth-service:8000/api"      # auth-service port 8000 (internal)
CUST_SVC  = "http://customer-service:8000/api"  # customer-service port 8000 (internal)
PROD_SVC  = "http://product-service:8000/api"   # product-service port 8000 (internal)
CART_SVC  = "http://cart-service:8000/api"      # cart-service port 8000 (internal)
ORDER_SVC = "http://order-service:8000/api"     # order-service port 8000 (internal)
PAY_SVC   = "http://pay-service:8000/api"       # pay-service port 8000 (internal)
SHIP_SVC  = "http://ship-service:8000/api"      # ship-service port 8000 (internal)
STAFF_SVC = "http://staff-service:8000/api"     # staff-service port 8000 (internal)
CMT_SVC   = "http://comment-rate-service:8000/api"  # comment-rate-service port 8000 (internal)
MGR_SVC   = "http://manager-service:8000/api"   # manager-service port 8000 (internal)

def p(url, data):
    try:
        r = requests.post(url, json=data, timeout=15)
        if r.status_code not in (200, 201):
            print(f"  WARN {r.status_code}: {url.split('/')[-2]}")
        return r
    except Exception as e:
        print(f"  ERR {url}: {e}")
        return type('R', (), {'status_code': 0, 'json': lambda s: {}})()

def get(url):
    try:
        r = requests.get(url, timeout=10)
        return r.json() if r.status_code == 200 else {}
    except:
        return {}

def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')

print("=" * 70)
print("  ECOMMERCE SEED DATA - FINAL")
print("=" * 70)

# ─── CHECK: Dữ liệu đã tồn tại chưa? ──────────────────────────────────────────
print("\n[0] Checking if seed data already exists...")
existing_customers = get(f"{CUST_SVC}/customers/?page_size=1")
existing_count = 0
if isinstance(existing_customers, dict):
    existing_count = existing_customers.get("count", 0)
elif isinstance(existing_customers, list):
    existing_count = len(existing_customers)

if existing_count > 0:
    print(f"  ✓ Found {existing_count} existing customers. Skipping seed data.")
    print("=" * 70)
    exit(0)

print("  ✓ No existing data found. Proceeding with seed...")

# ─── STEP 1: Product Types ────────────────────────────────────────────────────
print("\n[1] Creating Product Types...")
TYPES = [
    {"slug": "book",       "name": "Sách",                "icon": "📚"},
    {"slug": "laptop",     "name": "Laptop",              "icon": "💻"},
    {"slug": "mobile",     "name": "Điện thoại",          "icon": "📱"},
    {"slug": "tablet",     "name": "Máy tính bảng",       "icon": "📟"},
    {"slug": "headphone",  "name": "Tai nghe",            "icon": "🎧"},
    {"slug": "smartwatch", "name": "Đồng hồ thông minh",  "icon": "⌚"},
    {"slug": "camera",     "name": "Máy ảnh",             "icon": "📷"},
    {"slug": "monitor",    "name": "Màn hình",            "icon": "🖥️"},
    {"slug": "keyboard",   "name": "Bàn phím",            "icon": "⌨️"},
    {"slug": "mouse",      "name": "Chuột",               "icon": "🖱️"},
    {"slug": "speaker",    "name": "Loa",                 "icon": "🔊"},
    {"slug": "router",     "name": "Router / Mạng",       "icon": "📡"},
]
type_ids = {}
for t in TYPES:
    r = p(f"{PROD_SVC}/product-types/", t)
    if r.status_code in (200, 201):
        type_ids[t["slug"]] = r.json()["id"]
        print(f"  ✓ {t['name']}")
    else:
        data = get(f"{PROD_SVC}/product-types/")
        results = data if isinstance(data, list) else data.get("results", [])
        for item in results:
            if item.get("slug") == t["slug"]:
                type_ids[t["slug"]] = item["id"]
                print(f"  ✓ {t['name']} (existing)")
                break

# ─── STEP 2: Categories ───────────────────────────────────────────────────────
print("\n[2] Creating Categories...")
CATS = [
    {"slug": "fiction",      "name": "Tiểu thuyết"},
    {"slug": "programming",  "name": "Lập trình"},
    {"slug": "science",      "name": "Khoa học"},
    {"slug": "history",      "name": "Lịch sử"},
    {"slug": "gaming-laptop","name": "Laptop Gaming"},
    {"slug": "ultrabook",    "name": "Ultrabook"},
    {"slug": "flagship",     "name": "Flagship"},
    {"slug": "mid-range",    "name": "Tầm trung"},
    {"slug": "budget",       "name": "Phổ thông"},
    {"slug": "tws",          "name": "True Wireless"},
    {"slug": "over-ear",     "name": "Over-ear"},
    {"slug": "smartwatch-sport","name": "Sport Watch"},
    {"slug": "mirrorless",   "name": "Mirrorless"},
    {"slug": "gaming-monitor","name": "Gaming Monitor"},
    {"slug": "4k-monitor",   "name": "4K Monitor"},
    {"slug": "mechanical-keyboard","name": "Bàn phím cơ"},
    {"slug": "wireless-mouse","name": "Chuột không dây"},
    {"slug": "bluetooth-speaker","name": "Loa Bluetooth"},
    {"slug": "wifi-router",  "name": "WiFi Router"},
]
cat_ids = {}
for c in CATS:
    r = p(f"{PROD_SVC}/categories/", c)
    if r.status_code in (200, 201):
        cat_ids[c["slug"]] = r.json()["id"]
    else:
        data = get(f"{PROD_SVC}/categories/")
        results = data if isinstance(data, list) else data.get("results", [])
        for item in results:
            if item.get("slug") == c["slug"]:
                cat_ids[c["slug"]] = item["id"]
                break
print(f"  ✓ {len(cat_ids)} categories")

# ─── STEP 3: Brands ───────────────────────────────────────────────────────────
print("\n[3] Creating Brands...")
BRANDS = [
    {"slug": "apple",    "name": "Apple",    "country": "USA"},
    {"slug": "samsung",  "name": "Samsung",  "country": "South Korea"},
    {"slug": "sony",     "name": "Sony",     "country": "Japan"},
    {"slug": "dell",     "name": "Dell",     "country": "USA"},
    {"slug": "lenovo",   "name": "Lenovo",   "country": "China"},
    {"slug": "asus",     "name": "ASUS",     "country": "Taiwan"},
    {"slug": "lg",       "name": "LG",       "country": "South Korea"},
    {"slug": "xiaomi",   "name": "Xiaomi",   "country": "China"},
    {"slug": "logitech", "name": "Logitech", "country": "Switzerland"},
    {"slug": "canon",    "name": "Canon",    "country": "Japan"},
    {"slug": "nikon",    "name": "Nikon",    "country": "Japan"},
    {"slug": "bose",     "name": "Bose",     "country": "USA"},
    {"slug": "jbl",      "name": "JBL",      "country": "USA"},
    {"slug": "tp-link",  "name": "TP-Link",  "country": "China"},
    {"slug": "asus-rog", "name": "ASUS ROG", "country": "Taiwan"},
    {"slug": "msi",      "name": "MSI",      "country": "Taiwan"},
    {"slug": "hp",       "name": "HP",       "country": "USA"},
    {"slug": "microsoft","name": "Microsoft","country": "USA"},
    {"slug": "google",   "name": "Google",   "country": "USA"},
    {"slug": "oppo",     "name": "OPPO",     "country": "China"},
]
brand_ids = {}
for b in BRANDS:
    r = p(f"{PROD_SVC}/brands/", b)
    if r.status_code in (200, 201):
        brand_ids[b["slug"]] = r.json()["id"]
    else:
        data = get(f"{PROD_SVC}/brands/")
        results = data if isinstance(data, list) else data.get("results", [])
        for item in results:
            if item.get("slug") == b["slug"]:
                brand_ids[b["slug"]] = item["id"]
                break
print(f"  ✓ {len(brand_ids)} brands")


# ─── STEP 4: Products (copy từ seed-complete.py) ────────────────────────────
print("\n[4] Creating Products...")

def make(name, type_slug, cat_slug, brand_slug, price, stock, desc, img, attrs=None, author=None):
    return {
        "name": name,
        "slug": slug(name) + "-" + str(int(time.time() * 1000) % 100000),
        "author": author,
        "product_type": type_ids.get(type_slug),
        "category": cat_ids.get(cat_slug),
        "brand": brand_ids.get(brand_slug),
        "price": price,
        "stock": stock,
        "description": desc,
        "cover_image_url": img,
        "attributes": attrs or {},
        "is_active": True,
    }

PRODUCTS = []

# 📚 SÁCH — 8 cuốn
PRODUCTS += [
    make("The Great Gatsby", "book", "fiction", "apple", 129000, 50,
         "Câu chuyện về Jay Gatsby và tình yêu với Daisy Buchanan.",
         "https://images.unsplash.com/photo-1507842217343-583f20270319?w=600&q=80",
         {"format": "paperback", "pages": 180}, "F. Scott Fitzgerald"),
    make("1984", "book", "fiction", "apple", 119000, 80,
         "Tiểu thuyết dystopia về xã hội toàn trị dưới Big Brother.",
         "https://images.unsplash.com/photo-1524995997946-a1c2e315a42f?w=600&q=80",
         {"format": "paperback", "pages": 328}, "George Orwell"),
    make("To Kill a Mockingbird", "book", "fiction", "apple", 149000, 60,
         "Câu chuyện về bất công chủng tộc ở miền Nam nước Mỹ.",
         "https://images.unsplash.com/photo-1543002588-d83cedbc4d60?w=600&q=80",
         {"format": "paperback", "pages": 281}, "Harper Lee"),
    make("Clean Code", "book", "programming", "apple", 359000, 70,
         "Sổ tay về nghề thủ công phần mềm agile.",
         "https://images.unsplash.com/photo-1516979187457-635ffe35ff15?w=600&q=80",
         {"format": "paperback", "pages": 431}, "Robert C. Martin"),
    make("Python Crash Course", "book", "programming", "apple", 299000, 85,
         "Giới thiệu thực hành lập trình Python qua các dự án.",
         "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=600&q=80",
         {"format": "paperback", "pages": 544}, "Eric Matthes"),
    make("Sapiens", "book", "history", "apple", 189000, 100,
         "Lịch sử ngắn gọn của loài người từ thời đồ đá.",
         "https://images.unsplash.com/photo-1507842217343-583f20270319?w=600&q=80",
         {"format": "hardcover", "pages": 443}, "Yuval Noah Harari"),
    make("A Brief History of Time", "book", "science", "apple", 169000, 50,
         "Khám phá vũ trụ, lỗ đen và bản chất của thời gian.",
         "https://images.unsplash.com/photo-1524995997946-a1c2e315a42f?w=600&q=80",
         {"format": "paperback", "pages": 212}, "Stephen Hawking"),
    make("Cosmos", "book", "science", "apple", 179000, 45,
         "Hành trình cá nhân qua vũ trụ của Carl Sagan.",
         "https://images.unsplash.com/photo-1543002588-d83cedbc4d60?w=600&q=80",
         {"format": "hardcover", "pages": 365}, "Carl Sagan"),
]

# 💻 LAPTOP — 9 chiếc
PRODUCTS += [
    make("MacBook Pro 16 M3", "laptop", "gaming-laptop", "apple", 45000000, 15,
         "Laptop cao cấp với chip M3 Pro, màn hình Retina 16 inch.",
         "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=600&q=80",
         {"cpu": "M3 Pro", "ram": "18GB", "storage": "512GB SSD"}),
    make("Dell XPS 15", "laptop", "gaming-laptop", "dell", 35000000, 20,
         "Laptop gaming mạnh mẽ với RTX 4070, màn hình 4K.",
         "https://images.unsplash.com/photo-1588872657840-790ff3bde08c?w=600&q=80",
         {"cpu": "Intel i9", "ram": "32GB", "storage": "1TB SSD"}),
    make("ASUS ROG Zephyrus G14", "laptop", "gaming-laptop", "asus-rog", 32000000, 18,
         "Laptop gaming siêu nhẹ với RTX 4060, hiệu năng cao.",
         "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=600&q=80",
         {"cpu": "Ryzen 9", "ram": "16GB", "storage": "512GB SSD"}),
    make("Lenovo ThinkPad X1 Carbon", "laptop", "ultrabook", "lenovo", 28000000, 25,
         "Ultrabook siêu mỏng, pin 15 giờ, bàn phím tuyệt vời.",
         "https://images.unsplash.com/photo-1588872657840-790ff3bde08c?w=600&q=80",
         {"cpu": "Intel i7", "ram": "16GB", "storage": "512GB SSD"}),
    make("HP Pavilion 15", "laptop", "budget", "hp", 12000000, 40,
         "Laptop phổ thông giá rẻ, phù hợp học tập và công việc.",
         "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=600&q=80",
         {"cpu": "Intel i5", "ram": "8GB", "storage": "256GB SSD"}),
    make("Samsung Galaxy Book3 Pro", "laptop", "ultrabook", "samsung", 30000000, 16,
         "Ultrabook cao cấp với màn hình AMOLED, thiết kế sang trọng.",
         "https://images.unsplash.com/photo-1588872657840-790ff3bde08c?w=600&q=80",
         {"cpu": "Intel i7", "ram": "16GB", "storage": "512GB SSD"}),
    make("MSI GE76 Raider", "laptop", "gaming-laptop", "msi", 38000000, 12,
         "Laptop gaming với RTX 4080, tản nhiệt tuyệt vời.",
         "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=600&q=80",
         {"cpu": "Intel i9", "ram": "32GB", "storage": "1TB SSD"}),
    make("Acer Swift 3", "laptop", "ultrabook", "asus", 18000000, 30,
         "Ultrabook nhẹ, pin lâu, giá tốt cho sinh viên.",
         "https://images.unsplash.com/photo-1588872657840-790ff3bde08c?w=600&q=80",
         {"cpu": "AMD Ryzen 5", "ram": "8GB", "storage": "512GB SSD"}),
    make("Razer Blade 15", "laptop", "gaming-laptop", "asus", 42000000, 10,
         "Laptop gaming cao cấp, thiết kế đen bóng sang trọng.",
         "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=600&q=80",
         {"cpu": "Intel i9", "ram": "32GB", "storage": "1TB SSD"}),
]

# 📱 ĐIỆN THOẠI — 9 chiếc
PRODUCTS += [
    make("iPhone 15 Pro Max", "mobile", "flagship", "apple", 28000000, 30,
         "Điện thoại flagship Apple với chip A17 Pro, camera 48MP.",
         "https://images.unsplash.com/photo-1511707267537-b85faf00021e?w=600&q=80",
         {"storage": "256GB", "color": "Titanium Black"}),
    make("Samsung Galaxy S24 Ultra", "mobile", "flagship", "samsung", 26000000, 35,
         "Flagship Samsung với S Pen, màn hình 6.8 inch Dynamic AMOLED.",
         "https://images.unsplash.com/photo-1511707267537-b85faf00021e?w=600&q=80",
         {"storage": "256GB", "color": "Phantom Black"}),
    make("Xiaomi 14 Ultra", "mobile", "flagship", "xiaomi", 18000000, 40,
         "Flagship Xiaomi với camera Leica, chip Snapdragon 8 Gen 3.",
         "https://images.unsplash.com/photo-1511707267537-b85faf00021e?w=600&q=80",
         {"storage": "512GB", "color": "Black"}),
    make("Google Pixel 8 Pro", "mobile", "flagship", "google", 22000000, 25,
         "Điện thoại Google với AI xử lý ảnh tuyệt vời.",
         "https://images.unsplash.com/photo-1511707267537-b85faf00021e?w=600&q=80",
         {"storage": "256GB", "color": "Obsidian"}),
    make("OnePlus 12", "mobile", "mid-range", "oppo", 14000000, 50,
         "Điện thoại tầm trung với chip Snapdragon 8 Gen 3, sạc nhanh.",
         "https://images.unsplash.com/photo-1511707267537-b85faf00021e?w=600&q=80",
         {"storage": "256GB", "color": "Silky Black"}),
    make("Samsung Galaxy A54", "mobile", "mid-range", "samsung", 10000000, 60,
         "Điện thoại tầm trung Samsung, pin 5000mAh, camera 50MP.",
         "https://images.unsplash.com/photo-1511707267537-b85faf00021e?w=600&q=80",
         {"storage": "128GB", "color": "Awesome Black"}),
    make("Xiaomi Redmi Note 13", "mobile", "budget", "xiaomi", 6000000, 80,
         "Điện thoại phổ thông Xiaomi, pin lâu, giá rẻ.",
         "https://images.unsplash.com/photo-1511707267537-b85faf00021e?w=600&q=80",
         {"storage": "128GB", "color": "Midnight Black"}),
    make("OPPO A78", "mobile", "budget", "oppo", 7000000, 70,
         "Điện thoại phổ thông OPPO, sạc nhanh 67W.",
         "https://images.unsplash.com/photo-1511707267537-b85faf00021e?w=600&q=80",
         {"storage": "128GB", "color": "Glowing Black"}),
    make("Samsung Galaxy Z Fold5", "mobile", "flagship", "samsung", 40000000, 12,
         "Điện thoại gập Samsung, màn hình 7.6 inch khi mở.",
         "https://images.unsplash.com/photo-1511707267537-b85faf00021e?w=600&q=80",
         {"storage": "256GB", "color": "Phantom Black"}),
]

# 📟 MÁY TÍNH BẢNG — 8 chiếc
PRODUCTS += [
    make("iPad Pro 12.9 M2", "tablet", "flagship", "apple", 22000000, 20,
         "Máy tính bảng cao cấp Apple với chip M2, màn hình Liquid Retina.",
         "https://images.unsplash.com/photo-1561070791-2526d30994b5?w=600&q=80",
         {"storage": "256GB", "screen": "12.9 inch"}),
    make("Samsung Galaxy Tab S9 Ultra", "tablet", "flagship", "samsung", 20000000, 25,
         "Máy tính bảng Samsung với màn hình 14.6 inch Dynamic AMOLED.",
         "https://images.unsplash.com/photo-1561070791-2526d30994b5?w=600&q=80",
         {"storage": "256GB", "screen": "14.6 inch"}),
    make("iPad Air 11", "tablet", "mid-range", "apple", 16000000, 30,
         "Máy tính bảng Apple tầm trung, chip M1, màn hình 11 inch.",
         "https://images.unsplash.com/photo-1561070791-2526d30994b5?w=600&q=80",
         {"storage": "128GB", "screen": "11 inch"}),
    make("Xiaomi Pad 6S Pro", "tablet", "mid-range", "xiaomi", 12000000, 35,
         "Máy tính bảng Xiaomi tầm trung, chip Snapdragon 8+ Gen 1.",
         "https://images.unsplash.com/photo-1561070791-2526d30994b5?w=600&q=80",
         {"storage": "256GB", "screen": "12.4 inch"}),
    make("Samsung Galaxy Tab A8", "tablet", "budget", "samsung", 6000000, 50,
         "Máy tính bảng phổ thông Samsung, pin 7000mAh.",
         "https://images.unsplash.com/photo-1561070791-2526d30994b5?w=600&q=80",
         {"storage": "64GB", "screen": "10.5 inch"}),
    make("Lenovo Tab P11 Pro", "tablet", "mid-range", "lenovo", 10000000, 40,
         "Máy tính bảng Lenovo với màn hình OLED 11.5 inch.",
         "https://images.unsplash.com/photo-1561070791-2526d30994b5?w=600&q=80",
         {"storage": "128GB", "screen": "11.5 inch"}),
    make("iPad 10", "tablet", "budget", "apple", 9000000, 45,
         "Máy tính bảng Apple phổ thông, chip A14 Bionic.",
         "https://images.unsplash.com/photo-1561070791-2526d30994b5?w=600&q=80",
         {"storage": "64GB", "screen": "10.9 inch"}),
    make("OnePlus Pad", "tablet", "mid-range", "oppo", 11000000, 38,
         "Máy tính bảng OnePlus với chip Snapdragon 8 Gen 1.",
         "https://images.unsplash.com/photo-1561070791-2526d30994b5?w=600&q=80",
         {"storage": "128GB", "screen": "11.6 inch"}),
]

# 🎧 TAI NGHE — 9 chiếc
PRODUCTS += [
    make("Sony WH-1000XM5", "headphone", "over-ear", "sony", 8000000, 25,
         "Tai nghe over-ear cao cấp, chống ồn tuyệt vời.",
         "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&q=80",
         {"type": "Over-ear", "battery": "30h"}),
    make("Apple AirPods Pro 2", "headphone", "tws", "apple", 6500000, 40,
         "Tai nghe True Wireless Apple, chống ồn chủ động.",
         "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&q=80",
         {"type": "TWS", "battery": "6h"}),
    make("Bose QuietComfort 45", "headphone", "over-ear", "bose", 7500000, 20,
         "Tai nghe Bose chống ồn, âm thanh cân bằng.",
         "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&q=80",
         {"type": "Over-ear", "battery": "24h"}),
    make("Samsung Galaxy Buds2 Pro", "headphone", "tws", "samsung", 4500000, 50,
         "Tai nghe TWS Samsung, chống ồn, âm thanh 360.",
         "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&q=80",
         {"type": "TWS", "battery": "5h"}),
    make("JBL Tune 750", "headphone", "over-ear", "jbl", 3500000, 60,
         "Tai nghe over-ear JBL giá rẻ, âm bass mạnh.",
         "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&q=80",
         {"type": "Over-ear", "battery": "15h"}),
    make("Xiaomi Buds 4 Pro", "headphone", "tws", "xiaomi", 2500000, 70,
         "Tai nghe TWS Xiaomi, chống ồn, giá tốt.",
         "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&q=80",
         {"type": "TWS", "battery": "6h"}),
    make("Sennheiser Momentum 4", "headphone", "over-ear", "sony", 6000000, 22,
         "Tai nghe Sennheiser, pin 60 giờ, âm thanh studio.",
         "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&q=80",
         {"type": "Over-ear", "battery": "60h"}),
    make("Google Pixel Buds Pro", "headphone", "tws", "google", 4000000, 45,
         "Tai nghe TWS Google, chống ồn, tích hợp AI.",
         "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&q=80",
         {"type": "TWS", "battery": "7h"}),
    make("Beats Studio Pro", "headphone", "over-ear", "apple", 9000000, 18,
         "Tai nghe Beats cao cấp, âm thanh mạnh mẽ.",
         "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&q=80",
         {"type": "Over-ear", "battery": "40h"}),
]

# ⌚ ĐỒNG HỒ THÔNG MINH — 8 chiếc
PRODUCTS += [
    make("Apple Watch Series 9", "smartwatch", "smartwatch-sport", "apple", 10000000, 30,
         "Đồng hồ Apple cao cấp, màn hình Always-On, ECG.",
         "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&q=80",
         {"size": "45mm", "color": "Midnight"}),
    make("Samsung Galaxy Watch6 Classic", "smartwatch", "smartwatch-sport", "samsung", 8000000, 35,
         "Đồng hồ Samsung với vòng xoay, màn hình AMOLED.",
         "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&q=80",
         {"size": "47mm", "color": "Black"}),
    make("Garmin Epix Gen 2", "smartwatch", "smartwatch-sport", "sony", 12000000, 20,
         "Đồng hồ thể thao Garmin, GPS, pin 11 ngày.",
         "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&q=80",
         {"size": "47mm", "color": "Titanium"}),
    make("Xiaomi Watch S1 Pro", "smartwatch", "smartwatch-sport", "xiaomi", 4500000, 50,
         "Đồng hồ Xiaomi tầm trung, màn hình AMOLED.",
         "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&q=80",
         {"size": "47mm", "color": "Black"}),
    make("Fitbit Sense 2", "smartwatch", "smartwatch-sport", "google", 5500000, 40,
         "Đồng hồ Fitbit, theo dõi sức khỏe, EDA.",
         "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&q=80",
         {"size": "40mm", "color": "Graphite"}),
    make("Huawei Watch GT 4", "smartwatch", "smartwatch-sport", "xiaomi", 6000000, 38,
         "Đồng hồ Huawei, pin 14 ngày, GPS.",
         "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&q=80",
         {"size": "46mm", "color": "Black"}),
    make("OnePlus Watch 2", "smartwatch", "smartwatch-sport", "oppo", 7000000, 32,
         "Đồng hồ OnePlus, chip Snapdragon, pin 100 giờ.",
         "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&q=80",
         {"size": "46mm", "color": "Radiant Steel"}),
    make("Amazfit GTR 4", "smartwatch", "smartwatch-sport", "xiaomi", 3500000, 60,
         "Đồng hồ Amazfit giá rẻ, pin 24 ngày.",
         "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&q=80",
         {"size": "47mm", "color": "Black"}),
]

# 📷 MÁY ẢNH — 8 chiếc
PRODUCTS += [
    make("Canon EOS R5", "camera", "mirrorless", "canon", 65000000, 12,
         "Máy ảnh mirrorless cao cấp, 45MP, quay 8K.",
         "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=600&q=80",
         {"sensor": "Full Frame", "megapixel": "45MP"}),
    make("Nikon Z9", "camera", "mirrorless", "nikon", 70000000, 10,
         "Máy ảnh Nikon cao cấp, 45.7MP, AF tuyệt vời.",
         "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=600&q=80",
         {"sensor": "Full Frame", "megapixel": "45.7MP"}),
    make("Sony A7R V", "camera", "mirrorless", "sony", 62000000, 15,
         "Máy ảnh Sony cao cấp, 61MP, AF nhanh.",
         "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=600&q=80",
         {"sensor": "Full Frame", "megapixel": "61MP"}),
    make("Canon EOS R6", "camera", "mirrorless", "canon", 45000000, 18,
         "Máy ảnh mirrorless Canon tầm trung, 20MP, quay 4K.",
         "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=600&q=80",
         {"sensor": "Full Frame", "megapixel": "20MP"}),
    make("Nikon Z6 III", "camera", "mirrorless", "nikon", 48000000, 16,
         "Máy ảnh Nikon tầm trung, 24.2MP, quay 8K.",
         "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=600&q=80",
         {"sensor": "Full Frame", "megapixel": "24.2MP"}),
    make("Sony A6700", "camera", "mirrorless", "sony", 35000000, 20,
         "Máy ảnh Sony APS-C, 26MP, AF nhanh.",
         "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=600&q=80",
         {"sensor": "APS-C", "megapixel": "26MP"}),
    make("Canon EOS M50 Mark II", "camera", "mirrorless", "canon", 18000000, 30,
         "Máy ảnh Canon APS-C giá rẻ, 24MP, quay 4K.",
         "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=600&q=80",
         {"sensor": "APS-C", "megapixel": "24MP"}),
    make("Fujifilm X-T5", "camera", "mirrorless", "sony", 32000000, 22,
         "Máy ảnh Fujifilm APS-C, 40MP, thiết kế retro.",
         "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=600&q=80",
         {"sensor": "APS-C", "megapixel": "40MP"}),
]

# 🖥️ MÀN HÌNH — 9 chiếc
PRODUCTS += [
    make("LG UltraWide 38GN950", "monitor", "gaming-monitor", "lg", 18000000, 15,
         "Màn hình gaming ultrawide 38 inch, 144Hz, 1ms.",
         "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=600&q=80",
         {"size": "38 inch", "refresh": "144Hz"}),
    make("ASUS ProArt PA348QV", "monitor", "4k-monitor", "asus", 15000000, 18,
         "Màn hình chuyên nghiệp 34 inch, 100% Adobe RGB.",
         "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=600&q=80",
         {"size": "34 inch", "resolution": "3440x1440"}),
    make("Dell S3721DGF", "monitor", "gaming-monitor", "dell", 12000000, 20,
         "Màn hình gaming 37 inch, 144Hz, VA panel.",
         "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=600&q=80",
         {"size": "37 inch", "refresh": "144Hz"}),
    make("LG 27UP550", "monitor", "4k-monitor", "lg", 10000000, 25,
         "Màn hình 4K 27 inch, 60Hz, IPS panel.",
         "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=600&q=80",
         {"size": "27 inch", "resolution": "4K"}),
    make("ASUS ROG Swift PG279QM", "monitor", "gaming-monitor", "asus", 14000000, 16,
         "Màn hình gaming 27 inch, 240Hz, IPS.",
         "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=600&q=80",
         {"size": "27 inch", "refresh": "240Hz"}),
    make("BenQ EW2780U", "monitor", "4k-monitor", "sony", 11000000, 22,
         "Màn hình 4K 27 inch, USB-C, thiết kế sang trọng.",
         "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=600&q=80",
         {"size": "27 inch", "resolution": "4K"}),
    make("MSI MAG 321URF", "monitor", "gaming-monitor", "msi", 16000000, 14,
         "Màn hình gaming 32 inch, 240Hz, mini-LED.",
         "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=600&q=80",
         {"size": "32 inch", "refresh": "240Hz"}),
    make("Dell P2423DE", "monitor", "gaming-monitor", "dell", 8000000, 35,
         "Màn hình văn phòng 24 inch, 60Hz, USB-C.",
         "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=600&q=80",
         {"size": "24 inch", "refresh": "60Hz"}),
    make("LG 32UP550", "monitor", "4k-monitor", "lg", 13000000, 19,
         "Màn hình 4K 32 inch, 60Hz, Thunderbolt 3.",
         "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=600&q=80",
         {"size": "32 inch", "resolution": "4K"}),
]

# ⌨️ BÀN PHÍM — 8 chiếc
PRODUCTS += [
    make("Corsair K95 Platinum XT", "keyboard", "mechanical-keyboard", "logitech", 5500000, 20,
         "Bàn phím cơ cao cấp, Cherry MX, RGB.",
         "https://images.unsplash.com/photo-1587829191301-4b34e1dc89f7?w=600&q=80",
         {"switch": "Cherry MX", "layout": "Full Size"}),
    make("Logitech G Pro X 60", "keyboard", "mechanical-keyboard", "logitech", 4500000, 25,
         "Bàn phím cơ gaming 60%, GX Brown.",
         "https://images.unsplash.com/photo-1587829191301-4b34e1dc89f7?w=600&q=80",
         {"switch": "GX Brown", "layout": "60%"}),
    make("Keychron K8 Pro", "keyboard", "mechanical-keyboard", "logitech", 3500000, 35,
         "Bàn phím cơ không dây, Keychron Brown.",
         "https://images.unsplash.com/photo-1587829191301-4b34e1dc89f7?w=600&q=80",
         {"switch": "Keychron Brown", "layout": "TKL"}),
    make("ASUS ROG Strix Scope II", "keyboard", "mechanical-keyboard", "asus", 4000000, 28,
         "Bàn phím cơ gaming, ROG Red Switch.",
         "https://images.unsplash.com/photo-1587829191301-4b34e1dc89f7?w=600&q=80",
         {"switch": "ROG Red", "layout": "Full Size"}),
    make("Ducky One 3", "keyboard", "mechanical-keyboard", "sony", 3800000, 30,
         "Bàn phím cơ Ducky, Cherry MX, PBT keycap.",
         "https://images.unsplash.com/photo-1587829191301-4b34e1dc89f7?w=600&q=80",
         {"switch": "Cherry MX", "layout": "Full Size"}),
    make("SteelSeries Apex Pro", "keyboard", "mechanical-keyboard", "logitech", 5000000, 22,
         "Bàn phím cơ gaming, OmniPoint switch.",
         "https://images.unsplash.com/photo-1587829191301-4b34e1dc89f7?w=600&q=80",
         {"switch": "OmniPoint", "layout": "Full Size"}),
    make("Razer DeathStalker V2", "keyboard", "mechanical-keyboard", "asus", 3200000, 40,
         "Bàn phím cơ gaming Razer, Razer Linear.",
         "https://images.unsplash.com/photo-1587829191301-4b34e1dc89f7?w=600&q=80",
         {"switch": "Razer Linear", "layout": "Full Size"}),
    make("Leopold FC900R", "keyboard", "mechanical-keyboard", "sony", 2800000, 45,
         "Bàn phím cơ Leopold, Cherry MX, PBT.",
         "https://images.unsplash.com/photo-1587829191301-4b34e1dc89f7?w=600&q=80",
         {"switch": "Cherry MX", "layout": "Full Size"}),
]

# 🖱️ CHUỘT — 9 chiếc
PRODUCTS += [
    make("Logitech MX Master 3S", "mouse", "wireless-mouse", "logitech", 3500000, 30,
         "Chuột không dây cao cấp, 8K DPI, sạc nhanh.",
         "https://images.unsplash.com/photo-1527814050087-3793815479db?w=600&q=80",
         {"type": "Wireless", "dpi": "8000"}),
    make("Razer DeathAdder V3", "mouse", "wireless-mouse", "asus", 2500000, 40,
         "Chuột gaming không dây, 30000 DPI, 70g.",
         "https://images.unsplash.com/photo-1527814050087-3793815479db?w=600&q=80",
         {"type": "Wireless", "dpi": "30000"}),
    make("SteelSeries Rival 3", "mouse", "wireless-mouse", "logitech", 1500000, 60,
         "Chuột gaming giá rẻ, 18000 DPI.",
         "https://images.unsplash.com/photo-1527814050087-3793815479db?w=600&q=80",
         {"type": "Wireless", "dpi": "18000"}),
    make("Corsair M65 RGB Ultra", "mouse", "wireless-mouse", "logitech", 2800000, 35,
         "Chuột gaming, 26000 DPI, nút bên.",
         "https://images.unsplash.com/photo-1527814050087-3793815479db?w=600&q=80",
         {"type": "Wireless", "dpi": "26000"}),
    make("ASUS ROG Chakram", "mouse", "wireless-mouse", "asus", 2200000, 45,
         "Chuột gaming ASUS, 16000 DPI, joystick.",
         "https://images.unsplash.com/photo-1527814050087-3793815479db?w=600&q=80",
         {"type": "Wireless", "dpi": "16000"}),
    make("Finalmouse UltralightX", "mouse", "wireless-mouse", "sony", 2000000, 50,
         "Chuột gaming siêu nhẹ, 8000 DPI.",
         "https://images.unsplash.com/photo-1527814050087-3793815479db?w=600&q=80",
         {"type": "Wireless", "dpi": "8000"}),
    make("Glorious Model O", "mouse", "wireless-mouse", "logitech", 1800000, 55,
         "Chuột gaming lỗ, 12000 DPI, nhẹ.",
         "https://images.unsplash.com/photo-1527814050087-3793815479db?w=600&q=80",
         {"type": "Wireless", "dpi": "12000"}),
    make("Logitech G502 HERO", "mouse", "wireless-mouse", "logitech", 1200000, 70,
         "Chuột gaming phổ thông, 25600 DPI.",
         "https://images.unsplash.com/photo-1527814050087-3793815479db?w=600&q=80",
         {"type": "Wireless", "dpi": "25600"}),
    make("BenQ EC2", "mouse", "wireless-mouse", "sony", 1600000, 65,
         "Chuột gaming esports, 3200 DPI.",
         "https://images.unsplash.com/photo-1527814050087-3793815479db?w=600&q=80",
         {"type": "Wireless", "dpi": "3200"}),
]

# 🔊 LOA — 8 chiếc
PRODUCTS += [
    make("Bose SoundLink Max", "speaker", "bluetooth-speaker", "bose", 8000000, 20,
         "Loa Bluetooth cao cấp, âm thanh 360, pin 20h.",
         "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=600&q=80",
         {"type": "Bluetooth", "power": "100W"}),
    make("JBL Charge 5", "speaker", "bluetooth-speaker", "jbl", 4500000, 35,
         "Loa Bluetooth JBL, chống nước, pin 20h.",
         "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=600&q=80",
         {"type": "Bluetooth", "power": "30W"}),
    make("Sony SRS-XB43", "speaker", "bluetooth-speaker", "sony", 5500000, 28,
         "Loa Bluetooth Sony, bass mạnh, chống nước.",
         "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=600&q=80",
         {"type": "Bluetooth", "power": "65W"}),
    make("Ultimate Ears Boom 3", "speaker", "bluetooth-speaker", "jbl", 3500000, 45,
         "Loa Bluetooth UE, âm thanh 360, chống nước.",
         "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=600&q=80",
         {"type": "Bluetooth", "power": "20W"}),
    make("Xiaomi Mi Portable", "speaker", "bluetooth-speaker", "xiaomi", 1500000, 70,
         "Loa Bluetooth Xiaomi giá rẻ, pin 13h.",
         "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=600&q=80",
         {"type": "Bluetooth", "power": "16W"}),
    make("Marshall Emberton II", "speaker", "bluetooth-speaker", "sony", 4000000, 32,
         "Loa Bluetooth Marshall, thiết kế retro.",
         "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=600&q=80",
         {"type": "Bluetooth", "power": "20W"}),
    make("Anker Soundcore Motion Boom", "speaker", "bluetooth-speaker", "sony", 2500000, 55,
         "Loa Bluetooth Anker, bass mạnh, giá tốt.",
         "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=600&q=80",
         {"type": "Bluetooth", "power": "30W"}),
    make("Bang & Olufsen Beosound A1", "speaker", "bluetooth-speaker", "sony", 6500000, 18,
         "Loa Bluetooth B&O cao cấp, thiết kế sang trọng.",
         "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=600&q=80",
         {"type": "Bluetooth", "power": "60W"}),
]

# 📡 ROUTER / MẠNG — 8 chiếc
PRODUCTS += [
    make("ASUS ROG Rapture GT-AXE16000", "router", "wifi-router", "asus", 12000000, 15,
         "Router gaming WiFi 6E, 16 Gbps, RGB.",
         "https://images.unsplash.com/photo-1621905251918-48416bd8575a?w=600&q=80",
         {"standard": "WiFi 6E", "speed": "16 Gbps"}),
    make("TP-Link Archer AXE300", "router", "wifi-router", "tp-link", 8000000, 25,
         "Router WiFi 6E TP-Link, 3 Gbps, giá tốt.",
         "https://images.unsplash.com/photo-1621905251918-48416bd8575a?w=600&q=80",
         {"standard": "WiFi 6E", "speed": "3 Gbps"}),
    make("Netgear Nighthawk RAXE500", "router", "wifi-router", "sony", 10000000, 18,
         "Router WiFi 6E Netgear, 12 Gbps.",
         "https://images.unsplash.com/photo-1621905251918-48416bd8575a?w=600&q=80",
         {"standard": "WiFi 6E", "speed": "12 Gbps"}),
    make("Linksys MR9600", "router", "wifi-router", "sony", 7000000, 30,
         "Router WiFi 6 Linksys, 6 Gbps.",
         "https://images.unsplash.com/photo-1621905251918-48416bd8575a?w=600&q=80",
         {"standard": "WiFi 6", "speed": "6 Gbps"}),
    make("ASUS ZenWiFi AXE7350", "router", "wifi-router", "asus", 9000000, 20,
         "Router WiFi 6E ASUS mesh, 7.3 Gbps.",
         "https://images.unsplash.com/photo-1621905251918-48416bd8575a?w=600&q=80",
         {"standard": "WiFi 6E", "speed": "7.3 Gbps"}),
    make("TP-Link Archer AX12", "router", "wifi-router", "tp-link", 4500000, 50,
         "Router WiFi 6 TP-Link phổ thông, 4.8 Gbps.",
         "https://images.unsplash.com/photo-1621905251918-48416bd8575a?w=600&q=80",
         {"standard": "WiFi 6", "speed": "4.8 Gbps"}),
    make("Eero Pro 6E", "router", "wifi-router", "amazon", 11000000, 16,
         "Router WiFi 6E Amazon Eero, mesh system.",
         "https://images.unsplash.com/photo-1621905251918-48416bd8575a?w=600&q=80",
         {"standard": "WiFi 6E", "speed": "10.8 Gbps"}),
    make("Synology MR2200ac", "router", "wifi-router", "sony", 3500000, 60,
         "Router WiFi 5 Synology giá rẻ, 2.2 Gbps.",
         "https://images.unsplash.com/photo-1621905251918-48416bd8575a?w=600&q=80",
         {"standard": "WiFi 5", "speed": "2.2 Gbps"}),
]

print(f"  ✓ {len(PRODUCTS)} products prepared")

# ─── STEP 5: Upload Products ──────────────────────────────────────────────────
print("\n[5] Uploading Products...")
success = 0
for i, prod in enumerate(PRODUCTS, 1):
    r = p(f"{PROD_SVC}/products/", prod)
    if r.status_code in (200, 201):
        success += 1
    if i % 20 == 0:
        print(f"  ✓ {i}/{len(PRODUCTS)} products")
    time.sleep(0.05)

print(f"  ✓ {success}/{len(PRODUCTS)} products created")

# ─── STEP 6: Customers ────────────────────────────────────────────────────────
print("\n[6] Creating Customers...")
CUSTOMERS = [
    {"username":"alice_nguyen","email":"alice@example.com","password":"Pass@1234","first_name":"Alice","last_name":"Nguyen","city":"Ho Chi Minh City","street":"123 Nguyen Hue"},
    {"username":"bob_tran","email":"bob@example.com","password":"Pass@1234","first_name":"Bob","last_name":"Tran","city":"Hanoi","street":"45 Hoan Kiem"},
    {"username":"carol_le","email":"carol@example.com","password":"Pass@1234","first_name":"Carol","last_name":"Le","city":"Da Nang","street":"78 Bach Dang"},
    {"username":"david_pham","email":"david@example.com","password":"Pass@1234","first_name":"David","last_name":"Pham","city":"Can Tho","street":"12 Ninh Kieu"},
    {"username":"emma_hoang","email":"emma@example.com","password":"Pass@1234","first_name":"Emma","last_name":"Hoang","city":"Hue","street":"56 Le Loi"},
    {"username":"frank_vo","email":"frank@example.com","password":"Pass@1234","first_name":"Frank","last_name":"Vo","city":"Bien Hoa","street":"90 Dong Khoi"},
    {"username":"grace_do","email":"grace@example.com","password":"Pass@1234","first_name":"Grace","last_name":"Do","city":"Vung Tau","street":"34 Tran Phu"},
    {"username":"henry_bui","email":"henry@example.com","password":"Pass@1234","first_name":"Henry","last_name":"Bui","city":"Nha Trang","street":"67 Nguyen Thi Minh Khai"},
]

cust_ids = {}
for c in CUSTOMERS:
    p(f"{AUTH_SVC}/auth/register/", {"username": c["username"], "email": c["email"], "password": c["password"], "role": "customer"})
    r = p(f"{CUST_SVC}/customers/", c)
    if r.status_code in (200, 201):
        cid = r.json().get("data", r.json()).get("id") or r.json().get("id")
        if cid:
            cust_ids[c["username"]] = cid
            print(f"  ✓ {c['first_name']} {c['last_name']}")

print(f"  ✓ {len(cust_ids)} customers created")

# ─── STEP 7: Addresses ────────────────────────────────────────────────────────
print("\n[7] Creating Addresses...")
addr_count = 0
for uname, cid in cust_ids.items():
    c = next(x for x in CUSTOMERS if x["username"] == uname)
    addr_data = {
        "customer": cid,
        "label": "Home",
        "recipient_name": f"{c['first_name']} {c['last_name']}",
        "phone_number": "0123456789",
        "street": c["street"],
        "ward": "Ward 1",
        "city": c["city"],
        "country": "Vietnam",
        "is_default": True
    }
    r = p(f"{CUST_SVC}/addresses/", addr_data)
    if r.status_code in (200, 201):
        addr_count += 1

print(f"  ✓ {addr_count} addresses created")

# ─── STEP 8: Staff ────────────────────────────────────────────────────────────
print("\n[8] Creating Staff...")
STAFF_LIST = [
    {"username":"staff_nam","email":"nam@ecommerce.com","password":"Staff@1234","first_name":"Nam","last_name":"Nguyen","role":"staff"},
    {"username":"staff_lan","email":"lan@ecommerce.com","password":"Staff@1234","first_name":"Lan","last_name":"Tran","role":"inventory"},
    {"username":"manager_hung","email":"hung@ecommerce.com","password":"Manager@1234","first_name":"Hung","last_name":"Pham","role":"manager"},
    {"username":"admin_root","email":"admin@ecommerce.com","password":"Admin@1234","first_name":"Admin","last_name":"Root","role":"admin"},
]

for s in STAFF_LIST:
    p(f"{AUTH_SVC}/auth/register/", {"username": s["username"], "email": s["email"], "password": s["password"], "role": s["role"]})
    p(f"{STAFF_SVC}/staff/", s)
    print(f"  ✓ {s['username']} ({s['role']})")

print(f"  ✓ {len(STAFF_LIST)} staff created")

# ─── STEP 9: Orders & Payments ────────────────────────────────────────────────
print("\n[9] Creating Orders & Payments...")
order_count = pay_count = 0
purchased_items = {}  # {(customer_id, product_id): order_id}

# Get all products
products_data = get(f"{PROD_SVC}/products/?page_size=100")
products = products_data if isinstance(products_data, list) else products_data.get("results", [])
product_ids = [p["id"] for p in products if "id" in p]

for uname, cid in list(cust_ids.items())[:6]:
    c = next(x for x in CUSTOMERS if x["username"] == uname)
    shipping_address = f"{c['street']}, Ward 1, {c['city']}, Vietnam"
    
    for _ in range(random.randint(2, 4)):
        picks = random.sample(product_ids, min(random.randint(1, 3), len(product_ids)))
        items = [{"product_id": pid, "quantity": random.randint(1, 2)} for pid in picks]
        total = round(random.uniform(500000, 5000000), 0)
        
        r = p(f"{ORDER_SVC}/orders/", {
            "customer_id": cid,
            "total_amount": total,
            "status": random.choice(["pending", "paid", "shipped"]),
            "shipping_address": shipping_address,
            "shipping_phone": "0123456789",
            "items": items
        })
        if r.status_code in (200, 201):
            oid = r.json().get("id")
            order_count += 1
            
            # Lưu purchased items
            for item in items:
                key = (cid, item["product_id"])
                purchased_items[key] = oid
            
            # Payment
            r2 = p(f"{PAY_SVC}/payments/", {
                "order_id": oid,
                "amount": total,
                "status": "success",
                "payment_method": random.choice(["credit_card", "paypal", "bank_transfer"]),
                "transaction_id": str(uuid.uuid4())
            })
            if r2.status_code in (200, 201):
                pay_count += 1

print(f"  ✓ {order_count} orders | {pay_count} payments created")

# ─── STEP 10: Shipments ───────────────────────────────────────────────────────
print("\n[10] Creating Shipments...")
ship_count = 0
ship_methods = ["standard", "express", "overnight"]

orders_data = get(f"{ORDER_SVC}/orders/?page_size=100")
orders = orders_data if isinstance(orders_data, list) else orders_data.get("results", [])

for order in orders[:15]:
    if order.get("status") in ("paid", "shipped"):
        sstat = "delivered" if order.get("status") == "shipped" else random.choice(["pending", "processing", "shipped"])
        est = (date.today() + timedelta(days=random.randint(2, 10))).isoformat()
        r = p(f"{SHIP_SVC}/shipments/", {
            "order_id": order.get("id"),
            "status": sstat,
            "shipping_address": order.get("shipping_address", "123 Main St, City, Country"),
            "tracking_number": f"TRK{uuid.uuid4().hex[:10].upper()}",
            "shipping_method": random.choice(ship_methods),
            "estimated_delivery": est
        })
        if r.status_code in (200, 201):
            ship_count += 1

print(f"  ✓ {ship_count} shipments created")

# ─── STEP 11: Managers ────────────────────────────────────────────────────────
print("\n[11] Creating Managers...")
MANAGERS = [
    {"name": "Hung Pham", "email": "manager1@ecommerce.com", "password": "Manager@1234", "department": "Operations"},
    {"name": "Linh Tran", "email": "manager2@ecommerce.com", "password": "Manager@1234", "department": "Sales"},
    {"name": "Duc Nguyen", "email": "manager3@ecommerce.com", "password": "Manager@1234", "department": "Inventory"},
]

mgr_count = 0
mgr_ids = {}
for m in MANAGERS:
    r = p(f"{MGR_SVC}/managers/", m)
    if r.status_code in (200, 201):
        mgr_count += 1
        mid = r.json().get("id")
        if mid:
            mgr_ids[m["email"]] = mid
        print(f"  ✓ {m['name']}")

print(f"  ✓ {mgr_count} managers created")

# ─── STEP 12: Comments & Ratings (LOGIC ĐÚNG) ─────────────────────────────────
print("\n[12] Creating Comments & Ratings...")
COMMENTS = [
    "Absolutely loved this product! A must-buy for everyone.",
    "Very good quality and well-made. Highly recommend.",
    "Changed my perspective on this category. Brilliant!",
    "A classic that never gets old. Perfect!",
    "Couldn't be happier with this purchase!",
    "Great product but a bit pricey.",
    "One of the best I've ever bought. 10/10.",
    "Fascinating features, explained beautifully.",
    "Good overall, some features could be better.",
    "Excellent quality. The brand really knows their stuff.",
    "Thought-provoking and deeply satisfying.",
    "Perfect for beginners and experts alike.",
    "The features are explained in a very accessible way.",
    "I learned so much from using this. Will buy again.",
    "Highly recommended for anyone interested in this.",
]

cmt_count = 0

# Chỉ tạo comments cho sản phẩm mà khách hàng đã mua
for (cid, pid), oid in purchased_items.items():
    # Mỗi (customer, product, order) pair chỉ có 1 comment
    comment_data = {
        "customer_id": cid,
        "book_id": pid,  # API sử dụng book_id
        "order_id": oid,
        "content": random.choice(COMMENTS),
        "rating": random.randint(3, 5),
        "helpful_count": random.randint(0, 50)
    }
    r = p(f"{CMT_SVC}/comments/", comment_data)
    if r.status_code in (200, 201):
        cmt_count += 1

print(f"  ✓ {cmt_count} comments created")

print("\n" + "=" * 70)
print("  SEED COMPLETE!")
print(f"  Products:  {success}")
print(f"  Customers: {len(cust_ids)}")
print(f"  Addresses: {addr_count}")
print(f"  Staff:     {len(STAFF_LIST)}")
print(f"  Managers:  {mgr_count}")
print(f"  Orders:    {order_count}")
print(f"  Payments:  {pay_count}")
print(f"  Shipments: {ship_count}")
print(f"  Comments:  {cmt_count}")
print("=" * 70)
print("\nLogin:")
print("  Customer: alice_nguyen / Pass@1234")
print("  Staff:    staff_nam / Staff@1234")
print("  Manager:  manager_hung / Manager@1234")
print("  Admin:    admin_root / Admin@1234")
