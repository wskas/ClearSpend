import math
from datetime import date, timedelta

from django.db import models
from django.db.models import F
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from decimal import Decimal
from dateutil.relativedelta import relativedelta

class User(AbstractUser):
    email = models.EmailField(unique=True)
    base_currency = models.CharField(max_length=3, default='USD')

    # Stamped into every issued token and re-checked on every authenticated
    # request. Bumping it invalidates all outstanding tokens for this user
    # instantly -- access *and* refresh. The token blacklist alone cannot do
    # this: it is only ever consulted for refresh tokens, so a stolen access
    # token stays valid for its full lifetime after a logout.
    # Bump via User.revoke_tokens(); see views.LogoutAllView.
    token_version = models.PositiveIntegerField(default=0)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

    def revoke_tokens(self):
        """
        Invalidate every token ever issued to this user. Use on "log out
        everywhere", on password change, and on suspected compromise.
        """
        User.objects.filter(pk=self.pk).update(token_version=F('token_version') + 1)
        self.refresh_from_db(fields=['token_version'])
        return self.token_version

class Category(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    hex_color_code = models.CharField(max_length=7, help_text="e.g., #3b82f6")

    #User and name combination must be unique to prevent duplicate category names for the same user.
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'name'], 
                name='unique_user_category_name'
            )
        ]

    def __str__(self):
        return f"{self.name} - {self.user.email}"

class Subscription(models.Model):
    BILLING_CYCLE_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
        ('custom', 'Custom'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='subscriptions')

    name = models.CharField(max_length=255)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    original_currency = models.CharField(max_length=3)
    billing_cycle = models.CharField(max_length=20, choices=BILLING_CYCLE_CHOICES, default='monthly')

    custom_interval_days = models.PositiveIntegerField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    # Anchor for renewal math. Nullable so pre-existing rows migrate cleanly;
    # get_next_renewal_date() returns None until it's set.
    start_date = models.DateField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.original_currency} {self.amount})"

    def get_next_renewal_date(self, today=None):
        """
        The next billing date on or after `today`, projected forward from
        start_date across the billing cycle. Returns None if start_date is
        unset. Mirrors the cycle handling in views.normalize_to_monthly.
        """
        if not self.start_date:
            return None

        if today is None:
            today = date.today()

        if self.start_date >= today:
            return self.start_date

        # Both branches below compute the period count arithmetically rather
        # than looping. The loops they replace cost one relativedelta addition
        # per elapsed period, and this method is a SerializerMethodField
        # evaluated for every row of every list page -- so a single row with a
        # far-past start_date made listing arbitrarily expensive. Validation
        # bounds new rows, but only this makes already-stored rows safe.
        #
        # Anchoring each step to start_date also fixes a drift bug. Adding one
        # month at a time compounded end-of-month clamping: Jan 31 became
        # Feb 28 and then stayed on the 28th forever. Anchored, the sequence is
        # Jan 31 -> Feb 28 -> Mar 31, which is how billing on the 31st behaves.
        if self.billing_cycle == 'monthly':
            elapsed = ((today.year - self.start_date.year) * 12
                       + today.month - self.start_date.month)
            next_date = self.start_date + relativedelta(months=elapsed)
            if next_date < today:
                next_date = self.start_date + relativedelta(months=elapsed + 1)
            return next_date

        if self.billing_cycle == 'yearly':
            elapsed = today.year - self.start_date.year
            next_date = self.start_date + relativedelta(years=elapsed)
            if next_date < today:
                next_date = self.start_date + relativedelta(years=elapsed + 1)
            return next_date

        if self.billing_cycle == 'custom' and self.custom_interval_days:
            # Jump straight to the right period instead of looping day-by-day.
            days_elapsed = (today - self.start_date).days
            periods = math.ceil(days_elapsed / self.custom_interval_days)
            return self.start_date + timedelta(days=periods * self.custom_interval_days)

        return None

class ExchangeRate(models.Model):
    currency_pair = models.CharField(max_length=7, unique=True, help_text="e.g., USD_EUR")
    rate = models.DecimalField(max_digits=12, decimal_places=6)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.currency_pair}: {self.rate}"

class RevokedRefreshToken(models.Model):
    """
    Refresh tokens revoked by an explicit logout, as opposed to ones
    blacklisted as a side effect of rotation.

    The distinction matters because of the rotation grace window (see
    tokens.VersionedRefreshToken.check_blacklist). That window exists to stop
    two tabs refreshing in the same instant from knocking each other out --
    but applied indiscriminately it would also give a just-logged-out token
    a few more seconds of life, which is precisely the wrong answer for the
    one operation whose entire purpose is immediate revocation.

    Rows here are read only on the refresh path and can be pruned alongside
    `manage.py flushexpiredtokens`.
    """
    jti = models.CharField(max_length=255, unique=True, db_index=True)
    revoked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.jti} revoked at {self.revoked_at}'
