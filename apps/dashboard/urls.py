from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views
from .auth import AdminLoginView, AdminMeView

urlpatterns = [
    # auth
    path("auth/login/", AdminLoginView.as_view()),
    path("auth/refresh/", TokenRefreshView.as_view()),
    path("auth/me/", AdminMeView.as_view()),
    # categories
    path("categories/", views.CategoryListCreateView.as_view()),
    path("categories/<int:pk>/", views.CategoryDetailView.as_view()),
    # colors
    path("colors/", views.ColorListCreateView.as_view()),
    path("colors/<int:pk>/", views.ColorDetailView.as_view()),
    # products
    path("products/", views.ProductListCreateView.as_view()),
    path("products/<int:pk>/", views.ProductDetailView.as_view()),
    path("products/<int:product_id>/images/", views.ProductImageCreateView.as_view()),
    path("products/<int:product_id>/images/<int:image_id>/", views.ProductImageDetailView.as_view()),
    path("products/<int:product_id>/colors/", views.ProductColorsView.as_view()),
    # pickup locations
    path("pickup-locations/", views.PickupLocationListCreateView.as_view()),
    path("pickup-locations/<int:pk>/", views.PickupLocationDetailView.as_view()),
]