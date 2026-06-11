from django.shortcuts import redirect, render

# ═══ FRONTEND PAGES ═══
def home(request):
    return render(request, "home.html")

def login_page(request):
    return render(request, "login.html")

def register_page(request):
    return render(request, "register.html")

def dashboard(request):
    return render(request, "dashboard.html")

def product_home(request):
    return render(request, "search.html", {"query": request.GET.get("q", "")})

def cart_page(request):
    return render(request, "cart_page.html")

def checkout_page(request):
    return render(request, "checkout_page.html")

def customer_login(request):
    return render(request, "login.html")

def manager_page(request):
    return render(request, "admin_dashboard.html", {
        "portal_kind": "admin",
        "portal_active": "dashboard",
        "portal_title": "Tổng quan hệ thống",
        "portal_subtitle": "Theo dõi người dùng, sản phẩm, đơn hàng và hoạt động vận hành.",
    })

def staff_page(request):
    return render(request, "staff_dashboard.html", {
        "portal_kind": "staff",
        "portal_active": "dashboard",
        "portal_title": "Tổng quan tác nghiệp",
        "portal_subtitle": "Các công việc cần xử lý trong ca làm việc hiện tại.",
    })

def index_page(request):
    return redirect("/")
