from django.db import models

# Create your models here.
# PickupLocation


class PickupLocation(models.Model):
    name = models.CharField(max_length=100)
    area = models.CharField(max_length=100)
    details = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.area})"