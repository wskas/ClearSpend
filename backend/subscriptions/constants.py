"""
Single source of truth for the currencies ClearSpend supports.
 
Consumed by:
  - management/commands/fetch_exchange_rates.py -- which rates to fetch
  - views.get_exchange_rate()                   -- the triangulation pivot
  - the frontend, via GET /api/currencies/      -- dropdown options
 
Adding a currency here is all that is required: the next
`fetch_exchange_rates` run picks it up and the frontend dropdowns follow.
Anything added must be quotable by the FX provider (Frankfurter).
"""
 
SUPPORTED_CURRENCIES = [
    'USD',
    'EUR',
    'GBP',
    'JPY',
    'CAD',
    'AUD',
    'CHF',
    'SGD',
    'IDR',
    'HKD',
]
 
# Rates are stored one-directional against this base (USD_EUR, USD_GBP, ...),
# so it doubles as the pivot for deriving any pair we do not store directly.
BASE_CURRENCY = 'USD'
