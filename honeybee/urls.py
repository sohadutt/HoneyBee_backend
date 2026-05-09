from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ConversationViewSet,
    GoogleLoginView,
    LoginView,
    MatchViewSet,
    RefreshTokenView,
    UserViewSet,
    available_kinks,
    logout,
    messaging_webhook,
    recommendations,
    request_otp,
    verify_otp,
)

# Initialize the default router for ViewSets
router = DefaultRouter()

# User Routes:
# - POST /users/ (Registration)
# - GET/PATCH /users/me/ (Profile)
# - GET/POST/PUT/DELETE /users/me/pictures/
router.register(r"users", UserViewSet, basename="user")
router.register(r"matches", MatchViewSet, basename="match")
router.register(r"conversations", ConversationViewSet, basename="conversation")

urlpatterns = [
    # API ViewSets
    path("", include(router.urls)),

    # Authentication & Session Management
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/google/", GoogleLoginView.as_view(), name="auth-google"),
    path("auth/refresh/", RefreshTokenView.as_view(), name="auth-refresh"),
    path("auth/logout/", logout, name="auth-logout"),

    # OTP Verification Flows
    path("auth/otp/request/", request_otp, name="auth-otp-request"),
    path("auth/otp/verify/", verify_otp, name="auth-otp-verify"),

    # Application Features & Data
    path("recommendations/", recommendations, name="recommendations"),
    path("kinks/available/", available_kinks, name="available-kinks"),

    # Webhooks
    path("webhooks/messaging/", messaging_webhook, name="messaging-webhook"),
]