"""
Cache backend that degrades instead of failing the request.

Django's built-in ``django.core.cache.backends.redis.RedisCache`` has no
equivalent of django-redis's ``IGNORE_EXCEPTIONS``: it forwards every unknown
key in ``OPTIONS`` straight into ``redis.ConnectionPool.from_url()``, so
setting that option did not soften anything -- it raised

    TypeError: AbstractConnection.__init__() got an unexpected keyword
    argument 'IGNORE_EXCEPTIONS'

on the *first cache access*, not at startup. Pool construction is lazy, so the
process booted cleanly and served 404s, while every request that reached DRF's
throttle (i.e. all of /api/) returned 500.

The cache here backs throttling and the login lockout counter. Neither is
worth a 500: a Redis outage should cost us rate limiting, not the API. So
Redis-level failures are swallowed and reported as a miss.

That is deliberately fail-open. While Redis is unreachable the per-account
login lockout stops counting, leaving the per-IP throttle -- itself cache
backed -- equally degraded. The alternative is failing closed, which converts
a cache outage into a total auth outage. Failures are logged at WARNING so the
degradation is visible rather than silent.

Programming errors are *not* swallowed. In particular ``incr()`` raises
``ValueError`` for a missing key, which callers rely on to detect an expired
window (see ``_record_login_failure`` in subscriptions/views.py); catching
only Redis transport errors keeps that signal intact.
"""

import functools
import logging

from django.core.cache.backends.redis import RedisCache

logger = logging.getLogger(__name__)


def _degrade(fallback):
    """
    Swallow Redis transport errors and return ``fallback`` instead.

    ``fallback`` is called with the same arguments as the wrapped method so
    each method can return whatever its contract calls for on a miss.
    """

    def decorator(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            try:
                return method(self, *args, **kwargs)
            except Exception as exc:
                # redis-py wraps socket failures in RedisError, but a bad URL
                # or a DNS failure can surface as OSError before that.
                if not isinstance(exc, self._degradable_errors):
                    raise
                logger.warning(
                    'Cache unavailable, degrading %s(): %s',
                    method.__name__, exc,
                )
                return fallback(*args, **kwargs)

        return wrapper

    return decorator


class ResilientRedisCache(RedisCache):
    """``RedisCache`` with transport failures degraded to cache misses."""

    def __init__(self, server, params):
        # IGNORE_EXCEPTIONS is accepted and ignored so an existing django-redis
        # style config does not blow up the pool; resilience is unconditional
        # here. Popping it is what keeps it out of ConnectionPool.from_url().
        options = params.get('OPTIONS')
        if options and 'IGNORE_EXCEPTIONS' in options:
            params = {**params, 'OPTIONS': {
                k: v for k, v in options.items() if k != 'IGNORE_EXCEPTIONS'
            }}
        super().__init__(server, params)

    @functools.cached_property
    def _degradable_errors(self):
        # Imported lazily: the redis package is only a dependency when this
        # backend is actually selected.
        import redis

        return (redis.RedisError, OSError)

    # get() already takes a `default`; honour it rather than assuming None.
    @_degrade(lambda key, default=None, version=None: default)
    def get(self, key, default=None, version=None):
        return super().get(key, default, version)

    @_degrade(lambda *a, **kw: None)
    def set(self, *args, **kwargs):
        return super().set(*args, **kwargs)

    @_degrade(lambda *a, **kw: False)
    def add(self, *args, **kwargs):
        return super().add(*args, **kwargs)

    @_degrade(lambda *a, **kw: False)
    def touch(self, *args, **kwargs):
        return super().touch(*args, **kwargs)

    @_degrade(lambda *a, **kw: False)
    def delete(self, *args, **kwargs):
        return super().delete(*args, **kwargs)

    @_degrade(lambda *a, **kw: False)
    def has_key(self, *args, **kwargs):
        return super().has_key(*args, **kwargs)

    @_degrade(lambda *a, **kw: None)
    def incr(self, *args, **kwargs):
        return super().incr(*args, **kwargs)

    @_degrade(lambda *a, **kw: None)
    def decr(self, *args, **kwargs):
        return super().decr(*args, **kwargs)

    @_degrade(lambda *a, **kw: {})
    def get_many(self, *args, **kwargs):
        return super().get_many(*args, **kwargs)

    # Contract: returns the keys that failed to be set. On an outage that is
    # all of them.
    @_degrade(lambda data, *a, **kw: list(data))
    def set_many(self, *args, **kwargs):
        return super().set_many(*args, **kwargs)

    @_degrade(lambda *a, **kw: None)
    def delete_many(self, *args, **kwargs):
        return super().delete_many(*args, **kwargs)

    @_degrade(lambda *a, **kw: None)
    def clear(self, *args, **kwargs):
        return super().clear(*args, **kwargs)
