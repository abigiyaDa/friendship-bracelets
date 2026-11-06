from django.urls import path

from . import admin_views

urlpatterns = [
    path("orders/", admin_views.AdminOrderListView.as_view()),
    path("orders/<int:pk>/", admin_views.AdminOrderDetailView.as_view()),
    path("orders/<int:pk>/status/", admin_views.AdminOrderStatusView.as_view()),
    path("customers/", admin_views.AdminCustomerListView.as_view()),
    path("customers/<int:pk>/", admin_views.AdminCustomerDetailView.as_view()),
]
