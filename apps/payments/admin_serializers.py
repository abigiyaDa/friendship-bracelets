from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Payment


class AdminPaymentSerializer(serializers.ModelSerializer):
    """Payment as the admin sees it. Includes the receipt URL.

    The public PaymentSerializer stays untouched and keeps hiding receipts.
    """

    receipt = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id", "payment_type", "method", "amount", "transaction_ref",
            "status", "verified_at", "created_at", "receipt",
        ]

    @extend_schema_field(OpenApiTypes.URI)
    def get_receipt(self, obj):
        if not obj.screenshot:
            return None
        request = self.context.get("request")
        url = obj.screenshot.url
        return request.build_absolute_uri(url) if request else url


class AdminPaymentListSerializer(AdminPaymentSerializer):
    order = serializers.IntegerField(source="order_id", read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    customer_name = serializers.CharField(
        source="order.customer.full_name", read_only=True
    )

    class Meta(AdminPaymentSerializer.Meta):
        fields = AdminPaymentSerializer.Meta.fields + [
            "order", "order_number", "customer_name",
        ]
