param(
    [string]$GW   = "http://localhost:8000/api",
    [string]$Book = "http://localhost:8002/api",
    [string]$Cart = "http://localhost:8003/api",
    [string]$Cmt  = "http://localhost:8008/api",
    [string]$Staff= "http://localhost:8007/api",
    [string]$Cust = "http://localhost:8001/api",
    [int]$WaitSeconds = 60
)
$ErrorActionPreference = "Stop"

function Invoke-Api {
    param([string]$Method="GET",[string]$Base,[string]$Path,[object]$Body,[string]$Token)
    $uri = "$Base/$Path"
    $headers = @{ "Content-Type"="application/json" }
    if ($Token) { $headers["Authorization"] = "Bearer $Token" }
    $params = @{ Method=$Method; Uri=$uri; Headers=$headers; TimeoutSec=30 }
    if ($Body) { $params["Body"] = ($Body | ConvertTo-Json -Depth 10) }
    return Invoke-RestMethod @params
}

Write-Host "Waiting for gateway..." -ForegroundColor Cyan
for ($i=0; $i -lt $WaitSeconds; $i+=3) {
    try { Invoke-Api -Base $GW -Path "books/" | Out-Null; Write-Host "Gateway ready!" -ForegroundColor Green; break } catch { Start-Sleep 3 }
}

# ── Publisher ──────────────────────────────────────────────
Write-Host "`n[1] Seeding publisher & books..." -ForegroundColor Cyan
$pub = $null
try {
    $pub = Invoke-Api -Method POST -Base $Book -Path "publishers/" -Body @{name="CloudBooks Press";address="123 Nguyễn Huệ, Q.1, TP.HCM"}
    Write-Host "  Publisher: id=$($pub.id)" -ForegroundColor Green
} catch {
    try {
        $pubs = Invoke-Api -Base $Book -Path "publishers/"
        $pubList = if ($pubs.results) { $pubs.results } else { $pubs }
        $pub = $pubList | Where-Object { $_.name -eq "CloudBooks Press" } | Select-Object -First 1
        if (-not $pub) { $pub = @{id=1} }
        Write-Host "  Publisher exists: id=$($pub.id)" -ForegroundColor Yellow
    } catch { $pub = @{id=1} }
}

# Sách với giá VNĐ thực tế và ảnh bìa thật từ Open Library / Google Books covers
$books = @(
  @{
    title="Clean Code"
    author="Robert C. Martin"
    category="programming"
    price="185000"
    stock=50
    description="Cuốn sách kinh điển về viết code sạch, dễ đọc và bảo trì. Bắt buộc phải đọc cho mọi lập trình viên."
    cover_image_url="https://m.media-amazon.com/images/I/41xShlnTZTL._SX376_BO1,204,203,200_.jpg"
  },
  @{
    title="The Pragmatic Programmer"
    author="Andrew Hunt & David Thomas"
    category="programming"
    price="210000"
    stock=40
    description="Hành trình từ lập trình viên mới đến bậc thầy. Những lời khuyên thực tiễn cho sự nghiệp phát triển phần mềm."
    cover_image_url="https://m.media-amazon.com/images/I/51W1sBPO7tL._SX380_BO1,204,203,200_.jpg"
  },
  @{
    title="Design Patterns"
    author="Gang of Four"
    category="programming"
    price="275000"
    stock=30
    description="23 mẫu thiết kế phần mềm hướng đối tượng kinh điển. Nền tảng không thể thiếu của kỹ sư phần mềm."
    cover_image_url="https://m.media-amazon.com/images/I/51szD9HC9pL._SX395_BO1,204,203,200_.jpg"
  },
  @{
    title="Sapiens: Lược Sử Loài Người"
    author="Yuval Noah Harari"
    category="history"
    price="165000"
    stock=25
    description="Hành trình 70.000 năm của loài người từ thời đồ đá đến thế kỷ 21. Bestseller toàn cầu."
    cover_image_url="https://m.media-amazon.com/images/I/713jIoMO3UL._AC_UF1000,1000_QL80_.jpg"
  },
  @{
    title="Lược Sử Thời Gian"
    author="Stephen Hawking"
    category="science"
    price="120000"
    stock=35
    description="Từ Vụ Nổ Lớn đến Lỗ Đen. Vật lý vũ trụ được giải thích cho mọi người đọc."
    cover_image_url="https://m.media-amazon.com/images/I/A1xkFZX5k-L._AC_UF1000,1000_QL80_.jpg"
  },
  @{
    title="Gatsby Vĩ Đại"
    author="F. Scott Fitzgerald"
    category="fiction"
    price="89000"
    stock=60
    description="Câu chuyện về giấc mơ Mỹ, tình yêu và sự thất vọng trong thập niên 1920. Kiệt tác văn học thế giới."
    cover_image_url="https://m.media-amazon.com/images/I/71FTb9X6wsL._AC_UF1000,1000_QL80_.jpg"
  },
  @{
    title="Introduction to Algorithms"
    author="Cormen, Leiserson, Rivest"
    category="programming"
    price="320000"
    stock=20
    description="Giáo trình thuật toán toàn diện nhất. Được sử dụng tại MIT và các trường đại học hàng đầu thế giới."
    cover_image_url="https://m.media-amazon.com/images/I/61Pgdn8Ys-L._AC_UF1000,1000_QL80_.jpg"
  },
  @{
    title="Cosmos"
    author="Carl Sagan"
    category="science"
    price="145000"
    stock=45
    description="Cuộc hành trình cá nhân xuyên vũ trụ. Khoa học, triết học và nhân văn hòa quyện tuyệt vời."
    cover_image_url="https://m.media-amazon.com/images/I/71KMnCNtFGL._AC_UF1000,1000_QL80_.jpg"
  },
  @{
    title="1984"
    author="George Orwell"
    category="fiction"
    price="95000"
    stock=55
    description="Tiểu thuyết dystopia kinh điển về xã hội toàn trị. Cảnh báo về quyền lực và tự do con người."
    cover_image_url="https://m.media-amazon.com/images/I/71kxa2Pu7tL._AC_UF1000,1000_QL80_.jpg"
  },
  @{
    title="Giải Tích (Calculus)"
    author="James Stewart"
    category="math"
    price="240000"
    stock=18
    description="Giáo trình giải tích toàn diện, phiên bản thứ 8. Được sử dụng rộng rãi tại các trường đại học Việt Nam."
    cover_image_url="https://m.media-amazon.com/images/I/71RnfLFMgFL._AC_UF1000,1000_QL80_.jpg"
  },
  @{
    title="Đắc Nhân Tâm"
    author="Dale Carnegie"
    category="history"
    price="79000"
    stock=80
    description="Cuốn sách self-help bán chạy nhất mọi thời đại. Nghệ thuật giao tiếp và tạo ảnh hưởng."
    cover_image_url="https://m.media-amazon.com/images/I/71XnFpBFMRL._AC_UF1000,1000_QL80_.jpg"
  },
  @{
    title="Nhà Giả Kim"
    author="Paulo Coelho"
    category="fiction"
    price="75000"
    stock=70
    description="Hành trình theo đuổi giấc mơ của chàng chăn cừu Santiago. Triết lý sống sâu sắc và cảm hứng."
    cover_image_url="https://m.media-amazon.com/images/I/51Z0nLAfLmL._SX330_BO1,204,203,200_.jpg"
  },
  @{
    title="Atomic Habits"
    author="James Clear"
    category="history"
    price="135000"
    stock=65
    description="Thay đổi nhỏ, kết quả phi thường. Phương pháp xây dựng thói quen tốt và loại bỏ thói quen xấu."
    cover_image_url="https://m.media-amazon.com/images/I/81wgcld4wxL._AC_UF1000,1000_QL80_.jpg"
  },
  @{
    title="Python Crash Course"
    author="Eric Matthes"
    category="programming"
    price="195000"
    stock=42
    description="Học Python nhanh chóng và thực tế. Từ cơ bản đến dự án thực tế trong thời gian ngắn nhất."
    cover_image_url="https://m.media-amazon.com/images/I/71sL5oNBBQL._AC_UF1000,1000_QL80_.jpg"
  },
  @{
    title="Thinking, Fast and Slow"
    author="Daniel Kahneman"
    category="science"
    price="155000"
    stock=38
    description="Khám phá hai hệ thống tư duy của con người. Tâm lý học hành vi và kinh tế học hành vi."
    cover_image_url="https://m.media-amazon.com/images/I/71wvKXBHRpL._AC_UF1000,1000_QL80_.jpg"
  },
  @{
    title="Dune"
    author="Frank Herbert"
    category="fiction"
    price="175000"
    stock=33
    description="Sử thi khoa học viễn tưởng vĩ đại nhất mọi thời đại. Hành tinh sa mạc Arrakis và cuộc chiến vì gia vị."
    cover_image_url="https://m.media-amazon.com/images/I/81ym3QUd3KL._AC_UF1000,1000_QL80_.jpg"
  }
)

$createdBooks = @()
foreach ($b in $books) {
    $b["publisher"] = $pub.id
    try {
        $nb = Invoke-Api -Method POST -Base $Book -Path "books/" -Body $b
        Write-Host "  Book: id=$($nb.id) '$($nb.title)' - $($nb.price)đ" -ForegroundColor Green
        $createdBooks += $nb
    } catch {
        Write-Host "  Skip (exists?): $($b.title)" -ForegroundColor Yellow
    }
}

if ($createdBooks.Count -eq 0) {
    try {
        $existing = Invoke-Api -Base $Book -Path "books/?page_size=50"
        $createdBooks = if ($existing.results) { $existing.results } else { $existing }
        Write-Host "  Loaded $($createdBooks.Count) existing books" -ForegroundColor Yellow
    } catch {}
}

# ── Register customer alice ────────────────────────────────
Write-Host "`n[2] Registering customer alice..." -ForegroundColor Cyan
$token = $null; $custUser = $null
try {
    $reg = Invoke-Api -Method POST -Base $GW -Path "auth/register/" -Body @{username="alice";email="alice@bookstore.vn";password="alice123";role="customer"}
    $token = $reg.access_token; $custUser = $reg.user
    Write-Host "  Registered: username=$($custUser.username) cart_id=$($custUser.cart_id)" -ForegroundColor Green
} catch {
    try {
        $login = Invoke-Api -Method POST -Base $GW -Path "auth/login/" -Body @{username="alice";password="alice123"}
        $token = $login.access_token; $custUser = $login.user
        Write-Host "  Login existing: username=$($custUser.username)" -ForegroundColor Yellow
    } catch { Write-Host "  Auth failed: $_" -ForegroundColor Red }
}

$custId = $custUser.service_user_id
$cartId = $custUser.cart_id

# ── Add to cart & checkout ─────────────────────────────────
Write-Host "`n[3] Adding items to cart..." -ForegroundColor Cyan
if ($cartId -and $createdBooks.Count -ge 2) {
    try {
        Invoke-Api -Method POST -Base $GW -Path "customers/$custId/updateCart/" -Body @{book_id=$createdBooks[0].id;quantity=1} -Token $token | Out-Null
        Invoke-Api -Method POST -Base $GW -Path "customers/$custId/updateCart/" -Body @{book_id=$createdBooks[1].id;quantity=2} -Token $token | Out-Null
        Write-Host "  Added 2 books to cart $cartId" -ForegroundColor Green
    } catch { Write-Host "  Cart update: $_" -ForegroundColor Yellow }
}

Write-Host "`n[4] Checkout via Saga..." -ForegroundColor Cyan
try {
    $order = Invoke-Api -Method POST -Base $GW -Path "orders/checkout/" -Body @{
        customer_id=$custId; cart_id=$cartId
        shipping_address="123 Nguyễn Huệ, Q.1, TP.HCM"
        payment_method="credit_card"
    } -Token $token
    Write-Host "  Order id=$($order.order.id) status=$($order.order.status) success=$($order.success)" -ForegroundColor Green
} catch { Write-Host "  Checkout: $_" -ForegroundColor Yellow }

# ── Reviews ────────────────────────────────────────────────
Write-Host "`n[5] Adding reviews..." -ForegroundColor Cyan
if ($createdBooks.Count -gt 0) {
    $reviews = @(
      @{customer_id=$custId;book_id=$createdBooks[0].id;content="Cuốn sách tuyệt vời, thay đổi cách tôi viết code hoàn toàn!";rating=5},
      @{customer_id=$custId;book_id=$createdBooks[1].id;content="Rất thực tế, áp dụng được ngay vào công việc hàng ngày.";rating=4},
      @{customer_id=$custId;book_id=$createdBooks[3].id;content="Sapiens mở ra góc nhìn hoàn toàn mới về lịch sử nhân loại.";rating=5}
    )
    foreach ($rev in $reviews) {
        try {
            Invoke-Api -Method POST -Base $Cmt -Path "comments/" -Body $rev | Out-Null
            Write-Host "  Review added for book_id=$($rev.book_id)" -ForegroundColor Green
        } catch { Write-Host "  Skip review book_id=$($rev.book_id)" -ForegroundColor Yellow }
    }
}

# ── Staff admin ────────────────────────────────────────────
Write-Host "`n[6] Creating staff accounts..." -ForegroundColor Cyan
$staffAccounts = @(
    @{username="staffadmin";email="admin@bookstore.vn";password="admin123";role="admin";department="HQ"},
    @{username="staff01";email="staff01@bookstore.vn";password="staff123";role="staff";department="Kho hàng"},
    @{username="manager01";email="manager@bookstore.vn";password="manager123";role="manager";department="Quản lý"}
)
foreach ($sa in $staffAccounts) {
    try {
        $sr = Invoke-Api -Method POST -Base $Staff -Path "staff/" -Body $sa
        Write-Host "  Created: $($sa.username) ($($sa.role))" -ForegroundColor Green
    } catch { Write-Host "  Exists: $($sa.username)" -ForegroundColor Yellow }
}

# Register manager via auth service
try {
    Invoke-Api -Method POST -Base $GW -Path "auth/register/" -Body @{username="manager01";email="manager@bookstore.vn";password="manager123";role="manager"} | Out-Null
    Write-Host "  Auth registered: manager01" -ForegroundColor Green
} catch { Write-Host "  Auth manager01 exists" -ForegroundColor Yellow }

# Register staffadmin via auth service
try {
    Invoke-Api -Method POST -Base $GW -Path "auth/register/" -Body @{username="staffadmin";email="admin@bookstore.vn";password="admin123";role="staff"} | Out-Null
    Write-Host "  Auth registered: staffadmin" -ForegroundColor Green
} catch { Write-Host "  Auth staffadmin exists" -ForegroundColor Yellow }

# ── 2nd customer bob ───────────────────────────────────────
Write-Host "`n[7] Registering 2nd customer (bob)..." -ForegroundColor Cyan
try {
    $reg2 = Invoke-Api -Method POST -Base $GW -Path "auth/register/" -Body @{username="bob";email="bob@bookstore.vn";password="bob12345";role="customer"}
    Write-Host "  Registered bob: cart_id=$($reg2.user.cart_id)" -ForegroundColor Green
    if ($createdBooks.Count -ge 3) {
        Invoke-Api -Method POST -Base $GW -Path "customers/$($reg2.user.service_user_id)/updateCart/" -Body @{book_id=$createdBooks[2].id;quantity=1} -Token $reg2.access_token | Out-Null
        Write-Host "  Bob added book to cart" -ForegroundColor Green
    }
} catch { Write-Host "  Bob exists or failed" -ForegroundColor Yellow }

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Seed completed!" -ForegroundColor Green
Write-Host ""
Write-Host "  UI:           http://localhost:8000" -ForegroundColor White
Write-Host "  Staff login:  /login/" -ForegroundColor White
Write-Host ""
Write-Host "  Accounts:" -ForegroundColor Yellow
Write-Host "    Customer:  alice / alice123" -ForegroundColor White
Write-Host "    Customer:  bob / bob12345" -ForegroundColor White
Write-Host "    Staff:     staffadmin / admin123" -ForegroundColor White
Write-Host "    Manager:   manager01 / manager123" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
