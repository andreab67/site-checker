"""In-process monitor state for the admin GUI: poll history, heartbeat, alerts.

Nothing here is persisted and nothing here is secret. Timestamps are stored as
RFC 3339 UTC and only localized for display.
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

RECENT_POLL_MAX = 64
HOME_RECENT_SHOWN = 16


def _display_tz() -> ZoneInfo:
    try:
        return ZoneInfo((os.getenv("TZ") or "").strip() or "America/Denver")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


# Display timezone for GUI rows and the email body (TZ env, default Denver).
DISPLAY_TZ = _display_tz()


def utc_now_rfc3339() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def format_local(iso_utc: str | None) -> str:
    """'2026-05-22T13:51:21.618624Z' -> '2026-05-22 07:51:21 MDT' (for TZ=America/Denver).

    Returns the input unchanged on parse failure so a malformed row never
    breaks a page render.
    """
    if not iso_utc:
        return iso_utc or ""
    try:
        dt = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
    except ValueError:
        return iso_utc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(DISPLAY_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")


@dataclass(frozen=True)
class PollSnapshot:
    poll_time_rfc3339: str | None
    poll_ok: bool | None
    content_md5_prefix: str | None
    last_change_rfc3339: str | None
    last_change_url: str | None
    last_email_rfc3339: str | None
    last_email_ok: bool | None
    last_email_detail: str | None


@dataclass(frozen=True)
class PollHistoryEntry:
    """One completed fetch attempt (success or failure)."""

    time_rfc3339: str
    ok: bool
    md5_prefix: str | None
    md5_full: str | None = None
    url: str | None = None
    http_status: int | None = None
    elapsed_ms: float | None = None
    content_length: int | None = None
    error_detail: str | None = None
    changed: bool = False


def _clip_detail(text: str, max_len: int = 400) -> str:
    return " ".join(text.split())[:max_len]


_lock = threading.Lock()
_last_poll_time: str | None = None
_last_poll_ok: bool | None = None
_last_md5_prefix: str | None = None
_last_change_time: str | None = None
_last_change_url: str | None = None
_last_email_time: str | None = None
_last_email_ok: bool | None = None
_last_email_detail: str | None = None
_heartbeat_monotonic: float | None = None
_started_monotonic: float = time.monotonic()
_history: deque[PollHistoryEntry] = deque(maxlen=RECENT_POLL_MAX)


def record_poll(
    *,
    ok: bool,
    md5_hex: str | None,
    url: str | None = None,
    http_status: int | None = None,
    elapsed_ms: float | None = None,
    content_length: int | None = None,
    error_detail: str | None = None,
) -> None:
    """Called from the monitor loop after each fetch attempt."""
    global _last_poll_time, _last_poll_ok, _last_md5_prefix
    ts = utc_now_rfc3339()
    prefix = md5_hex[:8] if md5_hex else None
    err = _clip_detail(error_detail) if error_detail else None
    with _lock:
        _last_poll_time = ts
        _last_poll_ok = ok
        _last_md5_prefix = prefix
        _history.appendleft(
            PollHistoryEntry(
                time_rfc3339=ts,
                ok=ok,
                md5_prefix=prefix,
                md5_full=md5_hex or None,
                url=url,
                http_status=http_status,
                elapsed_ms=elapsed_ms,
                content_length=content_length,
                error_detail=err or None,
            )
        )


def record_change(url: str) -> None:
    """Mark the newest history row for `url` as a detected change."""
    global _last_change_time, _last_change_url
    with _lock:
        _last_change_time = utc_now_rfc3339()
        _last_change_url = url
        for i, e in enumerate(_history):
            if e.url == url:
                _history[i] = PollHistoryEntry(**{**e.__dict__, "changed": True})
                break


def record_email(ok: bool, detail: str = "") -> None:
    global _last_email_time, _last_email_ok, _last_email_detail
    with _lock:
        _last_email_time = utc_now_rfc3339()
        _last_email_ok = ok
        _last_email_detail = _clip_detail(detail) or None


def heartbeat() -> None:
    """Called by the monitor loop once per iteration."""
    global _heartbeat_monotonic
    with _lock:
        _heartbeat_monotonic = time.monotonic()


def heartbeat_age_seconds() -> float | None:
    """Seconds since the last loop heartbeat; None if the loop never ran."""
    with _lock:
        if _heartbeat_monotonic is None:
            return None
        return time.monotonic() - _heartbeat_monotonic


def uptime_seconds() -> float:
    return time.monotonic() - _started_monotonic


def get_poll_snapshot() -> PollSnapshot:
    with _lock:
        return PollSnapshot(
            poll_time_rfc3339=_last_poll_time,
            poll_ok=_last_poll_ok,
            content_md5_prefix=_last_md5_prefix,
            last_change_rfc3339=_last_change_time,
            last_change_url=_last_change_url,
            last_email_rfc3339=_last_email_time,
            last_email_ok=_last_email_ok,
            last_email_detail=_last_email_detail,
        )


def get_recent_polls(limit: int = HOME_RECENT_SHOWN) -> tuple[PollHistoryEntry, ...]:
    """Newest-first poll history, length capped at ``limit``."""
    with _lock:
        n = max(0, min(limit, len(_history)))
        return tuple(_history[i] for i in range(n))


def reset_for_tests() -> None:
    global _last_poll_time, _last_poll_ok, _last_md5_prefix, _last_change_time
    global _last_change_url, _last_email_time, _last_email_ok, _last_email_detail
    global _heartbeat_monotonic, _started_monotonic
    with _lock:
        _last_poll_time = _last_poll_ok = _last_md5_prefix = None
        _last_change_time = _last_change_url = None
        _last_email_time = _last_email_ok = _last_email_detail = None
        _heartbeat_monotonic = None
        _started_monotonic = time.monotonic()
        _history.clear()
