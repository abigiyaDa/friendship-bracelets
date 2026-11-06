from rest_framework import serializers

from apps.catalog.serializers import ColorSerializer
from apps.payments.admin_serializers import AdminPaymentSerializer

from apps.pickups.models import PickupLocation

from .models import Customer, Order, OrderItem, OrderItemColor
from .order_lookup import OrderSummarySerializer


class AdminCustomerMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "full_name", "phone"]


class AdminCustomerBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "full_name", "phone", "email", "telegram_username"]


class AdminPickupSerializer(serializers.ModelSerializer):
    class Meta:
        model = PickupLocation
        fields = ["id", "name", "area", "details"]


class AdminOrderListSerializer(serializers.ModelSerializer):
    customer = AdminCustomerMiniSerializer(read_only=True)
    pickup_location = serializers.CharField(source="pickup_location.name", read_only=True)
    item_count = serializers.IntegerField(read_only=True)  # annotated in the view

    class Meta:
        model = Order
        fields = [
            "id", "order_number", "status", "customer", "pickup_location",
            "total_amount", "deposit_amount", "item_count", "created_at",
        ]


class AdminOrderItemColorSerializer(serializers.ModelSerializer):
    color = ColorSerializer(read_only=True)

    class Meta:
        model = OrderItemColor
        fields = ["position", "color"]


class AdminOrderItemSerializer(serializers.ModelSerializer):
    colors = AdminOrderItemColorSerializer(many=True, read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id", "product_name", "unit_price", "quantity", "color_mode",
            "name_text", "notes", "colors",
        ]


class AdminOrderDetailSerializer(serializers.ModelSerializer):
    customer = AdminCustomerBriefSerializer(read_only=True)
    pickup_location = AdminPickupSerializer(read_only=True)
    items = AdminOrderItemSerializer(many=True, read_only=True)
    payments = AdminPaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id", "order_number", "status", "customer", "pickup_location",
            "total_amount", "deposit_percent", "deposit_amount", "customer_note",
            "created_at", "updated_at", "items", "payments",
        ]


class OrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)


class AdminCustomerListSerializer(serializers.ModelSerializer):
    order_count = serializers.IntegerField(read_only=True)  # annotated in the view

    class Meta:
        model = Customer
        fields = [
            "id", "full_name", "phone", "email", "telegram_username",
            "created_at", "order_count",
        ]
        # phone is the customer's identity (unique key, used by order lookup)
        read_only_fields = ["phone", "created_at"]


class AdminCustomerDetailSerializer(AdminCustomerListSerializer):
    orders = OrderSummarySerializer(many=True, read_only=True)

    class Meta(AdminCustomerListSerializer.Meta):
        fields = AdminCustomerListSerializer.Meta.fields + ["orders"]
