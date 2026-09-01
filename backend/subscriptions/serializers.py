import re
from datetime import date

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.settings import api_settings

from .constants import SUPPORTED_CURRENCIES
from .models import Category, Subscription
from .tokens import TOKEN_VERSION_CLAIM, VersionedRefreshToken

User = get_user_model()

# `$` also matches immediately before a trailing newline in Python, so
# `re.match(r'^[A-Z]{3}$', 'USD\n')` succeeds. `\Z` is the true end anchor.
# Today the model's max_length happens to reject the 4-character string
# first, but a validator should not depend on an incidental length check --
# the hex-colour value is interpolated into inline styles downstream.
CURRENCY_RE = re.compile(r'^[A-Z]{3}\Z')
HEX_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}\Z')

# Plausibility bounds for Subscription.start_date. Generous on purpose -- the
# point is to reject values no subscription could have (year 1, year 3000),
# not to second-guess someone backdating a long-running service.
START_DATE_MAX_YEARS_PAST = 50
START_DATE_MAX_YEARS_FUTURE = 10


def validate_currency_code(value):
    """
    Shared by every currency field. Constrained to the currencies we actually
    hold FX rates for -- anything else silently lands in the projections
    `warnings` array forever, which reads as a bug rather than a rejection.
    """
    code = (value or '').strip().upper()
    if not CURRENCY_RE.match(code):
        raise serializers.ValidationError(
            'Must be a 3-letter ISO currency code, e.g. USD.'
        )
    if code not in SUPPORTED_CURRENCIES:
        raise serializers.ValidationError(
            f'Unsupported currency. Choose one of: {", ".join(SUPPORTED_CURRENCIES)}.'
        )
    return code


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class ClearSpendTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Issues tokens stamped with the user's current token_version."""
    token_class = VersionedRefreshToken


class ClearSpendTokenRefreshSerializer(TokenRefreshSerializer):
    """
    Refresh with a token_version check.

    The refresh endpoint is unauthenticated, so DRF's authentication class
    never runs here. Without this check, bumping token_version would revoke
    access tokens but leave the refresh token able to mint fresh ones --
    "log out everywhere" would not actually log anyone out.
    """
    token_class = VersionedRefreshToken

    def validate(self, attrs):
        data = super().validate(attrs)

        # super() already parsed and verified the token; re-read the claim
        # from the parsed payload rather than trusting the raw input.
        refresh = self.token_class(attrs['refresh'], verify=False)
        user_id = refresh.payload.get(api_settings.USER_ID_CLAIM)
        claimed = refresh.payload.get(TOKEN_VERSION_CLAIM)

        current = (
            User.objects.filter(pk=user_id)
            .values_list('token_version', flat=True)
            .first()
        )
        if current is None or claimed is None or int(claimed) != current:
            raise AuthenticationFailed('Token has been revoked.', code='token_revoked')

        return data


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class RegisterSerializer(serializers.ModelSerializer):
    """POST /api/auth/register/"""
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'password', 'base_currency']
        extra_kwargs = {
            'username': {'required': True},
            'base_currency': {'required': False},
        }

    def validate_base_currency(self, value):
        return validate_currency_code(value)

    def create(self, validated_data):
        # create_user handles password hashing correctly (set_password),
        # unlike ModelSerializer's default .create() which would store it plain.
        return User.objects.create_user(**validated_data)


class UserProfileSerializer(serializers.ModelSerializer):
    """GET/PATCH /api/user/profile/"""

    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'base_currency']
        read_only_fields = ['id', 'email']

    def validate_base_currency(self, value):
        return validate_currency_code(value)


# ---------------------------------------------------------------------------
# Categories & subscriptions
# ---------------------------------------------------------------------------

class CategorySerializer(serializers.ModelSerializer):
    """GET/POST /api/categories/"""

    class Meta:
        model = Category
        fields = ['id', 'name', 'hex_color_code']

    def validate_hex_color_code(self, value):
        if not HEX_COLOR_RE.match(value or ''):
            raise serializers.ValidationError('Must be a valid hex color, e.g. #3b82f6.')
        return value

    def validate_name(self, value):
        user = self.context['request'].user
        qs = Category.objects.filter(user=user, name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('You already have a category with this name.')
        return value

    def validate(self, attrs):
        if self.instance is None:
            user = self.context['request'].user
            cap = settings.MAX_CATEGORIES_PER_USER
            if Category.objects.filter(user=user).count() >= cap:
                raise serializers.ValidationError(
                    f'Category limit reached ({cap}). Delete one before adding another.'
                )
        return attrs


class SubscriptionSerializer(serializers.ModelSerializer):
    """GET/POST /api/subscriptions/, GET/PUT/PATCH/DELETE /api/subscriptions/<id>/"""

    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.none(), required=False, allow_null=True
    )
    next_renewal_date = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            'id', 'name', 'amount', 'original_currency', 'category',
            'billing_cycle', 'custom_interval_days', 'is_active',
            'start_date', 'next_renewal_date',
        ]
        read_only_fields = ['id', 'is_active', 'next_renewal_date']

    def get_next_renewal_date(self, obj):
        renewal = obj.get_next_renewal_date()
        return renewal.isoformat() if renewal else None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request is not None:
            # Scope the category dropdown to the requesting user's own
            # categories only -- prevents cross-user category assignment.
            self.fields['category'].queryset = Category.objects.filter(user=request.user)

    def validate_original_currency(self, value):
        return validate_currency_code(value)

    def validate_start_date(self, value):
        """
        Bound start_date to a plausible range.

        A subscription tracker has no use for a start date in the year 1 or in
        the year 3000, and leaving the field unbounded meant a client could
        store one: get_next_renewal_date then had to walk from that date to
        today. That method is now O(1), so this is defence in depth rather than
        the sole protection -- but it also just rejects obvious nonsense before
        it reaches the database.
        """
        if value is None:
            return value

        today = date.today()
        earliest = today - relativedelta(years=START_DATE_MAX_YEARS_PAST)
        latest = today + relativedelta(years=START_DATE_MAX_YEARS_FUTURE)

        if value < earliest:
            raise serializers.ValidationError(
                f'Start date cannot be earlier than {earliest.isoformat()}.'
            )
        if value > latest:
            raise serializers.ValidationError(
                f'Start date cannot be later than {latest.isoformat()}.'
            )
        return value

    def validate(self, attrs):
        billing_cycle = attrs.get('billing_cycle', getattr(self.instance, 'billing_cycle', None))
        custom_days = attrs.get('custom_interval_days', getattr(self.instance, 'custom_interval_days', None))

        if billing_cycle == 'custom' and not custom_days:
            raise serializers.ValidationError({
                'custom_interval_days': 'Required when billing_cycle is "custom".'
            })
        if billing_cycle != 'custom' and custom_days:
            raise serializers.ValidationError({
                'custom_interval_days': 'Only allowed when billing_cycle is "custom".'
            })

        if self.instance is None:
            # ProjectionsView walks every active subscription on each request,
            # so an uncapped row count is an authenticated user's lever on
            # their own request cost.
            user = self.context['request'].user
            cap = settings.MAX_SUBSCRIPTIONS_PER_USER
            if Subscription.objects.filter(user=user).count() >= cap:
                raise serializers.ValidationError(
                    f'Subscription limit reached ({cap}). Delete one before adding another.'
                )

        return attrs

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
