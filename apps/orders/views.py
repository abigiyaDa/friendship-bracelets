from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response

from .serializers import OrderCreatedSerializer, OrderCreateSerializer


class OrderCreateView(generics.CreateAPIView):
    """Public endpoint: a customer sends their info + cart and gets an order back."""

    serializer_class = OrderCreateSerializer

    @extend_schema(
        request=OrderCreateSerializer,
        responses={201: OrderCreatedSerializer},
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(
            OrderCreatedSerializer(order).data, status=status.HTTP_201_CREATED
        )