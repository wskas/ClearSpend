import math
from datetime import date, timedelta

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from decimal import Decimal
from dateutil.relativedelta import relativedelta

class User(AbstractUser):
    email = models.EmailField(unique=True)
    base_currency = models.CharField(max_length=3, default='USD')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

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

        if self.billing_cycle == 'monthly':
            next_date = self.start_date
            while next_date < today:
                next_date += relativedelta(months=1)
            return next_date

        if self.billing_cycle == 'yearly':
            next_date = self.start_date
            while next_date < today:
                next_date += relativedelta(years=1)
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