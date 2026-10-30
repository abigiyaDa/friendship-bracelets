from django.contrib import admin

from .models import Customer, Order, OrderItem, OrderItemColor


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "email", "telegram_username")
    search_fields = ("full_name", "phone")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number", "customer", "status", "total_amount",
        "deposit_amount", "pickup_location", "created_at",
    )
    list_filter = ("status", "pickup_location")
    search_fields = ("order_number", "customer__full_name", "customer__phone")
    inlines = [OrderItemInline]


class OrderItemColorInline(admin.TabularInline):
    model = OrderItemColor
    extra = 0


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("product_name", "order", "quantity", "color_mode")
    inlines = [OrderItemColorInline]


@admin.register(OrderItemColor)
class OrderItemColorAdmin(admin.ModelAdmin):
    list_display = ("order_item", "position", "color")