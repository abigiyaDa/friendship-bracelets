from django.urls import path

from . import views

urlpatterns = [
    path("pickup-locations/", views.PickupLocationListView.as_view()),
]