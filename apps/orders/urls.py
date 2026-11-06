from django.urls import path

from apps.orders import order_lookup

from . import order_detail, views

urlpatterns = [
    path("orders/", views.OrderCreateView.as_view()),
    path("orders/lookup/", order_lookup.OrderLookupView.as_view()),
    path("orders/<str:order_number>/", order_detail.OrderDetailView.as_view()),
]
