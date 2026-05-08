from __future__ import annotations

from rest_framework.test import APITestCase

from .models import Kink, Message, User


class HoneybeeApiTests(APITestCase):
    def setUp(self) -> None:
        self.kink = Kink.objects.create(name="Rope")
        self.user = self._create_user(
            username="alex",
            email="alex@example.com",
            sex=User.Sex.MALE,
            orientation=User.Orientation.STRAIGHT,
            dominance=[User.Dominance.DOMINANT],
            match_dominance_preferences=[User.Dominance.SUBMISSIVE],
            messaging_external_id="external-alex",
        )
        self.candidate = self._create_user(
            username="sam",
            email="sam@example.com",
            sex=User.Sex.FEMALE,
            orientation=User.Orientation.STRAIGHT,
            dominance=[User.Dominance.SUBMISSIVE],
            messaging_external_id="external-sam",
        )
        self.user.kinks.add(self.kink)
        self.candidate.kinks.add(self.kink)

    def test_recommendations_include_compatible_verified_users(self) -> None:
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/recommendations/?limit=5")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["user"]["id"], self.candidate.id)
        self.assertGreater(response.data[0]["score"], 0)
        self.assertEqual(response.data[0]["shared_kinks"], ["Rope"])

    def test_messaging_webhook_creates_inbound_message(self) -> None:
        payload = {
            "event_id": "evt-1",
            "event_type": "message.received",
            "provider": "generic",
            "from": "external-sam",
            "to": "external-alex",
            "body": "hello",
        }

        response = self.client.post("/api/webhooks/messaging/", payload, format="json")

        self.assertEqual(response.status_code, 202)
        self.assertEqual(Message.objects.count(), 1)
        message = Message.objects.get()
        self.assertEqual(message.sender, self.candidate)
        self.assertEqual(message.recipient, self.user)
        self.assertEqual(message.direction, Message.Direction.INBOUND)

    def _create_user(
        self,
        *,
        username: str,
        email: str,
        sex: str,
        orientation: str,
        dominance: list[str],
        match_dominance_preferences: list[str] | None = None,
        messaging_external_id: str,
    ) -> User:
        user = User.objects.create_user(
            username=username,
            email=email,
            password="strong-test-password",
            first_name=username.title(),
            phone="+10000000000",
            country=User.CountryCode.US_1,
            sex=sex,
            orientation=orientation,
            dominance=dominance,
            match_dominance_preferences=match_dominance_preferences or [],
            messaging_external_id=messaging_external_id,
            is_verified=True,
        )
        return user
