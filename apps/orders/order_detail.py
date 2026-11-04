from django.db.models import Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.serializers import ColorSerializer
from apps.payments.models import Payment
from apps.payments.serializers import PaymentSerializer
from apps.pickups.serializers import PickupLocationSerializer

from .models import Order, OrderItem, OrderItemColor


class OrderItemColorSerializer(serializers.ModelSerializer):
    color = ColorSerializer(read_only=True)

    class Meta:
        model = OrderItemColor
        fields = ["position", "color"]


class OrderItemDetailSerializer(serializers.ModelSerializer):
    colors = OrderItemColorSerializer(many=True, read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id", "product_name", "unit_price", "quantity",
            "color_mode", "name_text", "notes", "colors",
        ]


class OrderDetailSerializer(serializers.ModelSerializer):
    pickup_location = PickupLocationSerializer(read_only=True)
    items = OrderItemDetailSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "order_number", "status", "total_amount", "deposit_percent",
            "deposit_amount", "customer_note", "created_at",
            "pickup_location", "items", "payments",
        ]


class OrderDetailView(APIView):
    @extend_schema(
        parameters=[OpenApiParameter("phone", str, required=True)],
        responses=OrderDetailSerializer,
    )
    def get(self, request, order_number):
        phone = request.query_params.get("phone", "").strip()
        if not phone:
            raise Http404  # same response as a wrong phone: nothing leaks

        queryset = (
            Order.objects.select_related("pickup_location", "customer")
            .prefetch_related(
                "items__colors__color",
                Prefetch("payments", queryset=Payment.objects.order_by("created_at")),
            )
        )
        order = get_object_or_404(
            queryset, order_number=order_number, customer__phone=phone
        )
        return Response(OrderDetailSerializer(order).data)