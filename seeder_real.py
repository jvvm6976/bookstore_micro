import urllib.request
import json
import random
import time

# Configurations
TARGET_GW = "http://localhost:8000/api"
TARGET_BOOK = "http://localhost:8002/api"
TARGET_CMT = "http://localhost:8008/api"
TARGET_STAFF = "http://localhost:8007/api"

def api_call(url, method='GET', data=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    bdata = json.dumps(data).encode('utf-8') if data else None
    request = urllib.request.Request(url, data=bdata, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:
            if response.status == 204:
                return {}
            content = response.read().decode('utf-8')
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        print(f"Skipped/Error on {method} {url}: {e.code}")
        return None
    except Exception as e:
        print(f"Failure {url}: {e}")
        return None

print("Fetching dynamic REAL data from OpenLibrary...")
subjects = ["programming", "science", "fiction", "history"]
books_data = []

# Fetch real data
for sub in subjects:
    print(f"Crawling {sub} books...")
    try:
        req = urllib.request.urlopen(f'https://openlibrary.org/subjects/{sub}.json?limit=15')
        data = json.loads(req.read().decode('utf-8'))
        for work in data.get('works', []):
            cover_i = work.get('cover_id')
            if cover_i and work.get('authors'):
                books_data.append({
                    "title": work['title'],
                    "author": work['authors'][0]['name'],
                    "category": sub,
                    "price": random.choice([89000, 120000, 150000, 195000, 240000, 310000]),
                    "stock": random.randint(10, 100),
                    "description": f"A wonderful {sub} book. Original title: {work['title']}. Highly rated.",
                    "cover_image_url": f"https://covers.openlibrary.org/b/id/{cover_i}-L.jpg"
                })
    except Exception as e:
        print("Scrape err:", e)

print(f"Found {len(books_data)} valid real books with covers!")

print("\n1. Setting up Publishers & Books")
pub = api_call(f"{TARGET_BOOK}/publishers/", 'POST', {"name": "O'Reilly Media", "address": "1005 Gravenstein Hwy"})
pub_id = pub.get('id', 1) if pub else 1

created_books = []
for idx, b in enumerate(books_data):
    b['publisher'] = pub_id
    res = api_call(f"{TARGET_BOOK}/books/", 'POST', b)
    if res and 'id' in res:
        created_books.append(res)
        if idx % 10 == 0:
            print(f"  Saved book {idx+1}/{len(books_data)}: {b['title']}")

print("\n2. Creating 25 Real Customers & Generating Transactions")
customers = []
for i in range(1, 26):
    uname = f"user_{i}"
    res = api_call(f"{TARGET_GW}/auth/register/", 'POST', {
        "username": uname, "email": f"{uname}@example.com", "password": "password123", "role": "customer"
    })
    if res and 'access_token' in res:
        customers.append(res)

for idx, c in enumerate(customers):
    token = c['access_token']
    cust = c['user']
    c_id = cust['service_user_id']
    cat_id = cust['cart_id']
    
    # 3. Add to Cart & Checkout & Review naturally
    items_to_buy = random.sample(created_books, min(3, len(created_books)))
    for b in items_to_buy:
        # Add to cart
        api_call(f"{TARGET_GW}/customers/{c_id}/updateCart/", 'POST', {"book_id": b['id'], "quantity": random.randint(1,2)}, token)
        # Random review
        if random.random() > 0.3:
            comments = ["Sách rất hay và bìa đẹp!", "Nội dung tuyệt vời, đúng cái mình cần tìm.", "Giao hàng hơi lâu nhưng sách y hình internet.", "Kiến thức bổ ích.", "Sách ổn, mua về trưng tủ cho đẹp :D"]
            api_call(f"{TARGET_CMT}/comments/", 'POST', {
                "customer_id": c_id, "book_id": b['id'], "content": random.choice(comments), "rating": random.randint(4, 5)
            })

    # Checkout
    if cat_id and items_to_buy:
        api_call(f"{TARGET_GW}/orders/checkout/", 'POST', {
            "customer_id": c_id, "cart_id": cat_id, 
            "shipping_address": f"Address {random.randint(100, 999)} Street, City", 
            "payment_method": "credit_card"
        }, token)
    
    if idx % 5 == 0:
        print(f"  Processed automated actions for customer {idx+1}/25")

print("\n4. Creating Staff and Managers")
api_call(f"{TARGET_GW}/auth/register/", 'POST', {"username": "admin_main", "email": "admin@book.com", "password": "admin", "role": "admin"})
api_call(f"{TARGET_GW}/auth/register/", 'POST', {"username": "manager1", "email": "m1@book.com", "password": "admin", "role": "manager"})

print("\nDONE! Huge database generated successfully across all microservices.")
