import re

from django.db.models import Sum
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, serializers
from rest_framework.throttling import ScopedRateThrottle

from apps.pickups.serializers import PickupLocationSerializer

from .models import Order


def phone_variants(raw):
    """0911223344, +251911223344, 251911223344 and 911223344 all match the same customer."""
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return set()
    variants = {digits}  # exact match always counts
    if digits.startswith("251"):
        national = digits[3:]
    elif digits.startswith("0"):
        national = digits[1:]
    else:
        national = digits
    if len(national) == 9:
        variants.update({national, f"0{national}", f"251{national}", f"+251{national}"})
    return variants


class OrderSummarySerializer(serializers.ModelSerializer):
    pickup_location = PickupLocationSerializer(read_only=True)
    item_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Order
        fields = [
            "order_number", "status", "total_amount", "deposit_amount",
            "pickup_location", "item_count", "created_at",
        ]


class OrderLookupView(generics.ListAPIView):
    """Public: all orders for a phone number (summary only, newest first)."""

    serializer_class = OrderSummarySerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "order_lookup"

    def get_queryset(self):
        phone = self.request.query_params.get("phone", "").strip()
        if not phone:
            raise serializers.ValidationError({"phone": "This query parameter is required."})
        return (
            Order.objects.filter(customer__phone__in=phone_variants(phone))
            .select_related("pickup_location")
            .annotate(item_count=Sum("items__quantity", default=0))
            .order_by("-created_at", "-id")
        )

    @extend_schema(parameters=[OpenApiParameter("phone", str, required=True)])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)