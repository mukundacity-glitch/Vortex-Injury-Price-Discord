"""One clock boundary for scheduled and manual production delivery."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import os


def allowed(now=None):
    local = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo('America/New_York'))
    return 5 <= local.hour < 20


def assert_allowed(now=None):
    if os.getenv('FPL_PUBLISH_WINDOW_ENFORCED', 'false').lower() == 'true' and not allowed(now):
        raise RuntimeError('Outside 05:00–20:00 America/New_York; retain pending edition for next window')
