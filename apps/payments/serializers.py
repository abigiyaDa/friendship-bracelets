import os
import uuid

from rest_framework import serializers

from .models import Payment

MAX_RECEIPT_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_FORMATS = {"JPEG", "PNG"}


class PaymentCreateSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=Payment.Method.choices)
    transaction_ref = serializers.CharField(max_length=100)
    receipt = serializers.ImageField()
    # optional: if the client sends it, it must equal the deposit
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)

    def validate_receipt(self, value):
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise serializers.ValidationError("Only .jpg, .jpeg or .png files are allowed.")
        if value.size > MAX_RECEIPT_SIZE:
            raise serializers.ValidationError("File is too large (max 5 MB).")
        fmt = getattr(getattr(value, "image", None), "format", None)
        if fmt not in ALLOWED_FORMATS:
            raise serializers.ValidationError("File must be a real JPG or PNG image.")
        value.name = f"{uuid.uuid4().hex}{ext}"  # random name, saved under media/receipts/
        return value

    def validate(self, attrs):
        order = self.context["order"]
        amount = attrs.get("amount")
        if amount is not None and amount != order.deposit_amount:
            raise serializers.ValidationError(
                {"amount": f"Amount must equal the deposit ({order.deposit_amount})."}
            )
        return attrs


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id", "payment_type", "method", "amount",
            "transaction_ref", "status", "created_at",
        ]