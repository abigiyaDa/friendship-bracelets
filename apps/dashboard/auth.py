from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, serializers
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

User = get_user_model()


class AdminTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        if not self.user.is_staff:
            # same error as a wrong password, so nothing leaks
            raise exceptions.AuthenticationFailed(
                self.error_messages["no_active_account"], "no_active_account"
            )
        data["user"] = {
            "id": self.user.id,
            "username": self.user.get_username(),
            "email": self.user.email,
        }
        return data


class AdminLoginView(TokenObtainPairView):
    serializer_class = AdminTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "admin_login"


class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "is_staff", "is_superuser"]


class AdminMeView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(responses=AdminUserSerializer)
    def get(self, request):
        return Response(AdminUserSerializer(request.user).data)