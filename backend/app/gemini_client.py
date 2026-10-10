from __future__ import annotations

import logging
import time
from functools import lru_cache

from app.config import settings

logger = logging.getLogger(__name__)

_quota_blocked_until = 0.0
QUOTA_COOLDOWN_SEC = 120.0


@lru_cache(maxsize=1)
def client():
    from google import genai

    return genai.Client(api_key=settings.gemini_api_key)


def disable_afc():
    from google.genai import types

    return types.AutomaticFunctionCallingConfig(disable=True)


def http_options(*, timeout_ms: int = 20_000, attempts: int = 2):
    from google.genai import types

    return types.HttpOptions(
        timeout=timeout_ms,
        retry_options=types.HttpRetryOptions(
            attempts=attempts,
            http_status_codes=[503, 504],
        ),
    )


def quota_blocked() -> bool:
    return time.monotonic() < _quota_blocked_until


def quota_remaining_sec() -> int:
    return max(0, int(_quota_blocked_until - time.monotonic()))


def mark_quota(exc: Exception | None = None) -> None:
    global _quota_blocked_until
    _quota_blocked_until = time.monotonic() + QUOTA_COOLDOWN_SEC
    logger.warning("gemini quota exhausted; skipping Gemini for %ss", int(QUOTA_COOLDOWN_SEC))


def is_quota_error(exc: Exception) -> bool:
    status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    return status == 429 or "RESOURCE_EXHAUSTED" in str(exc).upper()
