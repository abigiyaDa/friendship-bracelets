from rest_framework import generics

from .models import PickupLocation
from .serializers import PickupLocationSerializer


class PickupLocationListView(generics.ListAPIView):
    """Public, read-only list of active pickup locations."""
    pagination_class = None

    serializer_class = PickupLocationSerializer

    def get_queryset(self):
        return PickupLocation.objects.filter(is_active=True).order_by("area", "name")