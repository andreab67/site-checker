"""In-process URL and email settings.

Seeded from the environment at startup, optionally overlaid from a JSON file
(SETTINGS_FILE), and hot-reloaded when the admin GUI saves. SMTP credentials
never pass through this module.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from urllib.parse import urlparse

KEYS = (
    "WEBSITE_URL",
    "WEBSITE_URL_2",
    "EMAIL_SENDER",
    "EMAIL_RECEIVER1",
    "EMAIL_RECEIVER2",
    "EMAIL_RECEIVER3",
    "EMAIL_RECEIVER4",
)

_lock = threading.Lock()
_values: dict[str, str] = {k: "" for k in KEYS}
_loaded_from_file: bool = False


def is_http_url(u: str) -> bool:
    """True for an absolute http(s) URL with a host (placeholders fail this)."""
    try:
        p = urlparse(u)
    except ValueError:
        return False
    return p.scheme in ("http", "https") and bool(p.netloc) and " " not in u


def settings_file() -> str:
    """Path of the persistence file, or '' when saves are memory-only."""
    return (os.getenv("SETTINGS_FILE") or "").strip()


def load_from_environ() -> None:
    """Initialize from the environment, then overlay SETTINGS_FILE if present."""
    global _loaded_from_file
    fresh = {k: (os.getenv(k) or "").strip() for k in KEYS}
    loaded = False
    path = settings_file()
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("top-level JSON value is not an object")
            for k in KEYS:
                v = data.get(k)
                if isinstance(v, str):
                    fresh[k] = v.strip()
            loaded = True
        except (OSError, ValueError) as e:
            logging.warning("Ignoring unreadable SETTINGS_FILE %s: %s", path, e)
    with _lock:
        _values.update(fresh)
        _loaded_from_file = loaded


def loaded_from_file() -> bool:
    with _lock:
        return _loaded_from_file


def apply_updates(
    *,
    website_url: str,
    website_url_2: str,
    email_sender: str,
    email_receiver1: str,
    email_receiver2: str,
    email_receiver3: str,
    email_receiver4: str,
) -> None:
    """Replace live settings (the monitor picks them up on its next poll)."""
    with _lock:
        _values.update(
            {
                "WEBSITE_URL": website_url.strip(),
                "WEBSITE_URL_2": website_url_2.strip(),
                "EMAIL_SENDER": email_sender.strip(),
                "EMAIL_RECEIVER1": email_receiver1.strip(),
                "EMAIL_RECEIVER2": email_receiver2.strip(),
                "EMAIL_RECEIVER3": email_receiver3.strip(),
                "EMAIL_RECEIVER4": email_receiver4.strip(),
            }
        )


def write_file(path: str, data: dict[str, str]) -> None:
    """Atomically write settings JSON (mode 0600). Raises OSError on failure."""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".site-checker-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({k: data.get(k, "") for k in KEYS}, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def get_monitored_urls() -> list[str]:
    """Configured http(s) URLs in stable order (1 then 2), de-duplicated."""
    with _lock:
        out: list[str] = []
        for k in ("WEBSITE_URL", "WEBSITE_URL_2"):
            u = _values[k]
            if u and is_http_url(u) and u not in out:
                out.append(u)
        return out


def get_email_sender() -> str:
    with _lock:
        return _values["EMAIL_SENDER"]


def get_receiver_emails() -> list[str]:
    """Non-empty receiver addresses (slots 1..4), de-duplicated, stable order."""
    with _lock:
        out: list[str] = []
        for k in ("EMAIL_RECEIVER1", "EMAIL_RECEIVER2", "EMAIL_RECEIVER3", "EMAIL_RECEIVER4"):
            v = _values[k]
            if v and v not in out:
                out.append(v)
        return out


def snapshot() -> tuple[str, str, str, str, str, str, str]:
    """(website_url, website_url_2, sender, r1, r2, r3, r4) for read-only UI."""
    with _lock:
        return tuple(_values[k] for k in KEYS)  # type: ignore[return-value]


def as_dict() -> dict[str, str]:
    with _lock:
        return dict(_values)
