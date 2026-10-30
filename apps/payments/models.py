from django.db import models

# Create your models here.
# Payment

class Payment(models.Model):
    class PaymentType(models.TextChoices):
        DEPOSIT = "deposit", "Deposit"
        FULL = "full", "Full payment"

    class Method(models.TextChoices):
        TELEBIRR = "telebirr", "Telebirr"
        BANK_TRANSFER = "bank_transfer", "Bank transfer"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    order = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, related_name="payments"
    )
    payment_type = models.CharField(max_length=20, choices=PaymentType.choices)
    method = models.CharField(max_length=20, choices=Method.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_ref = models.CharField(max_length=100, null=True, blank=True)
    screenshot = models.ImageField(upload_to="receipts/", null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order.order_number} - {self.payment_type} ({self.status})"