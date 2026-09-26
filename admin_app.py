"""Admin GUI: heartbeat home page, status board, and token-gated runtime settings.

Runs inside the monitor process on a daemon thread (see monitor.py). Pages are
server-rendered; every dynamic value goes through html.escape.
"""

from __future__ import annotations

import hashlib
import hmac
import html
import os
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

import runner_state
import settings_store
from settings_validation import RuntimeSettingsPayload

STATIC_DIR = Path(__file__).resolve().parent / "static"
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'"
)


def _env_present(name: str) -> bool:
    v = os.getenv(name)
    return bool(v and v.strip())


def check_interval_seconds() -> int:
    """CHECK_INTERVAL_SECONDS (default 300, floor 30). Shared with monitor.py."""
    raw = (os.getenv("CHECK_INTERVAL_SECONDS") or "").strip()
    try:
        value = int(raw) if raw else 300
    except ValueError:
        value = 300
    return max(30, value)


def smtp_host() -> str:
    return (os.getenv("SMTP_HOST") or "").strip() or "email-smtp.us-east-1.amazonaws.com"


def _admin_token() -> str:
    return (os.getenv("SITE_CHECKER_ADMIN_TOKEN") or "").strip()


def _admin_token_matches(got: str, expected: str) -> bool:
    """Constant-time compare via digests so unequal lengths stay safe."""
    return hmac.compare_digest(
        hashlib.sha256(got.encode("utf-8")).digest(),
        hashlib.sha256(expected.encode("utf-8")).digest(),
    )


def _require_admin_token(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    expected = _admin_token()
    if not expected:
        raise HTTPException(status_code=503, detail="SITE_CHECKER_ADMIN_TOKEN is not set on the server")
    got = (x_admin_token or "").strip()
    if not got or not _admin_token_matches(got, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _stale_after_seconds() -> float:
    # One full sleep plus worst-case fetch timeouts for two URLs and an SMTP send.
    return 2 * check_interval_seconds() + 180


# ------------------------------------------------------------------ markup helpers
def _head(title: str) -> str:
    return (
        "<!doctype html><html lang='en'><head>"
        "<meta charset='utf-8'/>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'/>"
        "<link rel='icon' type='image/png' href='/static/icon.png'/>"
        f"<title>{html.escape(title)}</title>"
        "<link rel='preconnect' href='https://fonts.googleapis.com'/>"
        "<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin/>"
        "<link href='https://fonts.googleapis.com/css2?"
        "family=Space+Grotesk:wght@400;500;600;700&amp;"
        "family=IBM+Plex+Mono:wght@400;500;600;700&amp;"
        "display=swap' rel='stylesheet'/>"
        "<link rel='stylesheet' href='/static/site-checker.css'/>"
        "</head>"
    )


def _badge(label: str, tone: str) -> str:
    return f"<span class='badge badge--{tone}'>{html.escape(label)}</span>"


def _badge_poll(ok: bool | None) -> str:
    if ok is True:
        return _badge("OK", "ok")
    if ok is False:
        return _badge("FAIL", "fail")
    return _badge("—", "unknown")


def _badge_yesno(yes: bool) -> str:
    return _badge("yes", "ok") if yes else _badge("no", "unknown")


def _kv_row(label: str, value_html: str) -> str:
    """One <dt>/<dd> pair. value_html is inserted as-is: escape before calling."""
    return f"<div class='kv__row'><dt>{html.escape(label)}</dt><dd>{value_html}</dd></div>"


def _poll_detail_html(e: runner_state.PollHistoryEntry) -> str:
    pairs: list[tuple[str, str]] = []
    if e.url:
        pairs.append(("Monitored URL", e.url))
    if e.http_status is not None:
        pairs.append(("HTTP status", str(e.http_status)))
    if e.elapsed_ms is not None:
        pairs.append(("Response time", f"{e.elapsed_ms:.1f} ms"))
    if e.content_length is not None:
        pairs.append(("Downloaded body", f"{e.content_length:,} bytes"))
    if e.md5_full:
        pairs.append(("Content MD5 (full)", e.md5_full))
    if e.changed:
        pairs.append(("Result", "content changed — alert triggered"))
    if e.error_detail:
        pairs.append(("Request error", e.error_detail))
    if not pairs:
        return "<p class='recent-list__nodetail'>No extended metadata was stored for this poll.</p>"
    chunks = "".join(
        f"<dt class='recent-list__dt'>{html.escape(k)}</dt><dd class='recent-list__dd'>{html.escape(v)}</dd>"
        for k, v in pairs
    )
    return f"<dl class='recent-list__dl'>{chunks}</dl>"


def _recent_checks_home(limit: int = runner_state.HOME_RECENT_SHOWN) -> str:
    rows = runner_state.get_recent_polls(limit)
    if not rows:
        return (
            "<section class='home-recent' aria-labelledby='recent-title'>"
            "<h2 class='home-recent__title' id='recent-title'>Recent checks</h2>"
            "<p class='home-recent__empty'>No fetch history yet. Polls appear after the "
            "monitor fetches a configured <code>WEBSITE_URL</code>.</p>"
            "</section>"
        )
    items = []
    for e in rows:
        badge = _badge_poll(e.ok) + (" " + _badge("changed", "warn") if e.changed else "")
        items.append(
            "<li class='recent-list__item'><details class='recent-list__details'>"
            "<summary class='recent-list__summary'><span class='recent-list__summary-grid'>"
            f"<span class='recent-list__time'>{html.escape(runner_state.format_local(e.time_rfc3339))}</span>"
            f"<span class='recent-list__status'>{badge}</span>"
            f"<span class='recent-list__hash'>{html.escape(e.md5_prefix or '—')}</span>"
            "<span class='recent-list__chevron' aria-hidden='true'>▸</span>"
            "</span><span class='recent-list__summary-sr'>Show details for this check</span></summary>"
            f"<div class='recent-list__body'>{_poll_detail_html(e)}</div>"
            "</details></li>"
        )
    return (
        "<section class='home-recent' aria-labelledby='recent-title'>"
        "<h2 class='home-recent__title' id='recent-title'>Recent checks</h2>"
        f"<p class='home-recent__sub'>Newest first. Showing up to {limit} of the last "
        f"{runner_state.RECENT_POLL_MAX} fetch attempts kept in memory. Open a row for timing, "
        "status, and errors.</p>"
        f"<ul class='recent-list' role='list'>{''.join(items)}</ul>"
        "</section>"
    )


def _persistence_label() -> str:
    path = settings_store.settings_file()
    return f"file: {path}" if path else "memory only (lost on restart)"


def _heartbeat_rail() -> str:
    age = runner_state.heartbeat_age_seconds()
    if age is None:
        dot, value = "status-rail__dot status-rail__dot--wait", "starting"
    elif age > _stale_after_seconds():
        dot, value = "status-rail__dot status-rail__dot--fail", f"stalled ({age:.0f}s since last loop)"
    else:
        dot, value = "status-rail__dot", "running"
    return (
        "<div class='status-rail' aria-live='polite'>"
        f"<span class='{dot}' aria-hidden='true'></span>"
        "<span class='status-rail__label'>monitor</span>"
        f"<span class='status-rail__value'>{html.escape(value)}</span>"
        "</div>"
    )


# ------------------------------------------------------------------ pages
def _home_page() -> str:
    return (
        f"{_head('site-checker')}"
        "<body class='app app--home'>"
        "<header class='app-header'>"
        "<p class='app-header__eyebrow'>watchdog</p>"
        "<h1 class='app-header__title'>site-checker</h1>"
        "<p class='app-header__lede'>Monitors a web page for content changes and emails an alert "
        "when it changes. This page is the live heartbeat of the container.</p>"
        f"{_heartbeat_rail()}"
        "</header>"
        f"{_recent_checks_home()}"
        "<div class='btn-row'><a class='btn' href='/admin'>Open status board →</a></div>"
        "</body></html>"
    )


def _status_page() -> str:
    url, url2, sender, r1, r2, r3, r4 = settings_store.snapshot()
    snap = runner_state.get_poll_snapshot()
    monitored = settings_store.get_monitored_urls()

    def t(value: str | None) -> str:
        return html.escape(runner_state.format_local(value)) if value else "—"

    def poll_line(label: str, value_html: str) -> str:
        return (
            f"<div class='poll-line'><span class='poll-line__k'>{html.escape(label)}</span>"
            f"<span class='poll-line__v'>{value_html}</span></div>"
        )

    email_state = _badge_poll(snap.last_email_ok) if snap.last_email_rfc3339 else _badge("none yet", "unknown")
    poll_block = "".join(
        [
            poll_line("last poll", t(snap.poll_time_rfc3339)),
            poll_line("fetch", _badge_poll(snap.poll_ok)),
            poll_line("content md5 prefix", html.escape(snap.content_md5_prefix or "—")),
            poll_line("last change", t(snap.last_change_rfc3339)),
            poll_line("changed url", html.escape(snap.last_change_url or "—")),
            poll_line("last alert email", f"{t(snap.last_email_rfc3339)} {email_state}"),
        ]
    )
    if snap.last_email_ok is False and snap.last_email_detail:
        poll_block += poll_line("email error", html.escape(snap.last_email_detail))

    def or_dash(v: str) -> str:
        return html.escape(v) if v else "—"

    placeholder = bool(url) and url not in monitored
    cfg_rows = "".join(
        [
            _kv_row("monitoring", _badge_yesno(bool(monitored))),
            _kv_row("check interval", html.escape(f"{check_interval_seconds()} s")),
            _kv_row("TZ", html.escape(str(runner_state.DISPLAY_TZ))),
            _kv_row(
                "WEBSITE_URL",
                or_dash(url) + (" " + _badge("not an http(s) url", "warn") if placeholder else ""),
            ),
            _kv_row("WEBSITE_URL_2", or_dash(url2)),
            _kv_row("EMAIL_SENDER", or_dash(sender)),
            _kv_row("EMAIL_RECEIVER1", or_dash(r1)),
            _kv_row("EMAIL_RECEIVER2", or_dash(r2)),
            _kv_row("EMAIL_RECEIVER3", or_dash(r3)),
            _kv_row("EMAIL_RECEIVER4", or_dash(r4)),
            _kv_row("smtp host", html.escape(smtp_host())),
            _kv_row("smtp username", _badge_yesno(_env_present("SMTP_USERNAME"))),
            _kv_row("smtp password", _badge_yesno(_env_present("SMTP_PASSWORD"))),
            _kv_row("settings saved to", html.escape(_persistence_label())),
        ]
    )
    return (
        f"{_head('site-checker — status')}"
        "<body class='app app--admin'>"
        "<a class='back-link' href='/'>← Home</a>"
        "<header class='app-header'>"
        "<p class='app-header__eyebrow'>operations</p>"
        "<h1 class='app-header__title'>Status board</h1>"
        "<p class='app-header__lede'>Runtime configuration and the last poll snapshot. "
        "SMTP secrets are never rendered—only configured / missing.</p>"
        "</header>"
        "<div class='grid grid--2'>"
        "<section class='card' aria-labelledby='poll-card-title'>"
        "<h2 class='card__title' id='poll-card-title'>Poll snapshot</h2>"
        "<p class='card__meta'>Updated every time the monitor loop fetches a watched URL.</p>"
        f"{poll_block}"
        "</section>"
        "<section class='card' aria-labelledby='cfg-card-title'>"
        "<h2 class='card__title' id='cfg-card-title'>Configuration</h2>"
        "<p class='card__meta'>Live values from the in-memory store (seeded from the environment"
        " and SETTINGS_FILE at startup, then hot-reloaded after saves).</p>"
        f"<dl class='kv'>{cfg_rows}</dl>"
        "</section>"
        "</div>"
        "<p class='admin-nav'><a class='admin-nav__link' href='/admin/settings'>Runtime settings →</a></p>"
        "<p class='footer-note'>SMTP username and password are intentionally omitted from this page. "
        "Rotate them through your platform's secret store and restart the container.</p>"
        "</body></html>"
    )


def _input(label: str, fid: str, name: str, value: str, *, kind: str = "text",
           required: bool = False, inputmode: str = "") -> str:
    req = " required" if required else ""
    im = f" inputmode='{inputmode}'" if inputmode else ""
    return (
        f"<label class='settings-label' for='{fid}'>{html.escape(label)}</label>"
        f"<input class='settings-input' id='{fid}' name='{name}' type='{kind}'{req}{im} "
        f"value=\"{html.escape(value)}\" autocomplete='off' spellcheck='false'/>"
    )


def _settings_page() -> str:
    w, w2, s, r1, r2, r3, r4 = settings_store.snapshot()
    if _admin_token():
        token_hint = (
            "<p class='settings-hint settings-hint--ok'>Paste the value of "
            "<code>SITE_CHECKER_ADMIN_TOKEN</code> from the container environment to authorize saves.</p>"
        )
    else:
        token_hint = (
            "<p class='settings-hint settings-hint--warn'><strong>Saving disabled.</strong> Set "
            "<code>SITE_CHECKER_ADMIN_TOKEN</code> (from your secret store, alongside the SMTP "
            "credentials) and restart the container.</p>"
        )
    if settings_store.settings_file():
        persist = (
            "Saved values are written to <code>"
            f"{html.escape(settings_store.settings_file())}</code> and applied immediately; they "
            "take precedence over the matching environment variables on restart."
        )
    else:
        persist = (
            "<strong>No <code>SETTINGS_FILE</code> configured:</strong> saves apply immediately but "
            "are lost when the container restarts. Mount a volume and set <code>SETTINGS_FILE</code> "
            "to keep them."
        )
    return (
        f"{_head('site-checker — settings')}"
        "<body class='app app--admin'>"
        "<a class='back-link' href='/admin'>← Status board</a>"
        "<header class='app-header'>"
        "<p class='app-header__eyebrow'>operations</p>"
        "<h1 class='app-header__title'>Runtime settings</h1>"
        "<p class='app-header__lede'>Update the monitored URLs and alert addresses without rebuilding "
        "the image. SMTP credentials are not shown or editable here.</p>"
        "</header>"
        "<section class='card settings-card' aria-labelledby='settings-title'>"
        "<h2 class='card__title' id='settings-title'>Edit configuration</h2>"
        f"{token_hint}"
        f"<p class='settings-hint settings-hint--ok'>{persist}</p>"
        "<form id='runtime-settings-form' class='settings-form' method='post' action='#'>"
        + _input("Monitored URL", "f-url", "website_url", w, kind="url", required=True)
        + _input("Monitored URL 2 (optional)", "f-url-2", "website_url_2", w2, inputmode="url")
        + _input("Email sender", "f-sender", "email_sender", s, kind="email", required=True)
        + _input("Recipient 1", "f-r1", "email_receiver1", r1, kind="email", required=True)
        + _input("Recipient 2 (optional)", "f-r2", "email_receiver2", r2, inputmode="email")
        + _input("Recipient 3 (optional)", "f-r3", "email_receiver3", r3, inputmode="email")
        + _input("Recipient 4 (optional)", "f-r4", "email_receiver4", r4, inputmode="email")
        + "<label class='settings-label' for='admin-token'>Admin token</label>"
        "<input class='settings-input' id='admin-token' type='password' autocomplete='off' "
        "placeholder='SITE_CHECKER_ADMIN_TOKEN value'/>"
        "<div class='settings-actions'><button class='btn settings-submit' type='submit'>"
        "Save settings</button></div>"
        "</form>"
        "<p id='settings-msg' class='settings-msg' aria-live='polite'></p>"
        "<p class='settings-footnote'>Serve this page only on a trusted network or behind an "
        "authenticating proxy; the token travels in a request header, so use TLS.</p>"
        "</section>"
        "<script src='/static/admin-settings.js' defer></script>"
        "</body></html>"
    )


# ------------------------------------------------------------------ app
def _save_settings(payload: RuntimeSettingsPayload) -> bool:
    """Persist (if configured) and then apply. Returns True when written to disk."""
    values = {
        "website_url": payload.website_url,
        "website_url_2": payload.website_url_2,
        "email_sender": str(payload.email_sender),
        "email_receiver1": str(payload.email_receiver1),
        "email_receiver2": payload.email_receiver2,
        "email_receiver3": payload.email_receiver3,
        "email_receiver4": payload.email_receiver4,
    }
    path = settings_store.settings_file()
    if path:
        # Write first: if the disk write fails the live settings stay untouched,
        # so the GUI never shows values that would silently revert on restart.
        settings_store.write_file(path, {k.upper(): v for k, v in values.items()})
    settings_store.apply_updates(**values)
    return bool(path)


def create_app() -> FastAPI:
    app = FastAPI(title="site-checker", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("Content-Security-Policy", CSP)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        return resp

    @app.get("/", response_class=HTMLResponse)
    def root() -> HTMLResponse:
        return HTMLResponse(_home_page())

    @app.get("/healthz")
    def healthz() -> JSONResponse:
        """Liveness: fails when the monitor loop stops iterating (e.g. a hung send).

        Before the first iteration the container gets one stale window of grace.
        """
        age = runner_state.heartbeat_age_seconds()
        limit = _stale_after_seconds()
        if age is None:
            ok = runner_state.uptime_seconds() < limit
        else:
            ok = age <= limit
        body = {
            "ok": ok,
            "heartbeat_age_seconds": None if age is None else round(age, 1),
            "stale_after_seconds": limit,
        }
        return JSONResponse(body, status_code=200 if ok else 503)

    @app.get("/admin", response_class=HTMLResponse)
    def admin() -> HTMLResponse:
        return HTMLResponse(_status_page())

    @app.get("/admin/settings", response_class=HTMLResponse)
    def admin_settings() -> HTMLResponse:
        return HTMLResponse(_settings_page())

    @app.post("/admin/api/settings")
    async def admin_api_settings(request: Request, _: None = Depends(_require_admin_token)) -> dict:
        # The token dependency runs before the body is read, so an
        # unauthenticated probe gets 401 rather than a schema description.
        try:
            raw = await request.json()
        except ValueError as e:  # json.JSONDecodeError and bad UTF-8 are ValueErrors
            raise HTTPException(status_code=400, detail="Invalid JSON body") from e
        try:
            payload = RuntimeSettingsPayload.model_validate(raw)
        except ValidationError as e:
            # include_context=False: custom validators put a live ValueError in
            # ctx, which is not JSON-serializable and would turn this into a 500.
            raise HTTPException(
                status_code=422,
                detail=e.errors(include_context=False, include_input=False, include_url=False),
            ) from e
        try:
            persisted = await run_in_threadpool(_save_settings, payload)
        except OSError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Could not write SETTINGS_FILE ({e.strerror or e}); live settings unchanged",
            ) from e
        return {"ok": True, "persisted": persisted}

    return app
