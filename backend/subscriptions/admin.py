from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Category, ExchangeRate, Subscription, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """
    Django's stock UserAdmin assumes USERNAME_FIELD == 'username'. Against
    this model its add form collects a username and no email -- so the
    required unique field is missing, base_currency is never offered, and the
    account is created without passing through RegisterSerializer (skipping
    the currency validator entirely). Redefine both fieldsets explicitly.
    """
    ordering = ('email',)
    list_display = ('email', 'username', 'base_currency', 'is_staff', 'is_active')
    search_fields = ('email', 'username')

    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name')}),
        ('Preferences', {'fields': ('base_currency',)}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        # Read-only: revoking sessions is an action, not a number to hand-edit.
        ('Sessions', {'fields': ('token_version',)}),
    )
    readonly_fields = ('token_version',)

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'base_currency', 'password1', 'password2'),
        }),
    )

    actions = ['revoke_all_sessions']

    @admin.action(description='Revoke all sessions for selected users')
    def revoke_all_sessions(self, request, queryset):
        for user in queryset:
            user.revoke_tokens()
        self.message_user(request, f'Revoked sessions for {queryset.count()} user(s).')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'hex_color_code')
    search_fields = ('name',)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'amount', 'original_currency', 'billing_cycle', 'is_active')
    list_filter = ('is_active', 'billing_cycle', 'original_currency')
    search_fields = ('name',)


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ('currency_pair', 'rate', 'last_updated')
    readonly_fields = ('last_updated',)
