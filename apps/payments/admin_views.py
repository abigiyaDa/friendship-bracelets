from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiParameter, OpenApiResponse, extend_schema, inline_serializer,
)
from rest_framework import generics, serializers, status
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.orders.status import change_status

from .admin_serializers import AdminPaymentListSerializer
from .models import Payment


class AdminPaymentListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminPaymentListSerializer
    filter_backends = [SearchFilter]
    search_fields = ["order__order_number", "transaction_ref"]

    def get_queryset(self):
        qs = Payment.objects.select_related("order", "order__customer")
        status_param = self.request.query_params.get("status")
        if status_param:
            if status_param not in Payment.Status.values:
                raise serializers.ValidationError(
                    {"status": f"Unknown status. Use one of: {', '.join(Payment.Status.values)}."}
                )
            qs = qs.filter(status=status_param)
        if status_param == Payment.Status.PENDING:
            return qs.order_by("created_at", "id")  # review queue: oldest first
        return qs.order_by("-created_at", "-id")

    @extend_schema(
        parameters=[OpenApiParameter("status", str, enum=Payment.Status.values)]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


def _conflict(message):
    return Response({"detail": message}, status=status.HTTP_409_CONFLICT)


def _review_payment(request, pk, payment_status, order_status):
    """Shared approve/reject logic. Everything happens in one transaction."""
    with transaction.atomic():
        # Lock order first, then payment. The order-status endpoint also locks
        # the order first, so the two can never deadlock each other.
        order_id = get_object_or_404(Payment.objects.only("order_id"), pk=pk).order_id
        order = Order.objects.select_for_update().get(pk=order_id)
        payment = Payment.objects.select_for_update().get(pk=pk)

        if payment.status != Payment.Status.PENDING:
            return _conflict(f"Payment is already '{payment.status}'.")
        if order.status != Order.Status.PAYMENT_REVIEW:
            return _conflict(
                f"Order is '{order.status}', it must be 'payment_review'."
            )

        payment.status = payment_status
        payment.verified_at = timezone.now()
        payment.save(update_fields=["status", "verified_at"])
        change_status(order, order_status)

    payment = Payment.objects.select_related("order__customer").get(pk=pk)
    data = AdminPaymentListSerializer(payment, context={"request": request}).data
    return Response({**data, "order_status": order.status})


_review_response = inline_serializer(
    "PaymentReviewResult",
    fields={
        "id": serializers.IntegerField(),
        "status": serializers.CharField(),
        "order_status": serializers.CharField(),
    },
)
_conflict_response = OpenApiResponse(description="Payment not pending or order not in payment_review")


class AdminPaymentApproveView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        request=None,
        responses={200: _review_response, 409: _conflict_response},
        description="Approve a pending deposit. Order moves to 'approved'.",
    )
    def post(self, request, pk):
        return _review_payment(
            request, pk, Payment.Status.APPROVED, Order.Status.APPROVED
        )


class AdminPaymentRejectView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        request=None,
        responses={200: _review_response, 409: _conflict_response},
        description="Reject a receipt. Order goes back to 'pending_payment'.",
    )
    def post(self, request, pk):
        return _review_payment(
            request, pk, Payment.Status.REJECTED, Order.Status.PENDING_PAYMENT
        )
