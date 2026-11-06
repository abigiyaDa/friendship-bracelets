from django.db import transaction
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, serializers, status
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.models import Payment

from .admin_serializers import (
    AdminCustomerDetailSerializer, AdminCustomerListSerializer,
    AdminOrderDetailSerializer, AdminOrderListSerializer,
    OrderStatusUpdateSerializer,
)
from .models import Customer, Order
from .status import InvalidStatusTransition, change_status

Status = Order.Status

# These two must go through payment approve/reject so order and payment agree.
BLOCKED_FROM_PAYMENT_REVIEW = {Status.APPROVED, Status.PENDING_PAYMENT}


def can_repair_review(order):
    """True when a review order can safely be marked approved directly.

    Legacy or interrupted data can leave an order in payment_review even though
    an admin already approved its payment. Allowing the missing
    payment_review -> approved step only when no payment is still pending and
    at least one payment is approved lets the order catch up with its payment.
    """
    payments = order.payments.all()
    return (
        not payments.filter(status=Payment.Status.PENDING).exists()
        and payments.filter(status=Payment.Status.APPROVED).exists()
    )


def order_detail_queryset():
    return (
        Order.objects.select_related("customer", "pickup_location")
        .prefetch_related(
            "items__colors__color",
            Prefetch("payments", queryset=Payment.objects.order_by("created_at", "id")),
        )
    )


# ---------------------------------------------------------------- orders
class AdminOrderListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminOrderListSerializer
    filter_backends = [SearchFilter]
    search_fields = ["order_number", "customer__phone", "customer__full_name"]

    def get_queryset(self):
        qs = (
            Order.objects.select_related("customer", "pickup_location")
            .annotate(item_count=Count("items"))
        )
        status_param = self.request.query_params.get("status")
        if status_param:
            if status_param not in Status.values:
                raise serializers.ValidationError(
                    {"status": f"Unknown status. Use one of: {', '.join(Status.values)}."}
                )
            qs = qs.filter(status=status_param)
        return qs.order_by("-created_at", "-id")

    @extend_schema(parameters=[OpenApiParameter("status", str, enum=Status.values)])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminOrderDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminOrderDetailSerializer
    queryset = order_detail_queryset()  # looked up by database id (pk)


class AdminOrderStatusView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        request=OrderStatusUpdateSerializer,
        responses=AdminOrderDetailSerializer,
        description=(
            "Move an order to a new status using the allowed transitions. "
            "payment_review -> approved / pending_payment must use the payment "
            "approve/reject endpoints, except that payment_review -> approved is "
            "allowed when the order has an approved payment and no pending one "
            "(repairing an order whose status fell behind its payment)."
        ),
    )
    def patch(self, request, pk):
        body = OrderStatusUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        new_status = body.validated_data["status"]

        with transaction.atomic():
            order = get_object_or_404(Order.objects.select_for_update(), pk=pk)

            if order.status == Status.PAYMENT_REVIEW and new_status in BLOCKED_FROM_PAYMENT_REVIEW:
                repairing_approval = (
                    new_status == Status.APPROVED and can_repair_review(order)
                )
                if not repairing_approval:
                    return Response(
                        {"detail": "Use the payment approve/reject endpoints."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            was_in_review = order.status == Status.PAYMENT_REVIEW
            try:
                change_status(order, new_status)
            except InvalidStatusTransition as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            # Cancelled while a receipt was waiting: close those payments too.
            if was_in_review and new_status == Status.CANCELLED:
                order.payments.filter(status=Payment.Status.PENDING).update(
                    status=Payment.Status.REJECTED, verified_at=timezone.now()
                )

        fresh = order_detail_queryset().get(pk=pk)
        return Response(
            AdminOrderDetailSerializer(fresh, context={"request": request}).data
        )


# ------------------------------------------------------------- customers
class AdminCustomerListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminCustomerListSerializer
    filter_backends = [SearchFilter]
    search_fields = ["full_name", "phone", "email", "telegram_username"]
    queryset = Customer.objects.annotate(order_count=Count("orders")).order_by(
        "-created_at", "-id"
    )


class AdminCustomerDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminCustomerDetailSerializer
    http_method_names = ["get", "patch", "head", "options"]  # no PUT, no DELETE
    queryset = (
        Customer.objects.annotate(order_count=Count("orders"))
        .prefetch_related(
            Prefetch("orders", queryset=Order.objects.order_by("-created_at", "-id"))
        )
    )
