from decimal import Decimal
 
import requests
from django.conf import settings
from django.core.management.base import BaseCommand
 
from subscriptions.models import ExchangeRate
 
# Extend as needed; keep in sync with what your frontend lets users pick
# as a base_currency / original_currency.
SUPPORTED_CURRENCIES = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'SGD','IDR','HKD']
BASE_FOR_FETCH = 'USD'
 
 
class Command(BaseCommand):
    """
    Manual/cron replacement for the Celery beat task described in the PRD.
 
    Run with:
        python manage.py fetch_exchange_rates
 
    Wire this up to a system cron entry (or a scheduled task on your host)
    to hit it daily until Celery is introduced. When you do add Celery,
    this same body drops straight into a @shared_task -- see the
    commented-out example at the bottom of this file.
    """
    help = 'Fetch latest FX rates from the external provider and upsert into ExchangeRate.'
 
    def handle(self, *args, **options):
        # Frankfurter (api.frankfurter.dev): no API key, no signup, no quota.
        # GET /v2/rates?base=USD&quotes=EUR,GBP,... -> a FLAT ARRAY, one row
        # per quote currency, e.g. [{"quote": "EUR", "rate": 0.8739, ...}, ...]
        # (NOT a {"rates": {...}} object -- that was the v1 shape.)
        url = f'{settings.EXCHANGE_RATE_API_BASE_URL}/v2/rates'
        quote_currencies = [c for c in SUPPORTED_CURRENCIES if c != BASE_FOR_FETCH]
 
        try:
            response = requests.get(
                url,
                params={'base': BASE_FOR_FETCH, 'quotes': ','.join(quote_currencies)},
                timeout=10,
            )
            response.raise_for_status()
            rows = response.json()
        except (requests.RequestException, ValueError) as exc:
            self.stderr.write(self.style.ERROR(f'Failed to fetch FX rates: {exc}'))
            # Deliberately don't touch existing rows -- get_exchange_rate()
            # in views.py will keep serving the last successfully synced
            # values, satisfying the PRD's "graceful fallback" requirement.
            return
 
        # Reshape the flat array into a {quote_currency: rate} lookup.
        rates = {row['quote']: row['rate'] for row in rows}
        updated = 0
 
        for currency in quote_currencies:
            if currency not in rates:
                continue
 
            pair = f'{BASE_FOR_FETCH}_{currency}'
            rate_value = Decimal(str(rates[currency]))
            ExchangeRate.objects.update_or_create(
                currency_pair=pair,
                defaults={'rate': rate_value},
            )
            updated += 1
 
        self.stdout.write(self.style.SUCCESS(f'Updated {updated} exchange rate(s) against {BASE_FOR_FETCH}.'))