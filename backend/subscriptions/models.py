from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from decimal import Decimal

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

    def __str__(self):
        return f"{self.name} - {self.user.email}"

class Subscription(models.Model):
    BILLING_CYCLE_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='subscriptions')
    
    name = models.CharField(max_length=255)
    # Using DecimalField and validating amount > 0 to prevent floating-point errors and enforce security
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    original_currency = models.CharField(max_length=3)
    billing_cycle = models.CharField(max_length=20, choices=BILLING_CYCLE_CHOICES, default='monthly')
    
    
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.original_currency} {self.amount})"

class ExchangeRate(models.Model):
    currency_pair = models.CharField(max_length=7, unique=True, help_text="e.g., USD_EUR")
    rate = models.DecimalField(max_digits=12, decimal_places=6)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.currency_pair}: {self.rate}"