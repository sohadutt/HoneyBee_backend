from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ConversationViewSet,
    KinkViewSet,
    LoginView,
    MatchViewSet,
    RefreshTokenView,
    UserViewSet,
    create_user,
    get_user_profile,
    logout,
    messaging_webhook,
    recommendations,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("kinks", KinkViewSet, basename="kink")
router.register("matches", MatchViewSet, basename="match")
router.register("conversations", ConversationViewSet, basename="conversation")

urlpatterns = [
    path("", include(router.urls)),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/refresh/", RefreshTokenView.as_view(), name="auth-refresh"),
    path("auth/logout/", logout, name="auth-logout"),
    path("auth/register/", create_user, name="auth-register"),
    path("profile/", get_user_profile, name="profile"),
    path("recommendations/", recommendations, name="recommendations"),
    path("webhooks/messaging/", messaging_webhook, name="messaging-webhook"),
]
