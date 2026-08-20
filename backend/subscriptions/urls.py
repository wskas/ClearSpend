from django.urls import include, path
from rest_framework.routers import DefaultRouter
 
from .views import *
 
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
    # User profile management
    path('user/profile/', ProfileView.as_view(), name='profile'),
    # Analytics projections
    path('analytics/projections/', ProjectionsView.as_view(), name='projections'),
    # Include the router URLs for subscriptions and categories
    path('', include(router.urls)),
]
