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
    return render(request, "manager.html")

def staff_page(request):
    return render(request, "staff.html")

def index_page(request):
    return redirect("/")
