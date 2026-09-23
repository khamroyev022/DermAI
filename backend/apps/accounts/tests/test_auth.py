from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class AuthTests(APITestCase):
    def test_register_returns_user_and_tokens(self):
        payload = {
            "username": "alice",
            "email": "alice@example.com",
            "password": "Str0ngPassw0rd!",
            "password_confirm": "Str0ngPassw0rd!",
        }
        response = self.client.post(reverse("accounts:register"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["username"], "alice")
        self.assertTrue(User.objects.filter(username="alice").exists())

    def test_register_rejects_password_mismatch(self):
        payload = {
            "username": "bob",
            "email": "bob@example.com",
            "password": "Str0ngPassw0rd!",
            "password_confirm": "different",
        }
        response = self.client.post(reverse("accounts:register"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password_confirm", response.data)

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user(username="carol", email="carol@example.com", password="Str0ngPassw0rd!")
        payload = {
            "username": "carol2",
            "email": "Carol@example.com",
            "password": "Str0ngPassw0rd!",
            "password_confirm": "Str0ngPassw0rd!",
        }
        response = self.client.post(reverse("accounts:register"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_login_refresh_and_me(self):
        User.objects.create_user(username="dave", email="dave@example.com", password="Str0ngPassw0rd!")
        response = self.client.post(
            reverse("accounts:login"), {"username": "dave", "password": "Str0ngPassw0rd!"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        access, refresh = response.data["access"], response.data["refresh"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        me = self.client.get(reverse("accounts:me"))
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data["email"], "dave@example.com")

        self.client.credentials()
        refreshed = self.client.post(reverse("accounts:token_refresh"), {"refresh": refresh}, format="json")
        self.assertEqual(refreshed.status_code, status.HTTP_200_OK)
        self.assertIn("access", refreshed.data)

    def test_login_with_wrong_password_fails(self):
        User.objects.create_user(username="erin", email="erin@example.com", password="Str0ngPassw0rd!")
        response = self.client.post(reverse("accounts:login"), {"username": "erin", "password": "nope"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_requires_authentication(self):
        response = self.client.get(reverse("accounts:me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
