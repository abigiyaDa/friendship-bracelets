from django.db import models

# Create your models here.
# Customer , Order , OrderItem, OrderItemColor


class Customer(models.Model):
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(max_length=254, null=True, blank=True)
    telegram_username = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name} ({self.phone})"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "Pending payment"
        PAYMENT_REVIEW = "payment_review", "Payment review"
        APPROVED = "approved", "Approved"
        IN_PRODUCTION = "in_production", "In production"
        READY = "ready", "Ready"
        PICKED_UP = "picked_up", "Picked up"
        CANCELLED = "cancelled", "Cancelled"

    order_number = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="orders"
    )
    pickup_location = models.ForeignKey(
        "pickups.PickupLocation", on_delete=models.PROTECT, related_name="orders"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING_PAYMENT
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    deposit_percent = models.PositiveSmallIntegerField()
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    customer_note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "orders"

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):
    class ColorMode(models.TextChoices):
        CUSTOM = "custom", "Custom colors"
        AS_IN_PICTURE = "as_in_picture", "As in picture"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="order_items"
    )
    product_name = models.CharField(max_length=150)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveSmallIntegerField(default=1)
    color_mode = models.CharField(max_length=20, choices=ColorMode.choices)
    name_text = models.CharField(max_length=50, null=True, blank=True)
    notes = models.CharField(max_length=500, null=True, blank=True)

    def __str__(self):
        return f"{self.product_name} x{self.quantity} ({self.order.order_number})"


class OrderItemColor(models.Model):
    order_item = models.ForeignKey(
        OrderItem, on_delete=models.CASCADE, related_name="colors"
    )
    position = models.PositiveSmallIntegerField()
    color = models.ForeignKey(
        "catalog.Color", on_delete=models.PROTECT, related_name="order_item_colors"
    )

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["order_item", "position"], name="unique_item_color_position"
            )
        ]

    def __str__(self):
        return f"{self.order_item} - {self.position}: {self.color.name}"