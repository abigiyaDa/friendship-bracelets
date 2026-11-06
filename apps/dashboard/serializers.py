import re

from django.core.validators import RegexValidator
from django.db import transaction
from django.db.models import Max
from django.utils.text import slugify
from rest_framework import serializers

from apps.catalog.models import Category, Color, Product, ProductImage
from apps.catalog.serializers import ColorSerializer
from apps.pickups.models import PickupLocation

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


def unique_slug(model, source, max_length):
    base = slugify(source)[:max_length] or "item"
    slug, n = base, 2
    while model.objects.filter(slug=slug).exists():
        suffix = f"-{n}"
        slug = base[: max_length - len(suffix)] + suffix
        n += 1
    return slug


def check_color_ids(ids):
    ids = list(dict.fromkeys(ids))  # dedupe, keep order
    found = set(Color.objects.filter(id__in=ids).values_list("id", flat=True))
    missing = [i for i in ids if i not in found]
    if missing:
        raise serializers.ValidationError(f"Unknown color ids: {missing}")
    return ids


def check_image_size(value):
    if value.size > MAX_IMAGE_SIZE:
        raise serializers.ValidationError("Image is too large (max 5 MB).")
    return value

class FormCleanMixin:
    """
    Multipart/form requests (Swagger sends every field, empty ones as ''):
    - drop empty values, so untouched fields mean "not provided"
    - split comma-separated lists like color_ids="1,2"
    To clear a field on purpose, send JSON (null / ""), not multipart.
    """

    list_fields = ()          # keys that stay lists (repeat keys or comma-separated)
    comma_list_fields = ()    # list keys that may also arrive as "1,2"

    def to_internal_value(self, data):
        if hasattr(data, "getlist"):
            cleaned = {}
            for key in data.keys():
                values = [v for v in data.getlist(key) if v not in ("", None)]
                if not values:
                    continue
                if key in self.comma_list_fields:
                    values = [
                        p.strip() for v in values for p in str(v).split(",") if p.strip()
                    ]
                if key in self.list_fields or key in self.comma_list_fields:
                    cleaned[key] = values
                else:
                    cleaned[key] = values[-1]
            data = cleaned
        return super().to_internal_value(data) 
    
# ---------- categories / colors ----------

class CategoryAdminSerializer(FormCleanMixin,serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "image"]
        extra_kwargs = {"slug": {"required": False}}  # generated from name if omitted

    def validate_image(self, value):
        return check_image_size(value) if value else value

    def create(self, validated_data):
        if not validated_data.get("slug"):
            validated_data["slug"] = unique_slug(Category, validated_data["name"], 120)
        return super().create(validated_data)


class ColorAdminSerializer(serializers.ModelSerializer):
    hex_code = serializers.CharField(
        max_length=7, required=False, allow_null=True, allow_blank=True,
        validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Use a hex code like #FF00AA.")],
    )

    class Meta:
        model = Color
        fields = ["id", "name", "hex_code", "is_available"]


# ---------- products ----------

class ProductImageAdminSerializer(FormCleanMixin,serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "is_primary", "sort_order"]

    def validate_image(self, value):
        return check_image_size(value)


class ProductAdminSerializer(FormCleanMixin,serializers.ModelSerializer):
    list_fields = ("uploaded_images",)
    comma_list_fields = ("color_ids",)
    category_name = serializers.CharField(source="category.name", read_only=True)
    colors = ColorSerializer(many=True, read_only=True)
    images = ProductImageAdminSerializer(many=True, read_only=True)
    # write-only inputs
    color_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)
    uploaded_images = serializers.ListField(child=serializers.ImageField(), write_only=True, required=False)

    class Meta:
        model = Product
        fields = [
            "id", "category", "category_name", "name", "slug", "description", "price",
            "is_special", "allows_custom_colors", "allows_name_text", "max_name_length",
            "lead_time_days", "is_active", "created_at", "updated_at",
            "colors", "images", "color_ids", "uploaded_images",
        ]
        read_only_fields = ["created_at", "updated_at"]
        extra_kwargs = {
            "slug": {"required": False},
            # multipart forms send nothing for an unticked/omitted boolean, and DRF would read
            # that as False. Explicit defaults keep new products active.
            "is_active": {"default": True},
            "allows_custom_colors": {"default": True},
        }

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0.")
        return value

    def validate_color_ids(self, value):
        return check_color_ids(value)

    def validate_uploaded_images(self, value):
        for f in value:
            check_image_size(f)
        return value

    def validate(self, attrs):
        allows = attrs.get("allows_name_text", getattr(self.instance, "allows_name_text", False))
        max_len = attrs.get("max_name_length", getattr(self.instance, "max_name_length", None))
        if allows and not max_len:
            raise serializers.ValidationError(
                {"max_name_length": "Required when allows_name_text is true."}
            )
        return attrs

    def create(self, validated_data):
        color_ids = validated_data.pop("color_ids", [])
        files = validated_data.pop("uploaded_images", [])
        if not validated_data.get("slug"):
            validated_data["slug"] = unique_slug(Product, validated_data["name"], 170)
        with transaction.atomic():
            product = Product.objects.create(**validated_data)
            if color_ids:
                product.colors.set(color_ids)
            for i, f in enumerate(files):
                ProductImage.objects.create(
                    product=product, image=f, is_primary=(i == 0), sort_order=i
                )
        return product

    def update(self, instance, validated_data):
        color_ids = validated_data.pop("color_ids", None)
        files = validated_data.pop("uploaded_images", [])
        with transaction.atomic():
            product = super().update(instance, validated_data)
            if color_ids is not None:
                product.colors.set(color_ids)
            if files:
                last = product.images.aggregate(m=Max("sort_order"))["m"]
                start = 0 if last is None else last + 1
                has_primary = product.images.filter(is_primary=True).exists()
                for i, f in enumerate(files):
                    ProductImage.objects.create(
                        product=product,
                        image=f,
                        is_primary=(not has_primary and i == 0),
                        sort_order=start + i,
                    )
        return product


class ProductColorsSerializer(serializers.Serializer):
    color_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)

    def validate_color_ids(self, value):
        return check_color_ids(value)


# ---------- pickup locations ----------

class PickupLocationAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = PickupLocation
        fields = ["id", "name", "area", "details", "is_active"]
# ---------- stats (response DTOs for Swagger) ----------

class StatsTotalsSerializer(serializers.Serializer):
    orders = serializers.IntegerField()
    customers = serializers.IntegerField()
    sales = serializers.CharField()
    pending_payment_reviews = serializers.IntegerField()


class StatsDailyPointSerializer(serializers.Serializer):
    date = serializers.DateField()
    orders = serializers.IntegerField()
    sales = serializers.CharField()


class StatsTopProductSerializer(serializers.Serializer):
    product_name = serializers.CharField()
    quantity = serializers.IntegerField()


class AdminStatsSerializer(serializers.Serializer):
    totals = StatsTotalsSerializer()
    orders_by_status = serializers.DictField(child=serializers.IntegerField())
    daily = StatsDailyPointSerializer(many=True)
    top_products = StatsTopProductSerializer(many=True)
