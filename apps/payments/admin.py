from django.contrib import admin

# Register your models here.

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "order", "payment_type", "method", "amount", "status", "created_at",
    )
    list_filter = ("status", "method", "payment_type")
    search_fields = ("order__order_number", "transaction_ref")