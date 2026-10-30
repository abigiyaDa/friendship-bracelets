from django.contrib import admin

# Register your models here.
from .models import PickupLocation


@admin.register(PickupLocation)
class PickupLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "area", "is_active")
    list_filter = ("is_active",)
