from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.orders.status import change_status

from .models import Payment
from .serializers import PaymentCreateSerializer, PaymentSerializer
from drf_spectacular.utils import OpenApiTypes, extend_schema


class PaymentCreateView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["telebirr", "bank_transfer"]},
                    "transaction_ref": {"type": "string"},
                    "receipt": {"type": "string", "format": "binary"},
                    "amount": {"type": "string", "format": "decimal"},
                },
                "required": ["method", "transaction_ref", "receipt"],
            }
        },
        responses={201: PaymentSerializer},
    )
    def post(self, request, order_number):
        with transaction.atomic():
            # lock the row so two uploads can't both pass the status check
            order = get_object_or_404(
                Order.objects.select_for_update(), order_number=order_number
            )

            if order.status != Order.Status.PENDING_PAYMENT:
                return Response(
                    {"detail": f"Order is '{order.status}', payment cannot be submitted."},
                    status=status.HTTP_409_CONFLICT,
                )

            serializer = PaymentCreateSerializer(
                data=request.data, context={"order": order}
            )
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data

            payment = Payment.objects.create(
                order=order,
                payment_type=Payment.PaymentType.DEPOSIT,
                method=data["method"],
                amount=order.deposit_amount,  # server decides the amount
                transaction_ref=data["transaction_ref"],
                screenshot=data["receipt"],
            )
            change_status(order, Order.Status.PAYMENT_REVIEW)

        body = PaymentSerializer(payment).data
        body["order_status"] = order.status
        return Response(body, status=status.HTTP_201_CREATED)