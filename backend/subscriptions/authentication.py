"""
Authentication class wired in as DRF's default (see settings.REST_FRAMEWORK).
"""

import logging

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from .tokens import TOKEN_VERSION_CLAIM

logger = logging.getLogger('clearspend.security')


class VersionedJWTAuthentication(JWTAuthentication):
    """
    Stock JWT authentication plus a `token_version` check.

    This is what makes revocation cover access tokens. SimpleJWT's blacklist
    is only consulted on the refresh path, so without this a token stolen via
    XSS keeps working for the remainder of its lifetime even after the user
    logs out and even after every refresh token is blacklisted.

    Cost is nil: the parent already fetches the user row to authenticate, so
    the version comparison rides along on a read that was happening anyway.
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)

        claimed = validated_token.get(TOKEN_VERSION_CLAIM)
        if claimed is None or int(claimed) != user.token_version:
            # Covers three cases: a token issued before this claim existed, a
            # token issued before a "log out everywhere", and a forged claim.
            logger.info(
                'Rejected token for user %s: token_version %r != %r',
                user.pk, claimed, user.token_version,
            )
            raise AuthenticationFailed(
                'Token has been revoked.', code='token_revoked'
            )

        return user
