"""
Token classes layered over SimpleJWT.

Three behaviours are added here:

1. A `token_version` claim, so revocation can cover access tokens. The stock
   blacklist is only ever consulted for refresh tokens, which means after a
   logout a stolen access token stays valid for its full lifetime.
2. A short grace window on the rotation blacklist, so two browser tabs
   refreshing in the same instant do not knock each other out.
3. Overlapping signing keys, so JWT_SIGNING_KEY can be rotated routinely
   without logging every user out (see RotatingKeyTokenBackend).
"""

import jwt
from django.conf import settings
from django.core.signals import setting_changed
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt import settings as jwt_settings
from rest_framework_simplejwt.backends import TokenBackend
from rest_framework_simplejwt.exceptions import (
    TokenBackendError,
    TokenBackendExpiredToken,
    TokenError,
)
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

TOKEN_VERSION_CLAIM = 'token_version'


class RotatingKeyTokenBackend(TokenBackend):
    """
    SimpleJWT's backend, but verification also accepts retired keys.

    Stock SimpleJWT holds exactly one HMAC key, so changing it invalidates
    every outstanding token at once -- which makes routine rotation a
    global-logout event nobody will schedule. Here tokens are always *signed*
    with the current key, and a token whose signature fails against it is
    retried against each key in JWT_PREVIOUS_SIGNING_KEYS. A session that
    refreshes during the overlap is re-signed with the new key, so once
    REFRESH_TOKEN_LIFETIME has passed the old key can be dropped with no one
    noticing.

    Only a *signature* mismatch falls through to the next key. Expiry, a bad
    issuer/audience, or a disallowed algorithm is a verdict on the token
    itself and is final regardless of which key would have matched.
    """

    def __init__(self, *args, previous_keys=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.previous_keys = tuple(previous_keys)

    def _decode_with(self, token, key, verify):
        return jwt.decode(
            token,
            key,
            algorithms=[self.algorithm],
            audience=self.audience,
            issuer=self.issuer,
            leeway=self.get_leeway(),
            options={
                'verify_aud': self.audience is not None,
                'verify_signature': verify,
                # Tokens we issue always carry these; a token lacking them
                # was not minted by this deployment's current config.
                'require': ['exp', *(['iss'] if self.issuer else []),
                            *(['aud'] if self.audience else [])],
            },
        )

    def decode(self, token, verify=True):
        keys = [self.prepared_signing_key]
        keys += [self._prepare_key(k) for k in self.previous_keys]
        try:
            for i, key in enumerate(keys):
                try:
                    return self._decode_with(token, key, verify)
                except jwt.InvalidSignatureError:
                    if i == len(keys) - 1:
                        raise
        except jwt.InvalidAlgorithmError as e:
            raise TokenBackendError(_('Invalid algorithm specified')) from e
        except jwt.ExpiredSignatureError as e:
            raise TokenBackendExpiredToken(_('Token is expired')) from e
        except jwt.InvalidTokenError as e:
            raise TokenBackendError(_('Token is invalid')) from e


_backend = None


def get_token_backend():
    global _backend
    if _backend is None:
        # Through the module, not the imported name: SimpleJWT *rebinds*
        # api_settings when SIMPLE_JWT changes, so a direct import goes stale.
        api_settings = jwt_settings.api_settings
        _backend = RotatingKeyTokenBackend(
            api_settings.ALGORITHM,
            api_settings.SIGNING_KEY,
            api_settings.VERIFYING_KEY,
            api_settings.AUDIENCE,
            api_settings.ISSUER,
            api_settings.JWK_URL,
            api_settings.LEEWAY,
            api_settings.JSON_ENCODER,
            previous_keys=getattr(settings, 'JWT_PREVIOUS_SIGNING_KEYS', ()),
        )
    return _backend


def _reset_backend(*, setting, **kwargs):
    # Keeps override_settings in tests honest; SimpleJWT's own module-level
    # backend has the same staleness problem and simply ignores it.
    global _backend
    if setting in ('SIMPLE_JWT', 'JWT_PREVIOUS_SIGNING_KEYS'):
        _backend = None


setting_changed.connect(_reset_backend)


class RotatingKeyMixin:
    def get_token_backend(self):
        return get_token_backend()


class VersionedAccessToken(RotatingKeyMixin, AccessToken):
    """Wired in via SIMPLE_JWT['AUTH_TOKEN_CLASSES']."""


class VersionedRefreshToken(RotatingKeyMixin, RefreshToken):
    """
    A refresh token carrying the issuing user's `token_version`.

    The claim propagates to derived access tokens for free: `access_token`
    copies every claim except those in `no_copy_claims`, and rotation reuses
    the same payload with a fresh jti, so both token types stay stamped.
    """

    access_token_class = VersionedAccessToken

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
