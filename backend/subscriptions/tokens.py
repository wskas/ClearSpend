"""
Token classes layered over SimpleJWT.

Two behaviours are added here:

1. A `token_version` claim, so revocation can cover access tokens. The stock
   blacklist is only ever consulted for refresh tokens, which means after a
   logout a stolen access token stays valid for its full lifetime.
2. A short grace window on the rotation blacklist, so two browser tabs
   refreshing in the same instant do not knock each other out.
"""

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

TOKEN_VERSION_CLAIM = 'token_version'


class VersionedRefreshToken(RefreshToken):
    """
    A refresh token carrying the issuing user's `token_version`.

    The claim propagates to derived access tokens for free: `access_token`
    copies every claim except those in `no_copy_claims`, and rotation reuses
    the same payload with a fresh jti, so both token types stay stamped.
    """

    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        token[TOKEN_VERSION_CLAIM] = user.token_version
        return token

    def check_blacklist(self):
        """
        Reject blacklisted tokens, but tolerate one that was blacklisted
        within the last REFRESH_REUSE_GRACE_SECONDS.

        Why the window exists: rotation blacklists the presented token. Two
        tabs whose access tokens expire together both read the same refresh
        token out of shared localStorage and both present it. Strictly, the
        second is a reuse and gets rejected -- and because the frontend
        responds to a failed refresh by clearing localStorage, that logs the
        *winning* tab out too on its next request. The window keeps genuine
        reuse-detection (a token replayed minutes or hours later is still
        rejected) while absorbing the race.

        The frontend also holds a cross-tab lock so only one tab refreshes;
        this is the backstop for when BroadcastChannel is unavailable or the
        tabs are in different browser profiles.

        The window applies to rotation only. A token revoked by an explicit
        logout is rejected immediately -- extending grace to it would hand a
        few extra seconds of life to the one operation whose whole purpose is
        immediate revocation.
        """
        from .models import RevokedRefreshToken

        jti = self.payload[api_settings.JTI_CLAIM]

        blacklisted_at = (
            BlacklistedToken.objects
            .filter(token__jti=jti)
            .values_list('blacklisted_at', flat=True)
            .first()
        )
        if blacklisted_at is None:
            return

        grace = getattr(settings, 'REFRESH_REUSE_GRACE_SECONDS', 0)
        if (
            grace
            and (timezone.now() - blacklisted_at).total_seconds() <= grace
            and not RevokedRefreshToken.objects.filter(jti=jti).exists()
        ):
            return

        raise TokenError(_('Token is blacklisted'))
