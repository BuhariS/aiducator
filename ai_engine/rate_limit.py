import logging
from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse

logger = logging.getLogger(__name__)


def rate_limit(name: str, *, limit: int, period: int, methods=("POST",)):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method not in methods:
                return view(request, *args, **kwargs)
            subject = f"user:{request.user.pk}" if request.user.is_authenticated else f"ip:{request.META.get('REMOTE_ADDR', 'unknown')}"
            key = f"aiducator:rate:{name}:{subject}"
            try:
                if cache.add(key, 1, timeout=period):
                    return view(request, *args, **kwargs)
                count = cache.incr(key)
            except Exception:
                logger.exception("Rate-limit backend unavailable for %s", name)
                return HttpResponse("This action is temporarily unavailable. Please try again shortly.", status=503)
            if count > limit:
                return HttpResponse("Too many requests. Please try again later.", status=429)
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
