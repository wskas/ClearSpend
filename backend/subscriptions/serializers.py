import re

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Category, Subscription

User = get_user_model()


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
        if not re.match(r'^[A-Z]{3}$', value.upper()):
            raise serializers.ValidationError('base_currency must be a 3-letter ISO code, e.g. USD.')
        return value.upper()


class CategorySerializer(serializers.ModelSerializer):
    """GET/POST /api/categories/"""

    class Meta:
        model = Category
        fields = ['id', 'name', 'hex_color_code']

    def validate_hex_color_code(self, value):
        if not re.match(r'^#[0-9A-Fa-f]{6}$', value):
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
        if not re.match(r'^[A-Z]{3}$', value.upper()):
            raise serializers.ValidationError('original_currency must be a 3-letter ISO code, e.g. USD.')
        return value.upper()

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
        return attrs

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)