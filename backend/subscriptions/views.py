import hashlib
import logging
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.cache import caches
from django.utils import timezone
from rest_framework import generics, permissions, status, viewsets
from rest_framework.exceptions import AuthenticationFailed, Throttled
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .constants import BASE_CURRENCY, SUPPORTED_CURRENCIES
from .models import Category, ExchangeRate, RevokedRefreshToken, Subscription
from .serializers import (
    CategorySerializer,
    ClearSpendTokenObtainPairSerializer,
    ClearSpendTokenRefreshSerializer,
    RegisterSerializer,
    SubscriptionSerializer,
    UserProfileSerializer,
)
from .tokens import VersionedRefreshToken

logger = logging.getLogger('clearspend.security')

TWO_DP = Decimal('0.01')
# FX rates are stored at 6dp (ExchangeRate.rate); derived rates match.
RATE_DP = Decimal('0.000001')
# 365.25 / 12 -- accounts for leap years when converting a custom daily
# interval into an "average" monthly figure (PRD 3.4).
AVG_DAYS_PER_MONTH = Decimal('30.4375')


class LoginRateThrottle(AnonRateThrottle):
    """
    Dedicated bucket for credential submission.

    Kept separate from the shared `anon` scope so the login limit can be
    tightened without also throttling CustomTokenRefreshView, which is
    AllowAny and would otherwise start failing for every legitimate user
    behind shared NAT.
    """
    scope = 'login'


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

# Lockout counters are kept out of the default cache: see CACHES in settings.
_lockout_cache = caches['lockout']


def _lockout_key(email):
    """
    Hash the address into the key.

    The email arrives straight off an unauthenticated request body, so
    interpolating it raw handed an attacker full control of the cache key --
    unbounded in length (memcached rejects >250 chars, Redis just grows) and,
    worse, unlimited in cardinality: flooding distinct junk addresses evicted
    a real account's counter and cleared its lockout. Hashing bounds the key
    and removes that control while keeping the per-account semantics.
    """
    digest = hashlib.sha256(email.strip().lower().encode('utf-8')).hexdigest()
    return f'login-failures:{digest}'


def _login_failures(email):
    return _lockout_cache.get(_lockout_key(email), 0)


def _record_login_failure(email):
    """
    Count failures per *account*, not per IP.

    An IP-keyed lockout punishes NAT'd offices and mobile carriers while a
    distributed attacker spreading attempts across hosts walks straight past
    it. The per-IP LoginRateThrottle above still applies on top of this.
    """
    key = _lockout_key(email)
    # add() only sets when absent, so the window starts at the first failure
    # and does not slide forward on every subsequent one.
    if not _lockout_cache.add(key, 1, settings.LOGIN_FAILURE_WINDOW_SECONDS):
        try:
            _lockout_cache.incr(key)
        except ValueError:
            # Entry expired between add() and incr(); restart the window.
            _lockout_cache.set(key, 1, settings.LOGIN_FAILURE_WINDOW_SECONDS)


def _clear_login_failures(email):
    _lockout_cache.delete(_lockout_key(email))


class RegisterView(generics.CreateAPIView):
    """
    POST /api/auth/register/

    `authentication_classes = []` for the same reason as CurrenciesView and
    LogoutView: DRF authenticates before it checks AllowAny, so a stale or
    expired token left in a visitor's localStorage would 401 this endpoint
    and make it impossible to sign up without clearing site data.
    """
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonRateThrottle]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        logger.info('Account created: user_id=%s', user.pk)
        return Response(UserProfileSerializer(user).data, status=status.HTTP_201_CREATED)


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    POST /api/auth/token/  (login)

    Adds a per-account lockout and authentication logging on top of
    SimpleJWT's view.
    """
    serializer_class = ClearSpendTokenObtainPairSerializer
    # These endpoints take their credential from the request *body*. Running
    # header authentication over them means a stale token locks the user out
    # of the very endpoint they need in order to get a fresh one -- which is
    # exactly the state a user is in once their tokens expire.
    authentication_classes = []
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        email = ''
        if hasattr(request.data, 'get'):
            email = str(request.data.get('email') or '')

        if email and _login_failures(email) >= settings.LOGIN_FAILURE_LIMIT:
            logger.warning('Login blocked by account lockout: %s', email)
            raise Throttled(
                wait=settings.LOGIN_FAILURE_WINDOW_SECONDS,
                detail='Too many failed attempts for this account. Try again later.',
            )

        try:
            response = super().post(request, *args, **kwargs)
        except AuthenticationFailed:
            if email:
                _record_login_failure(email)
            logger.warning('Login failed: %s', email or '(no email supplied)')
            raise

        if email:
            _clear_login_failures(email)
        logger.info('Login succeeded: %s', email)
        return response


class CustomTokenRefreshView(TokenRefreshView):
    """POST /api/auth/token/refresh/"""
    serializer_class = ClearSpendTokenRefreshSerializer
    authentication_classes = []
    throttle_classes = [AnonRateThrottle]


class LogoutView(APIView):
    """
    POST /api/auth/logout/  -- blacklist one refresh token.

    Deliberately unauthenticated. The refresh token *is* the credential being
    revoked, and it is self-authenticating; demanding a second, shorter-lived
    credential to revoke it gets the dependency backwards. Requiring a valid
    access token would break logout in exactly the case it exists for: a user
    walking away from a shared machine has almost always been idle long
    enough for the 15-minute access token to expire, and the frontend does
    not refresh on /auth/ paths -- so the call would 401, the client would
    swallow it, and the refresh token would live on while the UI reported a
    successful logout.

    `authentication_classes = []` matters as much as the permission class:
    DRF runs authentication before permissions, so a stale Authorization
    header would 401 here even with AllowAny.
    """
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request):
        raw = None
        if hasattr(request.data, 'get'):
            # A JSON array body makes request.data a list; .get would raise.
            raw = request.data.get('refresh')

        if not raw:
            return Response(
                {'detail': 'A refresh token is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = VersionedRefreshToken(raw)
        except TokenError:
            # Already expired or already blacklisted. Logout is idempotent:
            # reporting failure here only teaches clients to skip the call.
            return Response(status=status.HTTP_204_NO_CONTENT)

        user_id = token.payload.get(api_settings.USER_ID_CLAIM)
        jti = token.payload.get(api_settings.JTI_CLAIM)

        # Recorded before blacklisting so there is no instant in which the
        # token counts as merely "rotated" and therefore inside the grace
        # window. Ordering matters more than it looks.
        if jti:
            RevokedRefreshToken.objects.get_or_create(jti=jti)

        try:
            token.blacklist()
        except AttributeError:
            # token_blacklist app not installed.
            logger.error('Logout could not blacklist: token_blacklist app missing.')
        logger.info('Logout: user_id=%s', user_id)

        return Response(status=status.HTTP_204_NO_CONTENT)


class LogoutAllView(APIView):
    """
    POST /api/auth/logout-all/  -- revoke every session for the caller.

    Bumps token_version, which invalidates outstanding access tokens too;
    blacklisting alone would leave them valid until they expire. Also
    blacklists the user's outstanding refresh tokens so the blacklist table
    reflects reality for anyone auditing it.

    This is the mechanism a password-change flow should call.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def post(self, request):
        version = request.user.revoke_tokens()

        outstanding = OutstandingToken.objects.filter(
            user=request.user, expires_at__gt=timezone.now()
        )
        for token in outstanding:
            BlacklistedToken.objects.get_or_create(token=token)

        logger.info(
            'All sessions revoked: user_id=%s token_version=%s',
            request.user.pk, version,
        )
        return Response({'detail': 'All sessions revoked.'}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

class ProfileView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/user/profile/"""
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

class CategoryViewSet(viewsets.ModelViewSet):
    """GET/POST /api/categories/, GET/PUT/PATCH/DELETE /api/categories/<id>/"""
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user).order_by('name')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

class SubscriptionViewSet(viewsets.ModelViewSet):
    """
    GET/POST /api/subscriptions/
    GET/PUT/PATCH/DELETE /api/subscriptions/<id>/

    DELETE is a soft delete (is_active=False) per PRD 3.2, so historical
    analytics survive removal.
    """
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get_queryset(self):
        # select_related('category') avoids an N+1 query per row when the
        # serializer/list view touches subscription.category.
        qs = Subscription.objects.filter(user=self.request.user).select_related('category')
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')
        return qs.order_by('-id')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

class CurrenciesView(APIView):
    """
    GET /api/currencies/

    Serves the canonical currency list so the frontend dropdowns cannot
    drift from what fetch_exchange_rates actually syncs.

    Unauthenticated on purpose: the registration form has to offer a
    base_currency before the user has an account. `authentication_classes`
    is emptied so a stale token in localStorage cannot turn this into a 401
    and bounce an anonymous visitor off /register.
    """
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonRateThrottle]

    def get(self, request):
        return Response({
            'currencies': SUPPORTED_CURRENCIES,
            'base_currency': BASE_CURRENCY,
        })


# ---------------------------------------------------------------------------
# Currency conversion
# ---------------------------------------------------------------------------

class RateTable:
    """
    The whole ExchangeRate table, loaded once and resolved from memory.

    Resolution previously ran one to two queries *per subscription* inside
    ProjectionsView's loop -- a textbook N+1 whose real cost was database
    round-trips, not the Decimal arithmetic. The table holds at most a few
    dozen rows (one per supported currency), so loading all of it once is
    strictly cheaper than any per-row lookup.
    """

    def __init__(self, rows=None):
        if rows is None:
            rows = ExchangeRate.objects.all()
        self._rates = {}
        self._updated = {}
        for row in rows:
            self._rates[row.currency_pair] = row.rate
            self._updated[row.currency_pair] = row.last_updated

    # -- internals ---------------------------------------------------------

    def _stored(self, from_currency, to_currency):
        """
        Look a pair up, falling back to its inverse so only one direction per
        pair needs storing (USD_EUR covers EUR_USD too).

        Returns (rate, [pairs consulted]) or (None, []).
        """
        direct_pair = f'{from_currency}_{to_currency}'
        rate = self._rates.get(direct_pair)
        if rate is not None:
            return rate, [direct_pair]

        inverse_pair = f'{to_currency}_{from_currency}'
        inverse = self._rates.get(inverse_pair)
        if inverse is not None and inverse != 0:
            return (Decimal('1') / inverse).quantize(RATE_DP, rounding=ROUND_HALF_UP), [inverse_pair]

        return None, []

    def _oldest(self, pairs):
        stamps = [self._updated[p] for p in pairs if self._updated.get(p) is not None]
        return min(stamps) if stamps else None

    # -- public ------------------------------------------------------------

    def resolve(self, from_currency, to_currency):
        """
        Return (rate, last_updated) for the conversion, where last_updated is
        the oldest timestamp among the rows consulted (None for the identity
        pair, which needs no data).

        Three strategies, in order:
          1. the stored pair            -- USD_EUR
          2. its inverse                -- EUR_USD -> 1 / USD_EUR
          3. a cross rate via the pivot -- EUR_GBP -> USD_GBP / USD_EUR

        (3) matters because fetch_exchange_rates only ever stores rates
        against BASE_CURRENCY, so a pair like EUR_GBP is never on file in
        either direction. Without triangulation, every subscription whose
        currency differs from a non-USD user's base_currency gets skipped.

        Raises ValueError when no strategy closes the loop.
        """
        if from_currency == to_currency:
            return Decimal('1'), None

        direct, pairs = self._stored(from_currency, to_currency)
        if direct is not None:
            return direct, self._oldest(pairs)

        # Cross rate through the pivot. Both legs are stored against
        # BASE_CURRENCY, so dividing them cancels it out.
        if BASE_CURRENCY not in (from_currency, to_currency):
            base_to_from, from_pairs = self._stored(BASE_CURRENCY, from_currency)
            base_to_to, to_pairs = self._stored(BASE_CURRENCY, to_currency)
            # Falsy covers both None and a zero rate (no division by zero).
            if base_to_from and base_to_to:
                rate = (base_to_to / base_to_from).quantize(RATE_DP, rounding=ROUND_HALF_UP)
                return rate, self._oldest(from_pairs + to_pairs)

        raise ValueError(f'No exchange rate available for {from_currency}_{to_currency}')


def get_exchange_rate(from_currency: str, to_currency: str) -> Decimal:
    """
    Resolve a single currency_pair rate. One query.

    For anything that converts more than one subscription, build a RateTable
    once and call .resolve() instead -- see ProjectionsView.

    No cache layer for v1: the table itself is the "most recently synced
    rate" source of truth (see last_updated). If you add Redis later, this
    and RateTable.__init__ are the places to touch.
    """
    rate, _ = RateTable().resolve(from_currency, to_currency)
    return rate


def normalize_to_monthly(subscription: Subscription) -> Decimal:
    """Reduce any billing_cycle to a single "cost per month" figure."""
    amount = subscription.amount

    if subscription.billing_cycle == 'monthly':
        return amount

    if subscription.billing_cycle == 'yearly':
        return (amount / Decimal('12')).quantize(TWO_DP, rounding=ROUND_HALF_UP)

    if subscription.billing_cycle == 'custom' and subscription.custom_interval_days:
        daily_rate = amount / Decimal(subscription.custom_interval_days)
        return (daily_rate * AVG_DAYS_PER_MONTH).quantize(TWO_DP, rounding=ROUND_HALF_UP)

    return amount


class ProjectionsView(APIView):
    """
    GET /api/analytics/projections/

    Normalizes every active subscription into the user's base_currency,
    then projects the combined monthly spend out across 3/6/12-month
    horizons, per PRD 3.4.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        user = request.user
        base_currency = user.base_currency

        subscriptions = (
            Subscription.objects.filter(user=user, is_active=True)
            .select_related('category')
        )

        # One query for every rate this request could possibly need, instead
        # of one to two per subscription.
        rates = RateTable()
        stale_cutoff = timezone.now() - timedelta(days=settings.EXCHANGE_RATE_STALE_AFTER_DAYS)

        line_items = []
        missing_rates = set()
        stale_currencies = set()
        total_monthly = Decimal('0')

        for sub in subscriptions:
            try:
                rate, last_updated = rates.resolve(sub.original_currency, base_currency)
            except ValueError:
                missing_rates.add(sub.original_currency)
                continue

            # A rate synced months ago is otherwise served as though it were
            # current, with no signal to the user that the number is old.
            if last_updated is not None and last_updated < stale_cutoff:
                stale_currencies.add(sub.original_currency)

            monthly_normalized = normalize_to_monthly(sub)
            monthly_in_base = (monthly_normalized * rate).quantize(TWO_DP, rounding=ROUND_HALF_UP)
            total_monthly += monthly_in_base

            line_items.append({
                'id': sub.id,
                'name': sub.name,
                'category': sub.category.name if sub.category else None,
                'monthly_cost_base_currency': str(monthly_in_base),
            })

        today = date.today()
        horizons = {}
        for months in (3, 6, 12):
            horizons[f'{months}_month'] = {
                'through': (today + relativedelta(months=months)).isoformat(),
                'projected_total': str((total_monthly * months).quantize(TWO_DP, rounding=ROUND_HALF_UP)),
            }

        warnings = [f'Missing exchange rate for {c}' for c in sorted(missing_rates)]
        warnings += [
            f'Exchange rate for {c} has not been updated in over '
            f'{settings.EXCHANGE_RATE_STALE_AFTER_DAYS} days'
            for c in sorted(stale_currencies)
        ]

        return Response({
            'base_currency': base_currency,
            'monthly_total': str(total_monthly.quantize(TWO_DP, rounding=ROUND_HALF_UP)),
            'projections': horizons,
            'line_items': line_items,
            'warnings': warnings,
        })
