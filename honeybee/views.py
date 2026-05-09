from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import random
import secrets
import time
from typing import Any, cast

from celery.result import AsyncResult
from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import Count, QuerySet
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

# Import the new PREDEFINED_KINKS dictionary
from .obj import PREDEFINED_KINKS
from .models import Conversation, Match, Message, MessagingWebhookEvent, User
from .serializers import (
    ConversationSerializer,
    EmailLoginSerializer,
    GoogleLoginSerializer,
    MatchSerializer,
    MessagingWebhookEventSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    OutboundMessageSerializer,
    RecommendationSerializer,
    UserCreateSerializer,
    UserSerializer,
)
from .services import Recommendation, recommend_users
from .tasks import ProfilePictureUpload, process_profile_pictures_task, send_otp_email_task

logger = logging.getLogger(__name__)

MAX_PROFILE_PICTURES = 6
OTP_TIMEOUT_SECONDS = 180


@api_view(["GET"])
@permission_classes([AllowAny])
def available_kinks(request: Request) -> Response:
    """
    Returns the predefined dictionary of kinks.
    Formatted as a list of objects for easy frontend rendering.
    """
    formatted_kinks = [
        {
            "id": key, 
            "name": key.replace("_", " ").title(), 
            "description": description
        }
        for key, description in PREDEFINED_KINKS.items()
    ]
    return Response(formatted_kinks)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = EmailLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return Response(_auth_payload(user, "Login successful."))


class RefreshTokenView(TokenRefreshView):
    permission_classes = [AllowAny]


class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(_auth_payload(user, "Google login successful."))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request: Request) -> Response:
    refresh_token = request.data.get("refresh")
    if not refresh_token:
        return Response(status=status.HTTP_204_NO_CONTENT)

    try:
        token = RefreshToken(str(refresh_token))
        token.blacklist()
    except AttributeError:
        # If the blacklist app is not installed
        return Response(status=status.HTTP_204_NO_CONTENT)
    except TokenError:
        return Response({"detail": "Invalid refresh token."}, status=status.HTTP_400_BAD_REQUEST)

    return Response(status=status.HTTP_204_NO_CONTENT)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self) -> type[UserSerializer] | type[UserCreateSerializer]:
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def get_permissions(self) -> list[BasePermission]:
        if self.action == "create":
            return [AllowAny()]
        return super().get_permissions()

    @transaction.atomic
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Overridden to handle User creation and immediate OTP dispatch."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        otp_sent = _send_otp(user.email)
        detail = "User created. Verification code sent." if otp_sent else "User created. Verification email is unavailable."
        
        return Response(
            {"detail": detail, "user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get", "patch"], permission_classes=[IsAuthenticated])
    def me(self, request: Request) -> Response:
        user = cast(User, request.user)
        if request.method == "GET":
            return Response(UserSerializer(user).data)

        serializer = UserSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get", "post", "put", "delete"],
        permission_classes=[IsAuthenticated],
        parser_classes=[MultiPartParser, FormParser],
        url_path="me/pictures",
    )
    @transaction.atomic
    def pictures(self, request: Request) -> Response:
        user = cast(User, request.user)

        if request.method == "GET":
            return Response(_profile_picture_payload(user))

        if request.method == "DELETE":
            return _delete_profile_picture(user, request)

        uploaded_files = _uploaded_picture_files(request)
        if not uploaded_files:
            return Response({"detail": "Upload at least one picture."}, status=status.HTTP_400_BAD_REQUEST)

        replaces_existing = request.method == "PUT"
        current_count = 0 if replaces_existing else len(user.highres_pictures_urls)
        
        if current_count + len(uploaded_files) > MAX_PROFILE_PICTURES:
            return Response(
                {"detail": f"Profiles can have at most {MAX_PROFILE_PICTURES} pictures."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            task_uploads = [_picture_upload_payload(uploaded_file) for uploaded_file in uploaded_files]
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        task = process_profile_pictures_task.delay(user.id, task_uploads, replaces_existing)

        return Response(
            {
                "detail": "Profile picture processing started.",
                "task_id": task.id,
                "status_url": request.build_absolute_uri(f"status/{task.id}/"),
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path=r"me/pictures/status/(?P<task_id>[^/.]+)",
    )
    def picture_status(self, request: Request, task_id: str) -> Response:
        task = AsyncResult(task_id)
        payload: dict[str, Any] = {"task_id": task_id, "state": task.state}
        if task.successful():
            payload["result"] = task.result
        elif task.failed():
            payload["detail"] = str(task.result)
        return Response(payload)


class MatchViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MatchSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[Match]:
        return (
            Match.objects.filter(owner=self.request.user)
            .select_related("matched_user")
        )


class ConversationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[Conversation]:
        return (
            Conversation.objects.filter(participants=self.request.user)
            .prefetch_related("participants", "messages")
            .distinct()
        )

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated])
    @transaction.atomic
    def send(self, request: Request) -> Response:
        serializer = OutboundMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sender = cast(User, request.user)
        recipient = cast(User, serializer.validated_data["recipient"])
        
        conversation = _get_or_create_conversation(sender, recipient)
        message = Message.objects.create(
            conversation=conversation,
            sender=sender,
            recipient=recipient,
            direction=Message.Direction.OUTBOUND,
            body=serializer.validated_data["body"],
        )
        conversation.save(update_fields=["updated_at"])
        
        return Response(
            ConversationSerializer(conversation).data | {"message_id": message.id}, 
            status=status.HTTP_201_CREATED
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def recommendations(request: Request) -> Response:
    user = cast(User, request.user)
    limit = min(int(request.query_params.get("limit", 20)), 50)
    items = recommend_users(user=user, limit=limit)

    if request.query_params.get("save_matches") == "true":
        _save_recommendations_as_matches(user, items)

    return Response(RecommendationSerializer(items, many=True).data)


@api_view(["POST"])
@permission_classes([AllowAny])
def messaging_webhook(request: Request) -> Response:
    if not _valid_webhook_signature(request):
        logger.warning("Rejected webhook event due to invalid signature.")
        return Response({"detail": "Invalid webhook signature."}, status=status.HTTP_401_UNAUTHORIZED)

    payload = cast(dict[str, Any], request.data)
    event_id = str(payload.get("event_id") or payload.get("id") or "")
    event_type = str(payload.get("event_type") or payload.get("type") or "message.received")
    provider = str(payload.get("provider") or "generic")

    if not event_id:
        payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        event_id = f"{provider}:{payload_hash}"

    event, created = MessagingWebhookEvent.objects.get_or_create(
        event_id=event_id,
        defaults={"event_type": event_type, "provider": provider, "payload": payload},
    )
    if not created:
        return Response({"detail": "Event already processed."}, status=status.HTTP_200_OK)

    _process_message_event(event)
    return Response(MessagingWebhookEventSerializer(event).data, status=status.HTTP_202_ACCEPTED)


# ==========================================
# UTILITY FUNCTIONS
# ==========================================

def _get_or_create_conversation(user: User, recipient: User) -> Conversation:
    """
    Ensures a 1-on-1 conversation exists. Uses annotation to strictly find 
    conversations with exactly 2 participants to avoid fetching group chats.
    """
    conversation = (
        Conversation.objects.annotate(p_count=Count("participants"))
        .filter(participants=user)
        .filter(participants=recipient)
        .filter(p_count=2)
        .first()
    )
    
    if conversation is not None:
        return conversation

    conversation = Conversation.objects.create()
    conversation.participants.set([user, recipient])
    return conversation


def _save_recommendations_as_matches(user: User, items: list[Recommendation]) -> None:
    for item in items:
        Match.objects.update_or_create(
            owner=user,
            matched_user=item.user,
            defaults={
                "score": item.score, 
                "kinks_in_common_count": len(item.shared_kinks),
                "kinks_in_common": item.shared_kinks,  # Directly assign the list now
            },
        )


def _valid_webhook_signature(request: Request) -> bool:
    secret = getattr(settings, "MESSAGING_WEBHOOK_SECRET", "")
    if not secret:
        return True

    signature = request.headers.get("X-Honeybee-Signature", "")
    
    # Ensure request.body is read securely (DRF sometimes clears the stream depending on the parser)
    body = request.body if hasattr(request, "body") else b""
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    expected = f"sha256={digest}"
    
    return hmac.compare_digest(signature, expected)


def _process_message_event(event: MessagingWebhookEvent) -> None:
    payload = cast(dict[str, Any], event.payload)
    if event.event_type not in {"message.received", "message.created", "message.inbound"}:
        event.processed_at = timezone.now()
        event.save(update_fields=["processed_at"])
        return

    sender_external_id = str(payload.get("sender_external_id") or payload.get("from") or "")
    recipient_external_id = str(payload.get("recipient_external_id") or payload.get("to") or "")
    body = str(payload.get("body") or payload.get("text") or "")
    
    if not sender_external_id or not recipient_external_id or not body:
        event.processed_at = timezone.now()
        event.save(update_fields=["processed_at"])
        return

    sender = User.objects.filter(messaging_external_id=sender_external_id).first()
    recipient = User.objects.filter(messaging_external_id=recipient_external_id).first()
    
    if recipient is None:
        logger.warning(f"Webhook Message Error: Recipient {recipient_external_id} not found.")
        event.processed_at = timezone.now()
        event.save(update_fields=["processed_at"])
        return

    conversation = _get_or_create_conversation(recipient, sender) if sender else Conversation.objects.create()
    if sender is None:
        conversation.participants.add(recipient)

    Message.objects.create(
        conversation=conversation,
        sender=sender,
        recipient=recipient,
        direction=Message.Direction.INBOUND,
        body=body,
        provider_message_id=str(payload.get("message_id") or payload.get("provider_message_id") or event.event_id),
    )
    
    conversation.save(update_fields=["updated_at"])
    event.processed_at = timezone.now()
    event.save(update_fields=["processed_at"])


def _uploaded_picture_files(request: Request) -> list[UploadedFile]:
    files = [*request.FILES.getlist("pictures")]
    single_file = request.FILES.get("picture")
    if single_file is not None:
        files.append(single_file)
    return files


def _picture_upload_payload(uploaded_file: UploadedFile) -> ProfilePictureUpload:
    content_type = str(getattr(uploaded_file, "content_type", ""))
    if not content_type.startswith("image/"):
        raise ValueError("Only image uploads are supported.")
    return {
        "data": base64.b64encode(uploaded_file.read()).decode("ascii"),
        "content_type": content_type,
        "filename": uploaded_file.name,
    }


def _profile_picture_payload(user: User) -> dict[str, list[str]]:
    return {
        "blurred_pictures_urls": user.lowres_pictures_urls,
        "highres_pictures_urls": user.highres_pictures_urls,
    }


def _delete_profile_picture(user: User, request: Request) -> Response:
    raw_index = request.data.get("index")
    highres_url = str(request.data.get("highres_url") or "")
    blurred_url = str(request.data.get("blurred_url") or "")

    index = _profile_picture_index(user, raw_index, highres_url, blurred_url)
    if index is None:
        return Response({"detail": "Picture not found."}, status=status.HTTP_404_NOT_FOUND)

    user.lowres_pictures_urls = [
        url for position, url in enumerate(user.lowres_pictures_urls) if position != index
    ]
    user.highres_pictures_urls = [
        url for position, url in enumerate(user.highres_pictures_urls) if position != index
    ]
    user.save(update_fields=["lowres_pictures_urls", "highres_pictures_urls", "updated_at"])
    return Response(_profile_picture_payload(user))


def _profile_picture_index(
    user: User,
    raw_index: Any,
    highres_url: str,
    blurred_url: str,
) -> int | None:
    if raw_index not in {None, ""}:
        try:
            index = int(str(raw_index))
        except ValueError:
            return None
        if 0 <= index < len(user.highres_pictures_urls):
            return index
        return None

    if highres_url and highres_url in user.highres_pictures_urls:
        return user.highres_pictures_urls.index(highres_url)
    if blurred_url and blurred_url in user.lowres_pictures_urls:
        return user.lowres_pictures_urls.index(blurred_url)
    return None


@api_view(["POST"])
@permission_classes([AllowAny])
def request_otp(request: Request) -> Response:
    serializer = OTPRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = str(serializer.validated_data["email"]).strip().lower()
    user = User.objects.filter(email=email).first()

    if user is None:
        time.sleep(random.uniform(0.1, 0.3))
        return Response({"detail": "If an account exists, a verification code will be sent."})

    _send_otp(email)
    return Response({"detail": "If an account exists, a verification code will be sent."})


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_otp(request: Request) -> Response:
    serializer = OTPVerifySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = str(serializer.validated_data["email"]).strip().lower()
    otp = str(serializer.validated_data["otp"])

    if cache.get(_otp_cache_key(email)) != otp:
        return Response({"detail": "Invalid or expired verification code."}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.filter(email=email).first()
    if user is None:
        return Response({"detail": "Invalid or expired verification code."}, status=status.HTTP_400_BAD_REQUEST)

    if not user.is_verified:
        user.is_verified = True
        user.save(update_fields=["is_verified", "updated_at"])

    cache.delete(_otp_cache_key(email))
    return Response(_auth_payload(user, "Verification successful."))


def _send_otp(email: str) -> bool:
    otp = "".join(secrets.choice("0123456789") for _ in range(6))
    cache.set(_otp_cache_key(email), otp, timeout=OTP_TIMEOUT_SECONDS)
    try:
        send_otp_email_task.delay(email, otp)
    except Exception as e:
        logger.error(f"Failed to queue OTP email for {email}: {e}")
        cache.delete(_otp_cache_key(email))
        return False
    return True


def _otp_cache_key(email: str) -> str:
    return f"auth-otp:{email}"


def _auth_payload(user: User, detail: str) -> dict[str, Any]:
    refresh = RefreshToken.for_user(user)
    return {
        "detail": detail,
        "user": UserSerializer(user).data,
        "tokens": {"refresh": str(refresh), "access": str(refresh.access_token)},
    }