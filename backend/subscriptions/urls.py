from django.urls import include, path
from rest_framework.routers import DefaultRouter

# Imported explicitly rather than with `import *`: a wildcard makes it
# impossible to tell from this file which views are actually routed, and
# lets a newly added view become reachable with no diff to the import line.
from .views import (
    CategoryViewSet,
    CurrenciesView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    LogoutAllView,
    LogoutView,
    ProfileView,
    ProjectionsView,
    RegisterView,
    SubscriptionViewSet,
)

router = DefaultRouter()
router.register(r'subscriptions', SubscriptionViewSet, basename='subscription')
router.register(r'categories', CategoryViewSet, basename='category')

urlpatterns = [
    # Register user
    path('auth/register/', RegisterView.as_view(), name='register'),
    # Login to get JWT token
    path('auth/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    # Refresh JWT token
    path('auth/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    # Revoke one refresh token (public -- the token is its own credential)
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    # Revoke every session for the caller (bumps token_version)
    path('auth/logout-all/', LogoutAllView.as_view(), name='logout_all'),
    # User profile management
    path('user/profile/', ProfileView.as_view(), name='profile'),
    # Supported currency list (public -- the register form needs it)
    path('currencies/', CurrenciesView.as_view(), name='currencies'),
    # Analytics projections
    path('analytics/projections/', ProjectionsView.as_view(), name='projections'),
    # Include the router URLs for subscriptions and categories
    path('', include(router.urls)),
]
