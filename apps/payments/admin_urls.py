from django.urls import path

from . import admin_views

urlpatterns = [
    path("payments/", admin_views.AdminPaymentListView.as_view()),
    path("payments/<int:pk>/approve/", admin_views.AdminPaymentApproveView.as_view()),
    path("payments/<int:pk>/reject/", admin_views.AdminPaymentRejectView.as_view()),
]
