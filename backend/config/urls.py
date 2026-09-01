import os

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('api/', include('subscriptions.urls')),
]

# The admin is a session-authenticated, fully-privileged surface sitting on
# the same host as the API. Hardening its session cookie is a smaller win
# than not exposing it at all, so it is opt-out here.
#
# Set ADMIN_ENABLED=False on any deployment that doesn't need it. Where it is
# needed, move it off the default path (ADMIN_URL) so it isn't found by
# scanners, and restrict it by IP at the proxy as well -- a non-default path
# is obscurity, not a control.
ADMIN_ENABLED = os.environ.get('ADMIN_ENABLED', 'True').strip().lower() in ('1', 'true', 'yes', 'on')
ADMIN_URL = os.environ.get('ADMIN_URL', 'admin/').strip().lstrip('/')

if ADMIN_ENABLED:
    urlpatterns.insert(0, path(ADMIN_URL, admin.site.urls))
