from django.urls import path

from . import order_detail

urlpatterns = [
    #adds: path("orders/", views.OrderCreateView.as_view()),
    path("orders/<str:order_number>/", order_detail.OrderDetailView.as_view()),
]