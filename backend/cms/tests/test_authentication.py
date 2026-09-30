# designed by mew
"""Real proxy identity and login throttling must remain independent per client."""

import json
from datetime import timedelta

from axes.helpers import get_client_ip_address
from axes.models import AccessAttempt
from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils import timezone


@override_settings(DEBUG=False)
class ClientAddressTests(SimpleTestCase):
    def address(self, peer, forwarded=None):
        request = RequestFactory().post(
            "/api/editor/login/", REMOTE_ADDR=peer, HTTP_X_FORWARDED_FOR=forwarded
        )
        # Exercise Axes' configured callback, including string import resolution.
        return get_client_ip_address(request)

    def test_production_loopback_accepts_single_ipv4_or_ipv6_client(self):
        self.assertEqual(self.address("127.0.0.1", "198.51.100.10"), "198.51.100.10")
        self.assertEqual(self.address("::1", "2001:db8::10"), "2001:db8::10")
        self.assertEqual(self.address("127.0.0.1", "198.51.100.11"), "198.51.100.11")

    def test_non_loopback_peer_cannot_spoof_forwarded_identity(self):
        self.assertEqual(self.address("198.51.100.10", "203.0.113.20"), "198.51.100.10")
        self.assertEqual(self.address("10.0.0.2", "203.0.113.20"), "10.0.0.2")

    def test_invalid_or_multiple_forwarded_addresses_fall_back_to_peer(self):
        for value in (
            None,
            "",
            "198.51.100.10, 203.0.113.20",
            "198.51.100.10:443",
            "198.51.100.999",
            " 198.51.100.10",
            "fe80::1%eth0",
            "unknown",
        ):
            with self.subTest(value=value):
                self.assertEqual(self.address("127.0.0.1", value), "127.0.0.1")

    @override_settings(DEBUG=True)
    def test_development_ignores_forwarding_headers(self):
        self.assertEqual(self.address("127.0.0.1", "198.51.100.10"), "127.0.0.1")

    def test_invalid_peer_does_not_make_forwarding_header_trusted(self):
        self.assertIsNone(self.address("invalid-peer", "198.51.100.10"))
        self.assertIsNone(self.address(None, "198.51.100.10"))


@override_settings(
    DEBUG=False,
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class LoginThrottleTests(TestCase):
    password = "Valid-Test-Password-728!"

    @classmethod
    def setUpTestData(cls):
        for username in ("first-editor", "second-editor"):
            get_user_model().objects.create_user(username, password=cls.password, is_staff=True)

    def login(self, username="first-editor", ip="198.51.100.10", password="incorrect"):
        return self.client.post(
            "/api/editor/login/",
            json.dumps({"username": username, "password": password}),
            content_type="application/json",
            secure=True,
            REMOTE_ADDR="127.0.0.1",
            HTTP_X_FORWARDED_FOR=ip,
        )

    def fail_five_times(self):
        for _ in range(4):
            self.assertEqual(self.login().status_code, 400)
        self.assertEqual(self.login().status_code, 429)

    def test_account_and_ip_lock_independently_without_locking_other_clients(self):
        self.fail_five_times()
        self.assertEqual(AccessAttempt.objects.get().ip_address, "198.51.100.10")
        self.assertEqual(self.login(ip="198.51.100.11", password=self.password).status_code, 429)
        self.assertEqual(
            self.login(username="second-editor", password=self.password).status_code, 429
        )
        self.assertEqual(
            self.login(
                username="second-editor", ip="198.51.100.11", password=self.password
            ).status_code,
            200,
        )
        self.assertFalse(AccessAttempt.objects.filter(ip_address="127.0.0.1").exists())

    def test_successful_login_clears_previous_failures(self):
        self.login()
        self.login()
        self.assertEqual(AccessAttempt.objects.get().failures_since_start, 2)
        self.assertEqual(self.login(password=self.password).status_code, 200)
        self.assertFalse(AccessAttempt.objects.exists())

    def test_lock_expires_after_fifteen_minutes(self):
        self.fail_five_times()
        AccessAttempt.objects.update(attempt_time=timezone.now() - timedelta(minutes=14))
        self.assertEqual(self.login(password=self.password).status_code, 429)
        AccessAttempt.objects.update(attempt_time=timezone.now() - timedelta(minutes=16))
        self.assertEqual(self.login(password=self.password).status_code, 200)
        self.assertFalse(AccessAttempt.objects.exists())
