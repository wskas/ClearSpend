import os
import re
import time
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

import jwt
import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache, caches
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from .constants import SUPPORTED_CURRENCIES
from .models import Category, ExchangeRate, Subscription
from .views import get_exchange_rate

User = get_user_model()

# Long enough to clear the password validators, obviously not a real secret.
PASSWORD = 'clearspend-test-pw-9182'
 
 
class GetExchangeRateTests(TestCase):
    """
    Rates are only ever stored against USD (see fetch_exchange_rates), so
    resolution has to cope with pairs that are never on file directly.
    """
 
    @classmethod
    def setUpTestData(cls):
        ExchangeRate.objects.create(currency_pair='USD_EUR', rate=Decimal('0.850000'))
        ExchangeRate.objects.create(currency_pair='USD_GBP', rate=Decimal('0.750000'))
 
    def test_identity_pair_is_one(self):
        self.assertEqual(get_exchange_rate('EUR', 'EUR'), Decimal('1'))
 
    def test_direct_pair(self):
        self.assertEqual(get_exchange_rate('USD', 'EUR'), Decimal('0.850000'))
 
    def test_inverse_pair(self):
        # 1 / 0.85
        self.assertEqual(get_exchange_rate('EUR', 'USD'), Decimal('1.176471'))
 
    def test_cross_rate_is_triangulated_through_usd(self):
        # EUR -> GBP is stored in neither direction: 0.75 / 0.85
        self.assertEqual(get_exchange_rate('EUR', 'GBP'), Decimal('0.882353'))
 
    def test_cross_rate_is_symmetric(self):
        # 0.85 / 0.75
        self.assertEqual(get_exchange_rate('GBP', 'EUR'), Decimal('1.133333'))
 
    def test_missing_leg_still_raises(self):
        # No USD_JPY on file, so the pivot cannot close the loop.
        with self.assertRaises(ValueError):
            get_exchange_rate('JPY', 'EUR')
 
    def test_zero_rate_does_not_divide_by_zero(self):
        ExchangeRate.objects.create(currency_pair='USD_CAD', rate=Decimal('0'))
        with self.assertRaises(ValueError):
            get_exchange_rate('CAD', 'EUR')
 
 
class ProjectionsCrossCurrencyTests(TestCase):
    """
    Regression: a non-USD user with a subscription in a third currency used
    to be dropped from projections entirely and reported as a warning.
    """
 
    def setUp(self):
        ExchangeRate.objects.create(currency_pair='USD_EUR', rate=Decimal('0.850000'))
        ExchangeRate.objects.create(currency_pair='USD_GBP', rate=Decimal('0.750000'))
        self.user = User.objects.create_user(
            username='gbpuser', email='gbp@example.com', password='pw-for-tests-123',
        )
        self.user.base_currency = 'GBP'
        self.user.save(update_fields=['base_currency'])
        Subscription.objects.create(
            user=self.user, name='Euro SaaS', amount=Decimal('100.00'),
            original_currency='EUR', billing_cycle='monthly',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
 
    def test_eur_subscription_is_converted_not_skipped(self):
        res = self.client.get(reverse('projections'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['warnings'], [])
        # 100 EUR * (0.75 / 0.85) = 88.24 GBP
        self.assertEqual(res.data['monthly_total'], '88.24')
        self.assertEqual(len(res.data['line_items']), 1)
 
    def test_unsynced_currency_is_still_warned_about(self):
        Subscription.objects.create(
            user=self.user, name='Yen SaaS', amount=Decimal('500.00'),
            original_currency='JPY', billing_cycle='monthly',
        )
        res = self.client.get(reverse('projections'))
        self.assertEqual(res.data['warnings'], ['Missing exchange rate for JPY'])
 
 
class CurrenciesEndpointTests(TestCase):
 
    def test_public_and_matches_the_canonical_list(self):
        # Unauthenticated: the register form needs this before signup.
        res = APIClient().get(reverse('currencies'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['currencies'], SUPPORTED_CURRENCIES)
        self.assertEqual(res.data['base_currency'], 'USD')

    def test_client_ip_diagnostic_is_off_by_default(self):
        with self.assertNoLogs('clearspend.security', level='INFO'):
            APIClient().get(reverse('currencies'))

    @override_settings(LOG_CLIENT_IP_HEADERS=True)
    def test_client_ip_diagnostic_logs_forwarding_headers(self):
        with self.assertLogs('clearspend.security', level='INFO') as logs:
            APIClient().get(
                reverse('currencies'),
                HTTP_X_FORWARDED_FOR='203.0.113.7, 10.0.0.1',
                HTTP_CF_CONNECTING_IP='203.0.113.7',
                HTTP_USER_AGENT='not-logged',
            )
        line = logs.output[0]
        self.assertIn('throttle_ident=', line)
        self.assertIn("'HTTP_X_FORWARDED_FOR': '203.0.113.7, 10.0.0.1'", line)
        self.assertIn("'HTTP_CF_CONNECTING_IP': '203.0.113.7'", line)
        self.assertNotIn('not-logged', line)


# ===========================================================================
# Security regression suite (see SECURITY_AUDIT_REVIEW.md)
#
# One test per corrected finding. These exist to stop a fix silently
# reverting to the broken behaviour it replaced -- several of the original
# controls failed *closed-looking but open*, which is exactly the class of
# bug a test catches and a code review does not.
# ===========================================================================


class AuthTestMixin:
    """
    Login is rate-limited per IP and failures are counted per account. Those
    live in *different* cache aliases -- throttle counters in `default`,
    lockout counters in the dedicated `lockout` alias (views.py) -- and both
    persist for the life of the test process.

    Every alias has to be reset, not just `default`. Clearing only `default`
    leaves lockout counters accumulating across tests, so a class whose tests
    each register a few failures against the same address eventually locks
    that account out and a later test's *valid* login gets a 429.
    """

    def _clear_caches(self):
        for alias in settings.CACHES:
            caches[alias].clear()

    def setUp(self):
        super().setUp()
        self._clear_caches()
        self.addCleanup(self._clear_caches)

    def make_user(self, email='user@example.com', password=PASSWORD, **extra):
        return User.objects.create_user(
            username=email.split('@')[0], email=email, password=password, **extra
        )

    def login(self, email='user@example.com', password=PASSWORD):
        res = APIClient().post(
            reverse('token_obtain_pair'), {'email': email, 'password': password}
        )
        self.assertEqual(res.status_code, 200, res.data)
        return res.data


class TenantIsolationTests(AuthTestMixin, TestCase):
    """
    Every viewset filters by request.user. These are the tests that keep it
    that way -- the audit verified the scoping by reading it, which does not
    survive the next refactor.
    """

    def setUp(self):
        super().setUp()
        self.alice = self.make_user('alice@example.com')
        self.bob = self.make_user('bob@example.com')

        self.bob_category = Category.objects.create(
            user=self.bob, name='Bob Media', hex_color_code='#123456'
        )
        self.bob_sub = Subscription.objects.create(
            user=self.bob, name='Bob Netflix', amount=Decimal('10.00'),
            original_currency='USD', billing_cycle='monthly',
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.alice)

    def test_list_excludes_other_users_subscriptions(self):
        res = self.client.get(reverse('subscription-list'))
        self.assertEqual(res.status_code, 200)
        ids = [row['id'] for row in res.data['results']]
        self.assertNotIn(self.bob_sub.id, ids)

    def test_cannot_read_another_users_subscription(self):
        res = self.client.get(reverse('subscription-detail', args=[self.bob_sub.id]))
        self.assertEqual(res.status_code, 404)

    def test_cannot_update_another_users_subscription(self):
        res = self.client.patch(
            reverse('subscription-detail', args=[self.bob_sub.id]), {'name': 'Hijacked'}
        )
        self.assertEqual(res.status_code, 404)
        self.bob_sub.refresh_from_db()
        self.assertEqual(self.bob_sub.name, 'Bob Netflix')

    def test_cannot_soft_delete_another_users_subscription(self):
        res = self.client.delete(reverse('subscription-detail', args=[self.bob_sub.id]))
        self.assertEqual(res.status_code, 404)
        self.bob_sub.refresh_from_db()
        self.assertTrue(self.bob_sub.is_active)

    def test_cannot_read_another_users_category(self):
        res = self.client.get(reverse('category-detail', args=[self.bob_category.id]))
        self.assertEqual(res.status_code, 404)

    def test_cannot_assign_another_users_category(self):
        """The re-scoped dropdown queryset in SubscriptionSerializer.__init__."""
        res = self.client.post(reverse('subscription-list'), {
            'name': 'Mine', 'amount': '5.00', 'original_currency': 'USD',
            'billing_cycle': 'monthly', 'category': self.bob_category.id,
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn('category', res.data)

    def test_projections_only_counts_own_subscriptions(self):
        ExchangeRate.objects.create(currency_pair='USD_EUR', rate=Decimal('0.850000'))
        Subscription.objects.create(
            user=self.alice, name='Alice Only', amount=Decimal('7.00'),
            original_currency='USD', billing_cycle='monthly',
        )
        res = self.client.get(reverse('projections'))
        self.assertEqual(res.data['monthly_total'], '7.00')


class RefreshTokenRevocationTests(AuthTestMixin, TestCase):
    """H1: the blacklist is only real once token_blacklist is installed."""

    def setUp(self):
        super().setUp()
        self.user = self.make_user()

    @override_settings(REFRESH_REUSE_GRACE_SECONDS=0)
    def test_reused_refresh_token_is_rejected(self):
        tokens = self.login()
        first = tokens['refresh']

        rotated = APIClient().post(reverse('token_refresh'), {'refresh': first})
        self.assertEqual(rotated.status_code, 200)
        self.assertNotEqual(rotated.data['refresh'], first)

        replayed = APIClient().post(reverse('token_refresh'), {'refresh': first})
        self.assertEqual(replayed.status_code, 401)

    @override_settings(REFRESH_REUSE_GRACE_SECONDS=10)
    def test_simultaneous_refresh_from_two_tabs_keeps_both_logged_in(self):
        """
        The multi-tab regression that turning the blacklist on introduces.

        Two tabs share one refresh token via localStorage. Both present it.
        Without the grace window the loser gets a blacklisted-token error,
        and because the frontend clears shared localStorage on a failed
        refresh, that logs the winning tab out too.
        """
        tokens = self.login()
        shared = tokens['refresh']

        tab_one = APIClient().post(reverse('token_refresh'), {'refresh': shared})
        tab_two = APIClient().post(reverse('token_refresh'), {'refresh': shared})

        self.assertEqual(tab_one.status_code, 200)
        self.assertEqual(tab_two.status_code, 200, 'second tab was logged out')

        # Both tabs came away with a usable access token.
        for response in (tab_one, tab_two):
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
            self.assertEqual(client.get(reverse('profile')).status_code, 200)

    @override_settings(REFRESH_REUSE_GRACE_SECONDS=10)
    def test_grace_window_does_not_excuse_a_late_replay(self):
        tokens = self.login()
        first = tokens['refresh']
        APIClient().post(reverse('token_refresh'), {'refresh': first})

        # Age the blacklist entry past the window.
        BlacklistedToken.objects.update(
            blacklisted_at=timezone.now() - timedelta(seconds=60)
        )

        replayed = APIClient().post(reverse('token_refresh'), {'refresh': first})
        self.assertEqual(replayed.status_code, 401)


class LogoutTests(AuthTestMixin, TestCase):
    """H2: logout has to work in the state logout exists for."""

    def setUp(self):
        super().setUp()
        self.user = self.make_user()

    def test_logout_blacklists_the_refresh_token(self):
        tokens = self.login()
        res = APIClient().post(reverse('logout'), {'refresh': tokens['refresh']})
        self.assertEqual(res.status_code, 204)

        replayed = APIClient().post(reverse('token_refresh'), {'refresh': tokens['refresh']})
        self.assertEqual(replayed.status_code, 401)

    def test_logout_works_without_a_usable_access_token(self):
        """
        The original failure: with IsAuthenticated (and DRF authenticating
        before it checks permissions), an idle user's expired access token
        turns logout into a 401. The client swallows it, clears localStorage,
        and reports success -- while the refresh token stays live.
        """
        tokens = self.login()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer expired.or.garbage.token')

        res = client.post(reverse('logout'), {'refresh': tokens['refresh']})
        self.assertEqual(res.status_code, 204)

        replayed = APIClient().post(reverse('token_refresh'), {'refresh': tokens['refresh']})
        self.assertEqual(replayed.status_code, 401)

    def test_logout_is_idempotent(self):
        tokens = self.login()
        APIClient().post(reverse('logout'), {'refresh': tokens['refresh']})
        again = APIClient().post(reverse('logout'), {'refresh': tokens['refresh']})
        self.assertEqual(again.status_code, 204)

    def test_logout_without_a_token_is_a_400(self):
        self.assertEqual(APIClient().post(reverse('logout'), {}).status_code, 400)

    def test_logout_tolerates_a_json_array_body(self):
        """request.data is a list here; a bare .get() would raise TypeError."""
        res = APIClient().post(reverse('logout'), ['nonsense'], format='json')
        self.assertEqual(res.status_code, 400)


class TokenVersionRevocationTests(AuthTestMixin, TestCase):
    """
    1a: revocation that actually covers access tokens.

    The blacklist is never consulted on the access path, so without this a
    stolen access token survives logout for its full lifetime.
    """

    def setUp(self):
        super().setUp()
        self.user = self.make_user()

    def test_access_token_stops_working_after_logout_all(self):
        tokens = self.login()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(client.get(reverse('profile')).status_code, 200)

        client.post(reverse('logout_all'))

        # Same still-unexpired access token, now revoked.
        self.assertEqual(client.get(reverse('profile')).status_code, 401)

    def test_refresh_token_stops_working_after_logout_all(self):
        tokens = self.login()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        client.post(reverse('logout_all'))

        res = APIClient().post(reverse('token_refresh'), {'refresh': tokens['refresh']})
        self.assertEqual(res.status_code, 401)

    def test_a_token_with_no_version_claim_is_rejected(self):
        """Tokens minted before the claim existed must not be grandfathered."""
        token = RefreshToken.for_user(self.user)   # stock class, no claim
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.assertEqual(client.get(reverse('profile')).status_code, 401)

    def test_fresh_login_after_revocation_works(self):
        self.login()
        self.user.revoke_tokens()
        tokens = self.login()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(client.get(reverse('profile')).status_code, 200)


OLD_KEY = 'o' * 40
NEW_KEY = 'n' * 40


class TokenValidationTests(AuthTestMixin, TestCase):
    """
    JWT checklist: pinned algorithm, required iss/aud, and overlapping keys
    so JWT_SIGNING_KEY rotation isn't forced to be a global logout.
    """

    def setUp(self):
        super().setUp()
        self.user = self.make_user()

    def claims(self):
        """A real, currently valid access-token payload to tamper with."""
        access = self.login()['access']
        return jwt.decode(access, options={'verify_signature': False})

    def status_with(self, token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return client.get(reverse('profile')).status_code

    def sign(self, payload, key=None, algorithm='HS256'):
        return jwt.encode(payload, key or settings.SIMPLE_JWT['SIGNING_KEY'],
                          algorithm=algorithm)

    def test_issued_tokens_carry_issuer_and_audience(self):
        claims = self.claims()
        self.assertEqual(claims['iss'], settings.SIMPLE_JWT['ISSUER'])
        self.assertEqual(claims['aud'], settings.SIMPLE_JWT['AUDIENCE'])

    def test_control_resigned_token_is_accepted(self):
        """Proves the tampering tests below fail for the stated reason."""
        self.assertEqual(self.status_with(self.sign(self.claims())), 200)

    def test_wrong_or_missing_audience_is_rejected(self):
        claims = self.claims()
        self.assertEqual(self.status_with(self.sign({**claims, 'aud': 'other-api'})), 401)
        claims.pop('aud')
        self.assertEqual(self.status_with(self.sign(claims)), 401)

    def test_wrong_or_missing_issuer_is_rejected(self):
        claims = self.claims()
        self.assertEqual(self.status_with(self.sign({**claims, 'iss': 'evil'})), 401)
        claims.pop('iss')
        self.assertEqual(self.status_with(self.sign(claims)), 401)

    def test_alg_none_is_rejected(self):
        token = jwt.encode(self.claims(), None, algorithm='none')
        self.assertEqual(self.status_with(token), 401)

    def test_other_hmac_algorithm_is_rejected(self):
        """Same key, different algorithm: the allowlist is exactly HS256."""
        token = self.sign(self.claims(), algorithm='HS512')
        self.assertEqual(self.status_with(token), 401)

    def test_expired_token_is_rejected(self):
        claims = {**self.claims(), 'exp': int(time.time()) - 60}
        self.assertEqual(self.status_with(self.sign(claims)), 401)

    def test_unknown_key_is_rejected(self):
        self.assertEqual(self.status_with(self.sign(self.claims(), key='x' * 40)), 401)

    def test_min_key_length_is_enforced(self):
        from django.core.exceptions import ImproperlyConfigured
        from config.settings import validate_jwt_key
        with self.assertRaises(ImproperlyConfigured):
            validate_jwt_key('JWT_SIGNING_KEY', 'short-key')
        validate_jwt_key('JWT_SIGNING_KEY', 'k' * 32)


class SigningKeyRotationTests(AuthTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user()

    def jwt_settings(self, **overrides):
        return override_settings(SIMPLE_JWT={**settings.SIMPLE_JWT, **overrides})

    def test_token_signed_with_previous_key_survives_rotation(self):
        with self.jwt_settings(SIGNING_KEY=OLD_KEY):
            tokens = self.login()

        with self.jwt_settings(SIGNING_KEY=NEW_KEY), \
                override_settings(JWT_PREVIOUS_SIGNING_KEYS=[OLD_KEY]):
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
            self.assertEqual(client.get(reverse('profile')).status_code, 200)

            res = APIClient().post(reverse('token_refresh'), {'refresh': tokens['refresh']})
            self.assertEqual(res.status_code, 200, res.data)

        # The refresh re-signed the session with the new key, so it outlives
        # the old key being dropped entirely.
        for token in (res.data['access'], res.data['refresh']):
            jwt.decode(token, NEW_KEY, algorithms=['HS256'],
                       audience=settings.SIMPLE_JWT['AUDIENCE'])
        with self.jwt_settings(SIGNING_KEY=NEW_KEY):
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
            self.assertEqual(client.get(reverse('profile')).status_code, 200)

    def test_rotation_without_previous_keys_is_a_global_logout(self):
        with self.jwt_settings(SIGNING_KEY=OLD_KEY):
            tokens = self.login()

        with self.jwt_settings(SIGNING_KEY=NEW_KEY):
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
            self.assertEqual(client.get(reverse('profile')).status_code, 401)
            res = APIClient().post(reverse('token_refresh'), {'refresh': tokens['refresh']})
            self.assertEqual(res.status_code, 401)


COOKIE = settings.REFRESH_COOKIE_NAME
XHR = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}


class RefreshCookieTests(AuthTestMixin, TestCase):
    """
    COOKIE_AUTH_PLAN.md Phase 1: the refresh token as an HttpOnly cookie,
    with CSRF defences on the endpoints that consume it.
    """

    def setUp(self):
        super().setUp()
        self.user = self.make_user()

    def cookie_login(self, **extra):
        """Log in on a client that keeps the cookie jar, like a browser."""
        client = APIClient()
        res = client.post(
            reverse('token_obtain_pair'),
            {'email': 'user@example.com', 'password': PASSWORD}, **extra,
        )
        self.assertEqual(res.status_code, 200, res.data)
        return client, res

    def test_login_sets_a_locked_down_cookie(self):
        with override_settings(REFRESH_COOKIE_SECURE=True):
            _, res = self.cookie_login()
        cookie = res.cookies[COOKIE]
        self.assertTrue(cookie['httponly'])
        self.assertTrue(cookie['secure'])
        self.assertEqual(cookie['samesite'], 'Strict')
        self.assertEqual(cookie['path'], '/api/auth/')
        self.assertEqual(
            cookie['max-age'],
            int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()),
        )
        self.assertNotIn('domain', {k for k, v in cookie.items() if v})
        # Dual mode: the pre-cookie frontend still gets it in JSON.
        self.assertEqual(res.data['refresh'], cookie.value)

    def test_refresh_from_cookie_alone_rotates_it(self):
        client, login = self.cookie_login()
        old = login.cookies[COOKIE].value

        res = client.post(reverse('token_refresh'), **XHR)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIn('access', res.data)
        self.assertNotEqual(res.cookies[COOKIE].value, old)

    @override_settings(REFRESH_REUSE_GRACE_SECONDS=0)
    def test_rotated_cookie_cannot_be_replayed(self):
        client, login = self.cookie_login()
        old = login.cookies[COOKIE].value
        client.post(reverse('token_refresh'), **XHR)

        attacker = APIClient()
        attacker.cookies[COOKIE] = old
        self.assertEqual(attacker.post(reverse('token_refresh'), **XHR).status_code, 401)

    def test_cookie_refresh_without_xhr_header_is_refused(self):
        """The forged-POST DoS: a foreign page can't add the header."""
        client, _ = self.cookie_login()
        self.assertEqual(client.post(reverse('token_refresh')).status_code, 403)

    def test_failed_refresh_does_not_clear_the_cookie(self):
        """A stale tab's failure must not delete the peer tab's new cookie."""
        client = APIClient()
        client.cookies[COOKIE] = 'garbage'
        res = client.post(reverse('token_refresh'), **XHR)
        self.assertEqual(res.status_code, 401)
        self.assertNotIn(COOKIE, res.cookies)

    def test_body_token_wins_without_xhr_header(self):
        """
        The pre-cookie frontend: its users hold the cookie (login sets it
        for everyone) but it never sends X-Requested-With. Preferring the
        cookie would 403 all of them mid-deploy.
        """
        client, login = self.cookie_login()
        res = client.post(reverse('token_refresh'), {'refresh': login.data['refresh']})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['refresh'], res.cookies[COOKIE].value)

    def test_foreign_origin_is_refused_on_login_and_refresh(self):
        evil = {'HTTP_ORIGIN': 'https://evil.example'}
        res = APIClient().post(
            reverse('token_obtain_pair'),
            {'email': 'user@example.com', 'password': PASSWORD}, **evil,
        )
        self.assertEqual(res.status_code, 403)
        self.assertNotIn(COOKIE, res.cookies)

        client, _ = self.cookie_login()
        self.assertEqual(client.post(reverse('token_refresh'), **XHR, **evil).status_code, 403)

    def test_trusted_origin_is_accepted(self):
        self.cookie_login(HTTP_ORIGIN=settings.AUTH_TRUSTED_ORIGINS[0])

    def test_logout_via_cookie_revokes_and_clears_it(self):
        client, login = self.cookie_login()
        old = login.cookies[COOKIE].value

        res = client.post(reverse('logout'), **XHR)
        self.assertEqual(res.status_code, 204)
        self.assertEqual(res.cookies[COOKIE]['max-age'], 0)
        self.assertEqual(res.cookies[COOKIE]['path'], '/api/auth/')

        replay = APIClient()
        replay.cookies[COOKIE] = old
        self.assertEqual(replay.post(reverse('token_refresh'), **XHR).status_code, 401)

    def test_cookie_logout_without_xhr_header_is_refused(self):
        """Otherwise any site could log the user out with one forged POST."""
        client, _ = self.cookie_login()
        self.assertEqual(client.post(reverse('logout')).status_code, 403)

    def test_logout_all_clears_the_cookie(self):
        client, login = self.cookie_login()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post(reverse('logout_all'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.cookies[COOKIE]['max-age'], 0)

    def test_auth_responses_are_never_cached(self):
        client, login = self.cookie_login()
        responses = {
            'login': login,
            'refresh': client.post(reverse('token_refresh'), **XHR),
            'failed login': APIClient().post(
                reverse('token_obtain_pair'),
                {'email': 'user@example.com', 'password': 'wrong'},
            ),
            'logout': client.post(reverse('logout'), **XHR),
        }
        for name, res in responses.items():
            with self.subTest(name):
                self.assertIn('no-store', res['Cache-Control'])

    @override_settings(REFRESH_TOKEN_IN_BODY=False)
    def test_cookie_only_mode(self):
        """Phase 3: the refresh token never appears in JSON or the body."""
        client, login = self.cookie_login()
        self.assertNotIn('refresh', login.data)
        self.assertIn(COOKIE, login.cookies)

        res = client.post(reverse('token_refresh'), **XHR)
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('refresh', res.data)

        # A body token is ignored outright, so a stolen one is useless here.
        stolen = res.cookies[COOKIE].value
        res = APIClient().post(reverse('token_refresh'), {'refresh': stolen}, **XHR)
        self.assertEqual(res.status_code, 400)


class LoginHardeningTests(AuthTestMixin, TestCase):
    """M3: per-account lockout, not per-IP."""

    def setUp(self):
        super().setUp()
        self.user = self.make_user()

    @override_settings(LOGIN_FAILURE_LIMIT=3)
    def test_account_locks_out_after_repeated_failures(self):
        client = APIClient()
        for _ in range(3):
            res = client.post(
                reverse('token_obtain_pair'),
                {'email': 'user@example.com', 'password': 'wrong-password'},
            )
            self.assertEqual(res.status_code, 401)

        # Correct password, but the account is locked.
        res = client.post(
            reverse('token_obtain_pair'),
            {'email': 'user@example.com', 'password': PASSWORD},
        )
        self.assertEqual(res.status_code, 429)

    @override_settings(LOGIN_FAILURE_LIMIT=3)
    def test_lockout_is_scoped_to_the_account_not_the_client(self):
        """
        A shared NAT egress must not let one attacked account lock out an
        unrelated user coming from the same address.
        """
        self.make_user('other@example.com')
        client = APIClient()
        for _ in range(3):
            client.post(
                reverse('token_obtain_pair'),
                {'email': 'user@example.com', 'password': 'wrong-password'},
            )

        res = client.post(
            reverse('token_obtain_pair'),
            {'email': 'other@example.com', 'password': PASSWORD},
        )
        self.assertEqual(res.status_code, 200)

    @override_settings(LOGIN_FAILURE_LIMIT=3)
    def test_successful_login_clears_the_failure_counter(self):
        client = APIClient()
        for _ in range(2):
            client.post(
                reverse('token_obtain_pair'),
                {'email': 'user@example.com', 'password': 'wrong'},
            )
        self.assertEqual(
            client.post(
                reverse('token_obtain_pair'),
                {'email': 'user@example.com', 'password': PASSWORD},
            ).status_code,
            200,
        )
        for _ in range(2):
            res = client.post(
                reverse('token_obtain_pair'),
                {'email': 'user@example.com', 'password': 'wrong'},
            )
            self.assertEqual(res.status_code, 401, 'counter was not reset')

    def test_login_throttle_uses_its_own_bucket(self):
        """
        Tightening the login limit must not throttle token refresh, which is
        AllowAny and would otherwise share the `anon` bucket.
        """
        from .views import LoginRateThrottle
        self.assertEqual(LoginRateThrottle.scope, 'login')
        self.assertIn('login', settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'])


class CurrencyValidationTests(AuthTestMixin, TestCase):
    """L1: the anchor bug, plus constraining to currencies we hold rates for."""

    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _post(self, currency):
        return self.client.post(reverse('subscription-list'), {
            'name': 'Test', 'amount': '5.00',
            'original_currency': currency, 'billing_cycle': 'monthly',
        })

    def test_rejects_markup(self):
        self.assertEqual(self._post('<b>').status_code, 400)

    def test_trailing_newline_never_reaches_the_database(self):
        """
        `$` matches before a trailing newline in Python, so the old
        `^[A-Z]{3}$` accepted a padded code outright. What actually saved it
        was the model's max_length rejecting the 4-character string first --
        an incidental length check, not the validator. With the `\Z` anchor
        plus explicit normalisation, the stored value is provably clean.
        """
        res = self._post('USD\n')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['original_currency'], 'USD')

    def test_rejects_wellformed_but_unsupported_code(self):
        res = self._post('ZWL')
        self.assertEqual(res.status_code, 400)
        self.assertIn('Unsupported currency', str(res.data['original_currency']))

    def test_accepts_and_normalises_a_supported_code(self):
        res = self._post('usd')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['original_currency'], 'USD')

    def test_profile_base_currency_is_validated_too(self):
        res = self.client.patch(reverse('profile'), {'base_currency': 'ZWL'})
        self.assertEqual(res.status_code, 400)

    def test_hex_colour_regex_is_anchored_with_capital_z(self):
        """
        Asserted against the pattern rather than the endpoint because DRF's
        CharField trims whitespace before validators run. The anchor still
        has to be right: hex_color_code is interpolated into inline styles
        downstream, and that guarantee should not rest on two unrelated
        layers happening to strip the input first.
        """
        from .serializers import HEX_COLOR_RE
        self.assertIsNone(HEX_COLOR_RE.match('#123456\n'))
        self.assertIsNotNone(HEX_COLOR_RE.match('#123456'))
        # The pattern this replaced accepted the trailing newline.
        self.assertIsNotNone(re.match(r'^#[0-9A-Fa-f]{6}$', '#123456\n'))

    def test_hex_colour_rejects_markup(self):
        res = self.client.post(
            reverse('category-list'),
            {'name': 'X', 'hex_color_code': '#123456"><script>'},
        )
        self.assertEqual(res.status_code, 400)

    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @override_settings(MAX_SUBSCRIPTIONS_PER_USER=2)
    def test_subscription_cap_is_enforced(self):
        for i in range(2):
            res = self.client.post(reverse('subscription-list'), {
                'name': f'Sub {i}', 'amount': '5.00',
                'original_currency': 'USD', 'billing_cycle': 'monthly',
            })
            self.assertEqual(res.status_code, 201)

        res = self.client.post(reverse('subscription-list'), {
            'name': 'One too many', 'amount': '5.00',
            'original_currency': 'USD', 'billing_cycle': 'monthly',
        })
        self.assertEqual(res.status_code, 400)

    @override_settings(MAX_CATEGORIES_PER_USER=1)
    def test_category_cap_is_enforced(self):
        first = self.client.post(
            reverse('category-list'), {'name': 'A', 'hex_color_code': '#111111'}
        )
        self.assertEqual(first.status_code, 201)
        second = self.client.post(
            reverse('category-list'), {'name': 'B', 'hex_color_code': '#222222'}
        )
        self.assertEqual(second.status_code, 400)


class ProjectionsQueryCountTests(AuthTestMixin, TestCase):
    """
    M5, corrected: the expensive part of ProjectionsView was never the
    Decimal maths -- it was one to two ExchangeRate queries per subscription
    inside the loop.
    """

    def setUp(self):
        super().setUp()
        self.user = self.make_user(base_currency='GBP')
        for code, rate in (
            ('EUR', '0.850000'), ('GBP', '0.750000'), ('JPY', '150.000000'),
            ('CAD', '1.350000'), ('AUD', '1.500000'),
        ):
            ExchangeRate.objects.create(
                currency_pair=f'USD_{code}', rate=Decimal(rate)
            )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _make_subscriptions(self, count):
        currencies = ['USD', 'EUR', 'JPY', 'CAD', 'AUD']
        Subscription.objects.bulk_create([
            Subscription(
                user=self.user, name=f'Sub {i}', amount=Decimal('10.00'),
                original_currency=currencies[i % len(currencies)],
                billing_cycle='monthly',
            )
            for i in range(count)
        ])

    def test_query_count_is_constant_in_the_number_of_subscriptions(self):
        self._make_subscriptions(5)
        with CaptureQueriesContext(connection) as few:
            self.assertEqual(self.client.get(reverse('projections')).status_code, 200)

        Subscription.objects.all().delete()
        self._make_subscriptions(30)
        with CaptureQueriesContext(connection) as many:
            res = self.client.get(reverse('projections'))
            self.assertEqual(res.status_code, 200)

        self.assertEqual(len(res.data['line_items']), 30)
        self.assertEqual(
            len(many.captured_queries), len(few.captured_queries),
            'query count grows with the number of subscriptions (N+1)',
        )

    def test_projection_totals_are_unchanged_by_the_rate_table(self):
        Subscription.objects.create(
            user=self.user, name='Euro SaaS', amount=Decimal('100.00'),
            original_currency='EUR', billing_cycle='monthly',
        )
        res = self.client.get(reverse('projections'))
        # 100 EUR * (0.75 / 0.85) = 88.24 GBP
        self.assertEqual(res.data['monthly_total'], '88.24')


class StaleRateWarningTests(AuthTestMixin, TestCase):
    """L3: a rate synced months ago was served as current with no signal."""

    def setUp(self):
        super().setUp()
        self.user = self.make_user(base_currency='USD')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        ExchangeRate.objects.create(currency_pair='USD_EUR', rate=Decimal('0.850000'))
        Subscription.objects.create(
            user=self.user, name='Euro SaaS', amount=Decimal('10.00'),
            original_currency='EUR', billing_cycle='monthly',
        )

    def test_fresh_rate_produces_no_warning(self):
        res = self.client.get(reverse('projections'))
        self.assertEqual(res.data['warnings'], [])

    def test_stale_rate_is_reported(self):
        # last_updated is auto_now, so age it with a direct UPDATE.
        ExchangeRate.objects.filter(currency_pair='USD_EUR').update(
            last_updated=timezone.now() - timedelta(days=90)
        )
        res = self.client.get(reverse('projections'))
        self.assertEqual(len(res.data['warnings']), 1)
        self.assertIn('has not been updated', res.data['warnings'][0])
        # Still converted, not skipped: 10 EUR / 0.85 = 11.76 USD.
        self.assertEqual(res.data['monthly_total'], '11.76')


class SettingsHardeningTests(TestCase):
    """H3/H5: the settings bugs that made the file lie about itself."""

    def test_debug_defaults_to_false(self):
        from config.settings import env_bool
        self.assertFalse(env_bool('CLEARSPEND_DEFINITELY_UNSET_VAR', False))

    def test_debug_parsing_is_tolerant(self):
        """`== 'True'` read all of these as False, silently."""
        from config.settings import env_bool
        for raw in ('true', 'True', '1', 'yes', 'TRUE ', ' true'):
            with self.subTest(raw=raw):
                os.environ['CLEARSPEND_TEST_BOOL'] = raw
                self.assertTrue(env_bool('CLEARSPEND_TEST_BOOL'))
        for raw in ('false', '0', 'no', ''):
            with self.subTest(raw=raw):
                os.environ['CLEARSPEND_TEST_BOOL'] = raw
                self.assertFalse(env_bool('CLEARSPEND_TEST_BOOL'))
        os.environ.pop('CLEARSPEND_TEST_BOOL', None)

    def test_database_url_is_actually_honoured(self):
        """
        .env.example advertised DATABASE_URL while settings hardcoded SQLite.
        """
        import dj_database_url
        parsed = dj_database_url.parse('postgres://u:p@db.example.com:5432/clearspend')
        self.assertEqual(parsed['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(parsed['NAME'], 'clearspend')

    def test_jwt_signing_key_is_separable_from_secret_key(self):
        """
        Otherwise rotating SECRET_KEY silently logs out every user, because
        SimpleJWT falls back to it for SIGNING_KEY.
        """
        self.assertIn('SIGNING_KEY', settings.SIMPLE_JWT)
        self.assertTrue(settings.SIMPLE_JWT['SIGNING_KEY'])

    def test_static_root_is_set(self):
        """Without it, collectstatic fails and DEBUG=False breaks /admin/."""
        self.assertTrue(settings.STATIC_ROOT)

    def test_error_logging_is_configured(self):
        """
        With DEBUG=False and no LOGGING, Django routes ERROR to mail_admins
        and ADMINS is unset -- 500s would go nowhere at all.
        """
        self.assertIn('console', settings.LOGGING['handlers'])
        self.assertIn('django.request', settings.LOGGING['loggers'])

    def test_csp_is_configured_without_unsafe_inline(self):
        directives = settings.CONTENT_SECURITY_POLICY['DIRECTIVES']
        self.assertEqual(directives['frame-ancestors'], ["'none'"])
        for name, value in directives.items():
            self.assertNotIn("'unsafe-inline'", value or [], f'{name} allows inline')

    def test_fx_provider_must_be_https(self):
        """Rates are an input to the money path."""
        self.assertTrue(settings.EXCHANGE_RATE_API_BASE_URL.startswith('https://'))


class ResilientRedisCacheTests(TestCase):
    """
    The Redis cache config that 500'd every /api/ request in production.

    `IGNORE_EXCEPTIONS` is a django-redis option. Django's built-in RedisCache
    forwards unrecognised OPTIONS into redis.ConnectionPool.from_url(), which
    raises TypeError -- and because pool construction is lazy it did so on the
    first cache access inside a request, not at startup. The process booted
    clean and served 404s while everything reaching DRF's throttle 500'd.
    """

    # Port 1 on loopback refuses immediately: an unreachable Redis, no waiting.
    UNREACHABLE = 'redis://127.0.0.1:1/0'

    def _cache(self, **params):
        from config.cache import ResilientRedisCache
        return ResilientRedisCache(self.UNREACHABLE, params)

    def test_unreachable_redis_degrades_to_a_miss(self):
        """The regression: this raised instead of returning the default."""
        cache_ = self._cache()
        with self.assertLogs('config.cache', level='WARNING'):
            self.assertEqual(cache_.get('any-key', 'fallback'), 'fallback')

    def test_throttle_and_lockout_calls_survive_an_outage(self):
        """Every method the throttle and login lockout actually reach."""
        cache_ = self._cache()
        with self.assertLogs('config.cache', level='WARNING'):
            self.assertEqual(cache_.get('k', 0), 0)      # _login_failures
            self.assertIs(cache_.add('k', 1, 60), False)  # _record_login_failure
            self.assertIsNone(cache_.incr('k'))
            self.assertIsNone(cache_.set('k', 1, 60))     # throttle history
            self.assertIs(cache_.delete('k'), False)      # _clear_login_failures

    def test_ignore_exceptions_option_does_not_reach_the_pool(self):
        """
        The exact production config. Left in OPTIONS it becomes
        `TypeError: AbstractConnection.__init__() got an unexpected keyword
        argument 'IGNORE_EXCEPTIONS'`.
        """
        cache_ = self._cache(OPTIONS={'IGNORE_EXCEPTIONS': True})
        with self.assertLogs('config.cache', level='WARNING') as logs:
            self.assertIsNone(cache_.get('any-key'))
        self.assertNotIn('IGNORE_EXCEPTIONS', ''.join(logs.output))

    def test_incr_value_error_is_not_swallowed(self):
        """
        incr() raises ValueError for a missing key and _record_login_failure
        relies on it to restart an expired window. Only transport errors are
        degraded; swallowing this would silently stop counting failures.
        """
        cache_ = self._cache()
        with mock.patch(
            'django.core.cache.backends.redis.RedisCache.incr',
            side_effect=ValueError('Key not found'),
        ):
            with self.assertRaises(ValueError):
                cache_.incr('k')

    def test_settings_selects_the_resilient_backend_for_redis(self):
        """Both aliases, or the lockout counter alone would still 500."""
        import importlib
        from config import settings as settings_module

        with mock.patch.dict(os.environ, {'REDIS_URL': self.UNREACHABLE}):
            reloaded = importlib.reload(settings_module)
        try:
            for alias in ('default', 'lockout'):
                with self.subTest(alias=alias):
                    self.assertEqual(
                        reloaded.CACHES[alias]['BACKEND'],
                        'config.cache.ResilientRedisCache',
                    )
                    self.assertNotIn(
                        'IGNORE_EXCEPTIONS',
                        reloaded.CACHES[alias].get('OPTIONS', {}),
                    )
        finally:
            importlib.reload(settings_module)


class FetchExchangeRatesTests(TestCase):
    """L3: the sync command's failure modes."""

    def _response(self, rows):
        mock_response = mock.Mock()
        mock_response.json.return_value = rows
        mock_response.raise_for_status.return_value = None
        return mock_response

    @mock.patch('subscriptions.management.commands.fetch_exchange_rates.requests.get')
    def test_rates_are_upserted(self, mock_get):
        mock_get.return_value = self._response([
            {'quote': 'EUR', 'rate': 0.86}, {'quote': 'GBP', 'rate': 0.75},
        ])
        call_command('fetch_exchange_rates', stdout=StringIO(), stderr=StringIO())
        self.assertEqual(
            ExchangeRate.objects.get(currency_pair='USD_EUR').rate, Decimal('0.86')
        )

    @mock.patch('subscriptions.management.commands.fetch_exchange_rates.requests.get')
    def test_network_failure_exits_non_zero_and_preserves_rates(self, mock_get):
        ExchangeRate.objects.create(currency_pair='USD_EUR', rate=Decimal('0.850000'))
        mock_get.side_effect = requests.RequestException('boom')

        # A bare `return` here reported success to cron.
        with self.assertRaises(CommandError):
            call_command('fetch_exchange_rates', stdout=StringIO(), stderr=StringIO())

        self.assertEqual(
            ExchangeRate.objects.get(currency_pair='USD_EUR').rate, Decimal('0.850000')
        )

    @mock.patch('subscriptions.management.commands.fetch_exchange_rates.requests.get')
    def test_implausible_move_is_rejected(self, mock_get):
        """
        A relative check catches what an absolute range cannot: 0.85 -> 85 is
        a 100x error that sits comfortably inside any plausible fixed window.
        """
        ExchangeRate.objects.create(currency_pair='USD_EUR', rate=Decimal('0.850000'))
        mock_get.return_value = self._response([{'quote': 'EUR', 'rate': 85.0}])

        with self.assertRaises(CommandError):
            call_command('fetch_exchange_rates', stdout=StringIO(), stderr=StringIO())

        self.assertEqual(
            ExchangeRate.objects.get(currency_pair='USD_EUR').rate, Decimal('0.850000')
        )

    @mock.patch('subscriptions.management.commands.fetch_exchange_rates.requests.get')
    def test_force_overrides_the_sanity_check(self, mock_get):
        ExchangeRate.objects.create(currency_pair='USD_EUR', rate=Decimal('0.850000'))
        mock_get.return_value = self._response([{'quote': 'EUR', 'rate': 85.0}])

        call_command('fetch_exchange_rates', '--force', stdout=StringIO(), stderr=StringIO())
        self.assertEqual(
            ExchangeRate.objects.get(currency_pair='USD_EUR').rate, Decimal('85.000000')
        )

    @mock.patch('subscriptions.management.commands.fetch_exchange_rates.requests.get')
    def test_first_sync_accepts_any_plausible_rate(self, mock_get):
        """No stored value to compare against; only the positivity check applies."""
        mock_get.return_value = self._response([{'quote': 'JPY', 'rate': 150.0}])
        call_command('fetch_exchange_rates', stdout=StringIO(), stderr=StringIO())
        self.assertEqual(
            ExchangeRate.objects.get(currency_pair='USD_JPY').rate, Decimal('150.000000')
        )

    @mock.patch('subscriptions.management.commands.fetch_exchange_rates.requests.get')
    def test_malformed_payload_is_a_command_error(self, mock_get):
        mock_get.return_value = self._response({'rates': {'EUR': 0.86}})  # v1 shape
        with self.assertRaises(CommandError):
            call_command('fetch_exchange_rates', stdout=StringIO(), stderr=StringIO())


class PaginationTests(AuthTestMixin, TestCase):
    """
    M5: pagination is safe here only because the dashboard's totals come from
    ProjectionsView, which walks the full active set server-side.
    """

    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        Subscription.objects.bulk_create([
            Subscription(
                user=self.user, name=f'Sub {i}', amount=Decimal('1.00'),
                original_currency='USD', billing_cycle='monthly',
            )
            for i in range(5)
        ])

    def test_list_response_is_paginated(self):
        res = self.client.get(reverse('subscription-list'))
        self.assertEqual(res.status_code, 200)
        self.assertIn('results', res.data)
        self.assertEqual(res.data['count'], 5)

    def test_page_size_is_capped(self):
        res = self.client.get(reverse('subscription-list'), {'page_size': '100000'})
        self.assertLessEqual(len(res.data['results']), 500)

    def test_totals_do_not_depend_on_the_page(self):
        ExchangeRate.objects.create(currency_pair='USD_EUR', rate=Decimal('0.85'))
        res = self.client.get(reverse('projections'), {'page_size': '1'})
        self.assertEqual(res.data['monthly_total'], '5.00')


class StaleTokenDoesNotBlockPublicEndpointsTests(AuthTestMixin, TestCase):
    """
    Caught by driving the real app, not by the suite: DRF authenticates
    before it checks AllowAny, so a stale Authorization header 401s an
    endpoint that is nominally public.

    For /auth/ that is a lockout rather than an annoyance -- the expired
    token blocks the very requests needed to obtain a fresh one, and the only
    way out is clearing site data. It bites hardest on the deploy that
    introduces token_version, which invalidates every previously issued
    token at once.

    APIClient sends no ambient header, which is exactly why this went
    unnoticed: it has to be asserted explicitly.
    """

    STALE = 'Bearer eyJhbGciOiJIUzI1NiJ9.stale.signature'

    def test_register_works_with_a_stale_token_present(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=self.STALE)
        res = client.post(reverse('register'), {
            'email': 'newcomer@example.com', 'username': 'newcomer',
            'password': PASSWORD,
        })
        self.assertEqual(res.status_code, 201, res.data)

    def test_login_works_with_a_stale_token_present(self):
        self.make_user()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=self.STALE)
        res = client.post(
            reverse('token_obtain_pair'),
            {'email': 'user@example.com', 'password': PASSWORD},
        )
        self.assertEqual(res.status_code, 200, res.data)

    def test_refresh_works_with_a_stale_access_token_present(self):
        self.make_user()
        tokens = self.login()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=self.STALE)
        res = client.post(reverse('token_refresh'), {'refresh': tokens['refresh']})
        self.assertEqual(res.status_code, 200, res.data)

    def test_currencies_works_with_a_stale_token_present(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=self.STALE)
        self.assertEqual(client.get(reverse('currencies')).status_code, 200)

    def test_protected_endpoints_still_reject_a_stale_token(self):
        """The carve-out must not leak into anything that holds data."""
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=self.STALE)
        for name in ('profile', 'projections', 'subscription-list', 'category-list'):
            with self.subTest(endpoint=name):
                self.assertEqual(client.get(reverse(name)).status_code, 401)


class StartDateRenewalTests(AuthTestMixin, TestCase):
    """
    next_renewal_date is a SerializerMethodField evaluated for every row of
    every list page, so its cost per row is a property of the API's worst
    case, not just of the model.
    """

    def _sub(self, **kwargs):
        # Unsaved on purpose: get_next_renewal_date is pure computation over
        # start_date and billing_cycle, so these cases need no user and no
        # database round-trip.
        return Subscription(
            name='S', amount=Decimal('10.00'), original_currency='USD', **kwargs
        )

    def test_far_past_start_date_is_cheap_to_evaluate(self):
        """
        Regression: the monthly and yearly branches used to advance one period
        at a time from start_date, so a date in year 1 cost ~24k relativedelta
        additions per row -- roughly 0.1s each, and a page holds up to 500.
        """
        for cycle in ('monthly', 'yearly'):
            with self.subTest(cycle=cycle):
                sub = self._sub(billing_cycle=cycle, start_date=date(1, 1, 1))
                started = time.perf_counter()
                renewal = sub.get_next_renewal_date()
                elapsed = time.perf_counter() - started

                self.assertIsNotNone(renewal)
                self.assertGreaterEqual(renewal, date.today())
                # Generous: the fixed version is microseconds, the old one
                # was ~0.1s for monthly. Anything near the old cost fails.
                self.assertLess(elapsed, 0.01, f'{cycle} took {elapsed:.4f}s')

    def test_month_end_anchoring_does_not_drift(self):
        """
        Adding one month at a time compounded end-of-month clamping: Jan 31
        became Feb 28 and then stayed on the 28th forever. Each step is now
        anchored to start_date, so the day-of-month recovers.
        """
        sub = self._sub(billing_cycle='monthly', start_date=date(2026, 1, 31))
        self.assertEqual(
            sub.get_next_renewal_date(today=date(2026, 2, 1)), date(2026, 2, 28)
        )
        self.assertEqual(
            sub.get_next_renewal_date(today=date(2026, 3, 1)), date(2026, 3, 31)
        )

    def test_renewal_on_exact_boundary_is_today(self):
        sub = self._sub(billing_cycle='monthly', start_date=date(2026, 1, 15))
        self.assertEqual(
            sub.get_next_renewal_date(today=date(2026, 3, 15)), date(2026, 3, 15)
        )

    def test_yearly_leap_day_start(self):
        sub = self._sub(billing_cycle='yearly', start_date=date(2024, 2, 29))
        self.assertEqual(
            sub.get_next_renewal_date(today=date(2025, 1, 1)), date(2025, 2, 28)
        )
        self.assertEqual(
            sub.get_next_renewal_date(today=date(2028, 1, 1)), date(2028, 2, 29)
        )

    def test_api_rejects_implausible_start_dates(self):
        self.make_user()
        tokens = self.login()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        for label, value in (
            ('year 1', '0001-01-01'),
            ('far future', '3000-01-01'),
        ):
            with self.subTest(case=label):
                res = client.post(reverse('subscription-list'), {
                    'name': 'S', 'amount': '10.00', 'original_currency': 'USD',
                    'billing_cycle': 'monthly', 'start_date': value,
                })
                self.assertEqual(res.status_code, 400, res.data)
                self.assertIn('start_date', res.data)

    def test_api_accepts_a_reasonable_start_date(self):
        self.make_user()
        tokens = self.login()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        res = client.post(reverse('subscription-list'), {
            'name': 'S', 'amount': '10.00', 'original_currency': 'USD',
            'billing_cycle': 'monthly',
            'start_date': (date.today() - timedelta(days=400)).isoformat(),
        })
        self.assertEqual(res.status_code, 201, res.data)
        self.assertIsNotNone(res.data['next_renewal_date'])
