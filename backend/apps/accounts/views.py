from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import (
    RegisterResponseSerializer,
    RegisterSerializer,
    UserSerializer,
    tokens_for_user,
)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    throttle_classes = ()

    @extend_schema(responses={201: RegisterResponseSerializer})
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        data = {"user": UserSerializer(user).data, **tokens_for_user(user)}
        return Response(data, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    """POST username + password → access & refresh tokens."""

    throttle_classes = ()


class RefreshView(TokenRefreshView):
    throttle_classes = ()


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user
