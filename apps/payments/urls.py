from django.urls import path

from . import views

urlpatterns = [
    path("orders/<str:order_number>/payments/", views.PaymentCreateView.as_view()),
]