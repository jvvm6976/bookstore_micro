from django.contrib import admin
from .models import Domain, Category, Product, Book, Electronics, Fashion


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'updated_at')
    search_fields = ('name',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'domain', 'created_at')
    list_filter = ('domain',)
    search_fields = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'stock', 'status')
    list_filter = ('category__domain', 'category', 'status')
    search_fields = ('name', 'sku')


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('product', 'author', 'isbn')
    search_fields = ('product__name', 'author', 'isbn')


@admin.register(Electronics)
class ElectronicsAdmin(admin.ModelAdmin):
    list_display = ('product', 'brand', 'warranty_months')
    search_fields = ('product__name', 'brand')


@admin.register(Fashion)
class FashionAdmin(admin.ModelAdmin):
    list_display = ('product', 'size', 'color')
    search_fields = ('product__name', 'size', 'color')
