import logging
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from subscriptions.constants import BASE_CURRENCY, SUPPORTED_CURRENCIES
from subscriptions.models import ExchangeRate

logger = logging.getLogger('subscriptions')


class Command(BaseCommand):
    """
    Manual/cron replacement for the Celery beat task described in the PRD.

    Run with:
        python manage.py fetch_exchange_rates

    Wire this up to a system cron entry (or a scheduled task on your host)
    to hit it daily until Celery is introduced. When you do add Celery,
    this same body drops straight into a @shared_task.

    Exits non-zero on failure so cron and uptime monitoring can actually see
    a broken sync -- a bare `return` reports success to the shell.
    """
    help = 'Fetch latest FX rates from the external provider and upsert into ExchangeRate.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Accept rates that fail the relative-deviation sanity check.',
        )

    def handle(self, *args, **options):
        # Frankfurter (api.frankfurter.dev): no API key, no signup, no quota.
        # GET /v2/rates?base=USD&quotes=EUR,GBP,... -> a FLAT ARRAY, one row
        # per quote currency, e.g. [{"quote": "EUR", "rate": 0.8739, ...}, ...]
        # (NOT a {"rates": {...}} object -- that was the v1 shape.)
        #
        # The https:// scheme is enforced at settings load: these numbers are
        # an input to the money path, so the transport has to be authenticated.
        url = f'{settings.EXCHANGE_RATE_API_BASE_URL}/v2/rates'
        quote_currencies = [c for c in SUPPORTED_CURRENCIES if c != BASE_CURRENCY]

        try:
            response = requests.get(
                url,
                params={'base': BASE_CURRENCY, 'quotes': ','.join(quote_currencies)},
                timeout=10,
            )
            response.raise_for_status()
            rows = response.json()
        except (requests.RequestException, ValueError) as exc:
            # Deliberately don't touch existing rows -- get_exchange_rate()
            # keeps serving the last successfully synced values, satisfying
            # the PRD's "graceful fallback" requirement.
            logger.error('FX sync failed: %s', exc)
            raise CommandError(f'Failed to fetch FX rates: {exc}')

        if not isinstance(rows, list):
            raise CommandError(
                f'Unexpected response shape from {url}: expected a list, got {type(rows).__name__}.'
            )

        # Reshape the flat array into a {quote_currency: rate} lookup.
        try:
            incoming = {row['quote']: Decimal(str(row['rate'])) for row in rows}
        except (KeyError, TypeError, InvalidOperation) as exc:
            raise CommandError(f'Malformed rate row in response from {url}: {exc}')

        stored = dict(
            ExchangeRate.objects.values_list('currency_pair', 'rate')
        )

        max_deviation = Decimal(str(settings.EXCHANGE_RATE_MAX_DEVIATION))
        accepted = {}
        rejected = []

        for currency in quote_currencies:
            if currency not in incoming:
                continue

            pair = f'{BASE_CURRENCY}_{currency}'
            new_rate = incoming[currency]

            if new_rate <= 0:
                rejected.append(f'{pair}: non-positive rate {new_rate}')
                continue

            # Relative sanity check. An absolute window cannot do this job:
            # IDR/USD sits around 16,000, so a 100x unit error still lands
            # comfortably inside any plausible fixed range.
            previous = stored.get(pair)
            if previous and not options['force']:
                deviation = abs(new_rate - previous) / previous
                if deviation > max_deviation:
                    rejected.append(
                        f'{pair}: {previous} -> {new_rate} '
                        f'({deviation * 100:.1f}% move, limit {max_deviation * 100:.0f}%)'
                    )
                    continue

            accepted[pair] = new_rate

        for message in rejected:
            self.stderr.write(self.style.WARNING(f'Rejected {message}'))
            logger.warning('FX rate rejected -- %s', message)

        # All-or-nothing: a mid-loop failure that left the table half-updated
        # would mix rates from two different syncs, which is worse than not
        # updating at all.
        with transaction.atomic():
            for pair, rate_value in accepted.items():
                ExchangeRate.objects.update_or_create(
                    currency_pair=pair,
                    defaults={'rate': rate_value},
                )

        self.stdout.write(self.style.SUCCESS(
            f'Updated {len(accepted)} exchange rate(s) against {BASE_CURRENCY}.'
        ))
        logger.info('FX sync: %s updated, %s rejected.', len(accepted), len(rejected))

        if rejected and not accepted:
            raise CommandError(
                'Every rate failed the sanity check; nothing was updated. '
                'Re-run with --force if the provider data is genuinely correct.'
            )
