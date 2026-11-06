import secrets
import string
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from rest_framework import serializers

from apps.catalog.models import Color, Product, ProductColor
from apps.pickups.models import PickupLocation

from .models import Customer, Order, OrderItem, OrderItemColor

DEPOSIT_PERCENT = 50
ORDER_NUMBER_PREFIX = "BR-"
ORDER_NUMBER_ALPHABET = string.ascii_uppercase + string.digits
ORDER_NUMBER_LENGTH = 8
DEFAULT_MAX_NAME_LENGTH = 50  # OrderItem.name_text max_length


def generate_order_number():
    """Return a unique order number like BR-7K2QX9AB (11 chars)."""
    while True:
        random_part = "".join(
            secrets.choice(ORDER_NUMBER_ALPHABET) for _ in range(ORDER_NUMBER_LENGTH)
        )
        order_number = f"{ORDER_NUMBER_PREFIX}{random_part}"
        if not Order.objects.filter(order_number=order_number).exists():
            return order_number


class CustomerInputSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=120)
    phone = serializers.CharField(max_length=20)
    email = serializers.EmailField(
        max_length=254, required=False, allow_blank=True, allow_null=True
    )
    telegram_username = serializers.CharField(
        max_length=64, required=False, allow_blank=True, allow_null=True
    )

    def validate_phone(self, value):
        # Remove every space so "0911 000 000" and "0911000000" match.
        phone = "".join(value.split())
        if not phone:
            raise serializers.ValidationError("This field may not be blank.")
        return phone


class OrderItemInputSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True),
        error_messages={
            "does_not_exist": "Product does not exist or is not active.",
        },
    )
    quantity = serializers.IntegerField(min_value=1, max_value=32767)
    color_mode = serializers.ChoiceField(choices=OrderItem.ColorMode.choices)
    colors = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )
    name_text = serializers.CharField(
        max_length=DEFAULT_MAX_NAME_LENGTH,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    notes = serializers.CharField(
        max_length=500, required=False, allow_blank=True, allow_null=True
    )

    def validate(self, attrs):
        product = attrs["product"]
        color_mode = attrs["color_mode"]
        colors = attrs.get("colors", [])
        name_text = (attrs.get("name_text") or "").strip()
        errors = {}

        # --- colors ---
        if color_mode == OrderItem.ColorMode.CUSTOM:
            if not product.allows_custom_colors:
                errors["color_mode"] = "This product does not allow custom colors."
            elif not colors:
                errors["colors"] = "Choose at least one color for a custom order."
            else:
                allowed_ids = set(
                    ProductColor.objects.filter(
                        product=product,
                        color_id__in=colors,
                        color__is_available=True,
                    ).values_list("color_id", flat=True)
                )
                bad_ids = sorted(set(colors) - allowed_ids)
                if bad_ids:
                    errors["colors"] = (
                        f"Color(s) {bad_ids} are not available for this product."
                    )
        else:  # as_in_picture
            if colors:
                errors["colors"] = "Colors must be empty when color_mode is 'as_in_picture'."

        # --- name text ---
        if name_text:
            if not product.allows_name_text:
                errors["name_text"] = "This product does not allow a name."
            else:
                max_len = product.max_name_length or DEFAULT_MAX_NAME_LENGTH
                if len(name_text) > max_len:
                    errors["name_text"] = (
                        f"Name must be at most {max_len} characters."
                    )

        if errors:
            raise serializers.ValidationError(errors)

        attrs["name_text"] = name_text or None
        attrs["notes"] = (attrs.get("notes") or "").strip() or None
        return attrs


class OrderCreateSerializer(serializers.Serializer):
    customer = CustomerInputSerializer()
    pickup_location = serializers.PrimaryKeyRelatedField(
        queryset=PickupLocation.objects.filter(is_active=True),
        error_messages={
            "does_not_exist": "Pickup location does not exist or is not active.",
        },
    )
    customer_note = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    items = OrderItemInputSerializer(many=True, allow_empty=False)

    def create(self, validated_data):
        customer_data = validated_data["customer"]
        items_data = validated_data["items"]

        with transaction.atomic():
            customer, _ = Customer.objects.get_or_create(
                phone=customer_data["phone"],
                defaults={
                    "full_name": customer_data["full_name"],
                    "email": customer_data.get("email") or None,
                    "telegram_username": customer_data.get("telegram_username") or None,
                },
            )

            # Money is calculated here from DB prices, never from the client.
            total_amount = sum(
                (item["product"].price * item["quantity"] for item in items_data),
                Decimal("0"),
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            deposit_amount = (
                total_amount * DEPOSIT_PERCENT / Decimal("100")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            order = Order.objects.create(
                order_number=generate_order_number(),
                customer=customer,
                pickup_location=validated_data["pickup_location"],
                total_amount=total_amount,
                deposit_percent=DEPOSIT_PERCENT,
                deposit_amount=deposit_amount,
                customer_note=(validated_data.get("customer_note") or "").strip()
                or None,
            )

            for item in items_data:
                product = item["product"]
                order_item = OrderItem.objects.create(
                    order=order,
                    product=product,
                    product_name=product.name,
                    unit_price=product.price,
                    quantity=item["quantity"],
                    color_mode=item["color_mode"],
                    name_text=item["name_text"],
                    notes=item["notes"],
                )
                OrderItemColor.objects.bulk_create(
                    [
                        OrderItemColor(
                            order_item=order_item,
                            position=position,
                            color_id=color_id,
                        )
                        for position, color_id in enumerate(item["colors"], start=1)
                    ]
                )

        return order


class OrderCreatedSerializer(serializers.ModelSerializer):
    """Output only: what the client gets back after creating an order."""

    class Meta:
        model = Order
        fields = [
            "order_number",
            "status",
            "total_amount",
            "deposit_percent",
            "deposit_amount",
        ]
        read_only_fields = fields