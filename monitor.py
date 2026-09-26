"""Poll one or two websites on a fixed interval, email an alert when content changes,
and serve a small admin GUI (status board + runtime settings) on ADMIN_PORT."""

from __future__ import annotations

import hashlib
import logging
import os
import smtplib
import threading
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
import uvicorn

import runner_state
import settings_store
from admin_app import check_interval_seconds, create_app, smtp_host

LOG_FORMAT = "%(asctime)s:%(levelname)s:%(message)s"
FETCH_TIMEOUT = (10, 30)  # (connect, read) seconds; requests has no default timeout
SMTP_PORT_SSL = 465
SMTP_TIMEOUT = 30


def setup_logging() -> None:
    """stderr always; LOG_FILE (default /var/log/site-checker.log) only if writable."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT)
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
               for h in root.handlers):
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)
    path = os.getenv("LOG_FILE", "/var/log/site-checker.log").strip()
    if path:
        try:
            file_handler = logging.FileHandler(path)
        except OSError as e:
            logging.info("File logging disabled (%s): %s", path, e.strerror or e)
        else:
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)


def fetch_website_content(url: str) -> str | None:
    """Fetch `url` and return the MD5 of its body, or None on any failure."""
    started = time.perf_counter()
    try:
        response = requests.get(url, timeout=FETCH_TIMEOUT)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.raise_for_status()
    except requests.RequestException as e:
        status = e.response.status_code if getattr(e, "response", None) is not None else None
        logging.error("Error fetching %s: %s", url, e)
        runner_state.record_poll(
            ok=False,
            md5_hex=None,
            url=url,
            http_status=status,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            error_detail=f"{type(e).__name__}: {e}",
        )
        return None
    content_hash = hashlib.md5(response.content).hexdigest()
    runner_state.record_poll(
        ok=True,
        md5_hex=content_hash,
        url=url,
        http_status=response.status_code,
        elapsed_ms=elapsed_ms,
        content_length=len(response.content),
    )
    logging.info("Content fetched successfully for URL: %s", url)
    return content_hash


def send_email(subject: str, body: str) -> bool:
    """Send a plain-text alert over SMTPS. Returns True when the server accepted it."""
    sender_email = settings_store.get_email_sender()
    receiver_emails = settings_store.get_receiver_emails()
    userid = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")

    if not sender_email or not receiver_emails:
        detail = "EMAIL_SENDER or all EMAIL_RECEIVER* are empty"
        logging.error("Failed to send email: %s", detail)
        runner_state.record_email(False, detail)
        return False

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = ", ".join(receiver_emails)
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL(smtp_host(), SMTP_PORT_SSL, timeout=SMTP_TIMEOUT) as server:
            server.login(userid or "", password or "")
            server.sendmail(sender_email, receiver_emails, message.as_string())
    except Exception as e:  # noqa: BLE001 - any SMTP/network/header error is a failed alert
        logging.error("Failed to send email: %s", e)
        runner_state.record_email(False, f"{type(e).__name__}: {e}")
        return False
    logging.info("Email sent successfully to %d recipient(s)", len(receiver_emails))
    runner_state.record_email(True)
    return True


def check_once(state: dict[str, str]) -> None:
    """Poll every configured URL once. `state` maps URL -> last alerted hash.

    A URL's first successful fetch sets its baseline. On a change the baseline
    only advances once the alert email is accepted, so an SMTP outage retries
    the alert on the next poll instead of silently dropping it.
    """
    urls = settings_store.get_monitored_urls()
    for stale in [u for u in state if u not in urls]:
        del state[stale]
    for url in urls:
        new_hash = fetch_website_content(url)
        if new_hash is None:
            logging.warning("Failed to fetch website content for %s", url)
            continue
        old_hash = state.get(url)
        if old_hash is None:
            state[url] = new_hash
            logging.info("Baseline recorded for %s (%s)", url, new_hash[:8])
            continue
        if new_hash == old_hash:
            logging.info("No changes detected for %s", url)
            continue
        logging.info("Website has changed: %s", url)
        runner_state.record_change(url)
        when = runner_state.format_local(runner_state.utc_now_rfc3339())
        sent = send_email(
            "Website Change Alert",
            f"Change detected in {url} at {when}\n\n"
            f"Previous content MD5: {old_hash}\nCurrent content MD5:  {new_hash}\n",
        )
        if sent:
            state[url] = new_hash
        else:
            logging.warning("Alert for %s not delivered; will retry on the next poll", url)


def run_admin_server() -> None:
    host = (os.getenv("ADMIN_HOST") or "0.0.0.0").strip()
    port = int((os.getenv("ADMIN_PORT") or "8080").strip())
    uvicorn.run(create_app(), host=host, port=port, log_level="warning",
                server_header=False, proxy_headers=False)


def main() -> None:
    setup_logging()
    settings_store.load_from_environ()
    if settings_store.loaded_from_file():
        logging.info("Runtime settings loaded from %s", settings_store.settings_file())
    if (os.getenv("ADMIN_ENABLED") or "1").strip() != "0":
        threading.Thread(target=run_admin_server, name="admin", daemon=True).start()

    interval = check_interval_seconds()
    urls = settings_store.get_monitored_urls()
    if urls:
        logging.info("Monitoring %s every %ds for changes...", ", ".join(urls), interval)
    else:
        logging.warning("No valid WEBSITE_URL configured; set it via env or the admin GUI")

    state: dict[str, str] = {}
    while True:
        runner_state.heartbeat()
        try:
            check_once(state)
        except Exception:  # keep the watchdog alive; /healthz reports a stuck loop
            logging.exception("Unexpected error in the monitor loop")
        time.sleep(interval)


if __name__ == "__main__":
    main()
