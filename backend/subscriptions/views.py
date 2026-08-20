from datetime import date
from decimal import Decimal, ROUND_HALF_UP
 
from dateutil.relativedelta import relativedelta
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
 
from .models import Category, ExchangeRate, Subscription
from .serializers import (
    CategorySerializer,
    RegisterSerializer,
    SubscriptionSerializer,
    UserProfileSerializer,
)
 
TWO_DP = Decimal('0.01')
# 365.25 / 12 -- accounts for leap years when converting a custom daily
# interval into an "average" monthly figure (PRD 3.4).
AVG_DAYS_PER_MONTH = Decimal('30.4375')
 
 
# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
 
class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/"""
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonRateThrottle]
    serializer_class = RegisterSerializer
 
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserProfileSerializer(user).data, status=status.HTTP_201_CREATED)
 
 
class CustomTokenObtainPairView(TokenObtainPairView):
    """POST /api/auth/token/  (login)"""
    throttle_classes = [AnonRateThrottle]
 
 
class CustomTokenRefreshView(TokenRefreshView):
    """POST /api/auth/token/refresh/"""
    throttle_classes = [AnonRateThrottle]
 
 
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
# Analytics / projections
# ---------------------------------------------------------------------------
 
def get_exchange_rate(from_currency: str, to_currency: str) -> Decimal:
    """
    Resolve a currency_pair rate straight from the ExchangeRate table, with
    automatic inverse-pair lookup so you only need to store one direction
    per pair (e.g. USD_EUR covers EUR_USD too).
 
    No cache layer for v1 -- the table itself is the "most recently synced
    rate" source of truth (see last_updated). If you add Redis later, this
    is the one function to touch: check cache first, fall back to this
    query, and populate the cache on miss.
    """
    if from_currency == to_currency:
        return Decimal('1')
 
    pair = f'{from_currency}_{to_currency}'
    rate_obj = ExchangeRate.objects.filter(currency_pair=pair).first()
    if rate_obj is not None:
        return rate_obj.rate
 
    inverse_pair = f'{to_currency}_{from_currency}'
    inverse_obj = ExchangeRate.objects.filter(currency_pair=inverse_pair).first()
    if inverse_obj is not None and inverse_obj.rate != 0:
        return (Decimal('1') / inverse_obj.rate).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
 
    raise ValueError(f'No exchange rate available for {pair}')
 
 
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
 
        line_items = []
        missing_rates = set()
        total_monthly = Decimal('0')
 
        for sub in subscriptions:
            try:
                rate = get_exchange_rate(sub.original_currency, base_currency)
            except ValueError:
                missing_rates.add(sub.original_currency)
                continue
 
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
 
        return Response({
            'base_currency': base_currency,
            'monthly_total': str(total_monthly.quantize(TWO_DP, rounding=ROUND_HALF_UP)),
            'projections': horizons,
            'line_items': line_items,
            'warnings': [f'Missing exchange rate for {c}' for c in sorted(missing_rates)],
        })