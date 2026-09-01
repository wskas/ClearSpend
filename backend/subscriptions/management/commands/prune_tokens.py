from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from subscriptions.models import RevokedRefreshToken


class Command(BaseCommand):
    """
    Delete token bookkeeping rows that can no longer affect a decision.

    Rotation writes an OutstandingToken *and* a BlacklistedToken roughly once
    per access-token lifetime per active session -- with 15-minute access
    tokens that is ~96 rows per user per day, forever. Nothing prunes them by
    default, which is a slow-motion self-inflicted outage on the database.

    Schedule this daily, next to fetch_exchange_rates:
        python manage.py prune_tokens
    """
    help = 'Delete expired outstanding/blacklisted tokens and stale revocation records.'

    def handle(self, *args, **options):
        # Ships with the token_blacklist app; drops OutstandingToken rows
        # whose expires_at has passed (cascading to their BlacklistedToken).
        call_command('flushexpiredtokens')

        # A revocation record only matters while the token it names could
        # still be presented, so anything older than the refresh lifetime is
        # dead weight. Uses the row's own age rather than the token's exp,
        # which is not stored here.
        from django.conf import settings
        lifetime = settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME']
        cutoff = timezone.now() - lifetime

        deleted, _ = RevokedRefreshToken.objects.filter(revoked_at__lt=cutoff).delete()

        self.stdout.write(self.style.SUCCESS(
            f'Flushed expired tokens; removed {deleted} stale revocation record(s).'
        ))
