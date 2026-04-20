from django.contrib import admin

from .infrastructure.models import Brand, Category, Product, ProductType, ProductVariant


@admin.register(ProductType)
class ProductTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug', 'icon')
    search_fields = ('name', 'slug')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug', 'parent')
    search_fields = ('name', 'slug')


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug', 'country')
    search_fields = ('name', 'slug')


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'product_type', 'brand', 'price', 'stock', 'is_active')
    list_filter = ('product_type', 'category', 'brand', 'is_active')
    search_fields = ('name', 'author', 'slug')
    inlines = [ProductVariantInline]
