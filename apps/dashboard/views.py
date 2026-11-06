from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Max, ProtectedError, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.filters import SearchFilter
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Category, Color, Product, ProductImage
from apps.catalog.serializers import ColorSerializer
from apps.orders.models import Customer, Order, OrderItem
from apps.payments.models import Payment
from apps.pickups.models import PickupLocation

from .serializers import (
    AdminStatsSerializer,
    CategoryAdminSerializer,
    ColorAdminSerializer,
    PickupLocationAdminSerializer,
    ProductAdminSerializer,
    ProductColorsSerializer,
    ProductImageAdminSerializer,
)

FILE_PARSERS = [MultiPartParser, FormParser, JSONParser]


class AdminMixin:
    permission_classes = [IsAdminUser]


class ProtectedDeleteMixin:
    """Turn 'still referenced' DB errors into a clean 409 instead of a 500."""

    protected_message = "This item is still in use and cannot be deleted."

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({"detail": self.protected_message}, status=status.HTTP_409_CONFLICT)


# ---------- categories ----------

class CategoryListCreateView(AdminMixin, generics.ListCreateAPIView):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategoryAdminSerializer
    parser_classes = FILE_PARSERS
    pagination_class = None


class CategoryDetailView(AdminMixin, ProtectedDeleteMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    serializer_class = CategoryAdminSerializer
    parser_classes = FILE_PARSERS
    protected_message = "This category still has products. Move or deactivate them first."


# ---------- colors ----------

class ColorListCreateView(AdminMixin, generics.ListCreateAPIView):
    queryset = Color.objects.all().order_by("name")  # includes unavailable colors
    serializer_class = ColorAdminSerializer
    pagination_class = None


class ColorDetailView(AdminMixin, ProtectedDeleteMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Color.objects.all()
    serializer_class = ColorAdminSerializer
    protected_message = "This color is used in orders. Set is_available=false instead."


# ---------- products ----------

def product_queryset():
    return Product.objects.select_related("category").prefetch_related("images", "colors")


class ProductListCreateView(AdminMixin, generics.ListCreateAPIView):
    """GET: all products incl. inactive. ?search=, ?is_active=true|false, ?category=<id>"""

    serializer_class = ProductAdminSerializer
    parser_classes = FILE_PARSERS
    filter_backends = [SearchFilter]
    search_fields = ["name", "slug"]

    def get_queryset(self):
        qs = product_queryset().order_by("-created_at", "-id")
        params = self.request.query_params
        is_active = params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ("true", "1"))
        category = params.get("category")
        if category and category.isdigit():
            qs = qs.filter(category_id=int(category))
        return qs


class ProductDetailView(AdminMixin, generics.RetrieveUpdateDestroyAPIView):
    """DELETE deactivates (products are PROTECTed by order items). PATCH is_active=true restores."""

    serializer_class = ProductAdminSerializer
    parser_classes = FILE_PARSERS
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return product_queryset()

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])


# ---------- product images ----------

def ensure_primary(product):
    """If a product has images but none is primary, promote the first one."""
    images = product.images.order_by("sort_order", "id")
    if images.exists() and not images.filter(is_primary=True).exists():
        first = images.first()
        first.is_primary = True
        first.save(update_fields=["is_primary"])


class ProductImageCreateView(AdminMixin, generics.CreateAPIView):
    serializer_class = ProductImageAdminSerializer
    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):
        product = get_object_or_404(Product, pk=self.kwargs["product_id"])
        data = serializer.validated_data
        with transaction.atomic():
            is_primary = data.get("is_primary", False) or not product.images.exists()
            if is_primary:
                product.images.update(is_primary=False)
            extra = {"product": product, "is_primary": is_primary}
            if "sort_order" not in data:
                last = product.images.aggregate(m=Max("sort_order"))["m"]
                extra["sort_order"] = 0 if last is None else last + 1
            serializer.save(**extra)


class ProductImageDetailView(AdminMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductImageAdminSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["get", "patch", "delete", "head", "options"]
    lookup_url_kwarg = "image_id"

    def get_queryset(self):
        return ProductImage.objects.filter(product_id=self.kwargs["product_id"])

    def perform_update(self, serializer):
        with transaction.atomic():
            image = serializer.save()
            if image.is_primary:
                image.product.images.exclude(pk=image.pk).update(is_primary=False)
            ensure_primary(image.product)

    def perform_destroy(self, instance):
        product = instance.product
        with transaction.atomic():
            instance.image.delete(save=False)  # remove the file from disk too
            instance.delete()
            ensure_primary(product)


# ---------- product colors ----------

class ProductColorsView(AdminMixin, APIView):
    """PUT the full list of color ids; replaces the product's color set."""

    @extend_schema(request=ProductColorsSerializer, responses=ColorSerializer(many=True))
    def put(self, request, product_id):
        product = get_object_or_404(Product, pk=product_id)
        serializer = ProductColorsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product.colors.set(serializer.validated_data["color_ids"])
        return Response(ColorSerializer(product.colors.order_by("name"), many=True).data)


# ---------- pickup locations ----------

class PickupLocationListCreateView(AdminMixin, generics.ListCreateAPIView):
    queryset = PickupLocation.objects.all().order_by("area", "name")  # includes inactive
    serializer_class = PickupLocationAdminSerializer
    pagination_class = None


class PickupLocationDetailView(AdminMixin, ProtectedDeleteMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = PickupLocation.objects.all()
    serializer_class = PickupLocationAdminSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]
    protected_message = "Orders use this location. Set is_active=false instead."

# ---------- stats ----------

SALES_STATUSES = [
    Order.Status.APPROVED,
    Order.Status.IN_PRODUCTION,
    Order.Status.READY,
    Order.Status.PICKED_UP,
]
DAILY_DAYS = 30


def money(value):
    return f"{(value or Decimal('0.00')):.2f}"


class AdminStatsView(AdminMixin, APIView):
    """Aggregate numbers for the admin dashboard."""

    @extend_schema(responses=AdminStatsSerializer)
    def get(self, request):
        tz = ZoneInfo(settings.TIME_ZONE)
        today = timezone.localdate()
        start_date = today - timedelta(days=DAILY_DAYS - 1)
        start_dt = timezone.make_aware(datetime.combine(start_date, time.min), tz)

        order_totals = Order.objects.aggregate(
            orders=Count("id"),
            sales=Sum("total_amount", filter=Q(status__in=SALES_STATUSES)),
        )
        customers = Customer.objects.count()
        pending_payment_reviews = Payment.objects.filter(
            status=Payment.Status.PENDING
        ).count()

        status_rows = Order.objects.values("status").annotate(count=Count("id"))
        counts_by_status = {row["status"]: row["count"] for row in status_rows}
        orders_by_status = {
            choice: counts_by_status.get(choice, 0) for choice, _ in Order.Status.choices
        }

        daily_rows = (
            Order.objects.filter(created_at__gte=start_dt)
            .annotate(day=TruncDate("created_at", tzinfo=tz))
            .values("day")
            .annotate(
                orders=Count("id"),
                sales=Sum("total_amount", filter=Q(status__in=SALES_STATUSES)),
            )
        )
        daily_by_date = {row["day"]: row for row in daily_rows}
        daily = [
            {
                "date": (start_date + timedelta(days=offset)).isoformat(),
                "orders": daily_by_date.get(start_date + timedelta(days=offset), {}).get("orders", 0),
                "sales": money(
                    daily_by_date.get(start_date + timedelta(days=offset), {}).get("sales")
                ),
            }
            for offset in range(DAILY_DAYS)
        ]

        top_products = (
            OrderItem.objects.exclude(order__status=Order.Status.CANCELLED)
            .values("product_name")
            .annotate(quantity=Sum("quantity"))
            .order_by("-quantity", "product_name")[:5]
        )

        return Response(
            {
                "totals": {
                    "orders": order_totals["orders"],
                    "customers": customers,
                    "sales": money(order_totals["sales"]),
                    "pending_payment_reviews": pending_payment_reviews,
                },
                "orders_by_status": orders_by_status,
                "daily": daily,
                "top_products": [
                    {"product_name": row["product_name"], "quantity": row["quantity"]}
                    for row in top_products
                ],
            }
        )
