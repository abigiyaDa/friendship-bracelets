from rest_framework import serializers

from .models import Category, Color, Product, ProductImage
from drf_spectacular.utils import extend_schema_field #


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "image"]


class CategoryBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class ColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Color
        fields = ["id", "name", "hex_code"]


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "is_primary"]


class ProductListSerializer(serializers.ModelSerializer):
    category = CategoryBriefSerializer(read_only=True)
    colors = ColorSerializer(many=True, read_only=True)
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "name", "slug", "price", "category",
            "is_special", "allows_custom_colors", "allows_name_text",
            "max_name_length", "lead_time_days",
            "primary_image", "colors",
        ]
    # the deocator helps the swagger identify what type the primary_image is 
    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_primary_image(self, obj):
        images = list(obj.images.all())
        if not images:
            return None
        primary = next((img for img in images if img.is_primary), images[0])
        request = self.context.get("request")
        url = primary.image.url
        return request.build_absolute_uri(url) if request else url


class ProductDetailSerializer(ProductListSerializer):
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + ["description", "images"]