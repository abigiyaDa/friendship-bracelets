from django.db.models import Prefetch
from rest_framework import generics

from .models import Category, Color, Product
from .serializers import (
    CategorySerializer,
    ColorSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
)


class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer


class ColorListView(generics.ListAPIView):
    queryset = Color.objects.filter(is_available=True).order_by("name")
    serializer_class = ColorSerializer


def active_products():
    return (
        Product.objects.filter(is_active=True)
        .select_related("category")
        .prefetch_related(
            "images",
            Prefetch("colors", queryset=Color.objects.filter(is_available=True)),
        )
    )


class ProductListView(generics.ListAPIView):
    serializer_class = ProductListSerializer

    def get_queryset(self):
        qs = active_products().order_by("-created_at")
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category__slug=category)
        return qs


class ProductDetailView(generics.RetrieveAPIView):
    serializer_class = ProductDetailSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return active_products()