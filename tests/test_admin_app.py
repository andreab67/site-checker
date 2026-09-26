from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import admin_app
import runner_state
import settings_store

TOKEN = "s3cret-admin-token"
BODY = {"website_url": "https://new.example/", "email_sender": "a@b.co", "email_receiver1": "c@d.co"}


@pytest.fixture()
def client(configured):
    return TestClient(admin_app.create_app())


def post(client, body=BODY, token=TOKEN, **kw):
    headers = {"X-Admin-Token": token} if token is not None else {}
    return client.post("/admin/api/settings", headers=headers, json=body, **kw)


def test_pages_render_with_security_headers(client):
    runner_state.record_poll(ok=True, md5_hex="f" * 32, url="https://watch.example/page",
                             http_status=200, elapsed_ms=12.5, content_length=1234)
    for path in ("/", "/admin", "/admin/settings"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "script-src 'self'" in r.headers["content-security-policy"]
        assert r.headers["x-frame-options"] == "DENY"
    home = client.get("/").text
    assert "ffffffff" in home and "1,234 bytes" in home
    assert client.get("/static/site-checker.css").status_code == 200


def test_status_board_never_renders_smtp_secrets(client, monkeypatch):
    monkeypatch.setenv("SMTP_USERNAME", "AKIAEXAMPLEUSER")
    monkeypatch.setenv("SMTP_PASSWORD", "super-secret-password")
    text = client.get("/admin").text
    assert "AKIAEXAMPLEUSER" not in text and "super-secret-password" not in text


def test_values_are_escaped(client):
    settings_store.apply_updates(website_url="https://x.example/?q=<script>alert(1)</script>",
                                 website_url_2="", email_sender="a@b.co", email_receiver1="c@d.co",
                                 email_receiver2="", email_receiver3="", email_receiver4="")
    for path in ("/admin", "/admin/settings"):
        text = client.get(path).text
        assert "<script>alert(1)</script>" not in text
        assert "&lt;script&gt;" in text


def test_save_503_when_token_unset(client):
    assert post(client).status_code == 503


def test_save_401_on_bad_or_missing_token(client, monkeypatch):
    monkeypatch.setenv("SITE_CHECKER_ADMIN_TOKEN", TOKEN)
    assert post(client, token="wrong").status_code == 401
    assert post(client, token=None).status_code == 401


def test_401_before_body_parsing(client, monkeypatch):
    monkeypatch.setenv("SITE_CHECKER_ADMIN_TOKEN", TOKEN)
    r = client.post("/admin/api/settings", headers={"X-Admin-Token": "wrong"}, content=b"{not json")
    assert r.status_code == 401


def test_422_from_custom_validator_is_json_not_500(client, monkeypatch):
    monkeypatch.setenv("SITE_CHECKER_ADMIN_TOKEN", TOKEN)
    r = post(client, body={**BODY, "website_url": "ftp://nope.example/"})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "input" not in detail[0] and "ctx" not in detail[0]
    assert "http or https" in detail[0]["msg"]


def test_save_applies_in_memory_without_settings_file(client, monkeypatch):
    monkeypatch.setenv("SITE_CHECKER_ADMIN_TOKEN", TOKEN)
    r = post(client, body={**BODY, "email_receiver2": "  e@f.co "})
    assert r.status_code == 200 and r.json() == {"ok": True, "persisted": False}
    assert settings_store.get_monitored_urls() == ["https://new.example/"]
    assert settings_store.get_receiver_emails() == ["c@d.co", "e@f.co"]


def test_save_persists_to_settings_file(client, monkeypatch, tmp_path):
    path = tmp_path / "settings.json"
    monkeypatch.setenv("SITE_CHECKER_ADMIN_TOKEN", TOKEN)
    monkeypatch.setenv("SETTINGS_FILE", str(path))
    r = post(client)
    assert r.status_code == 200 and r.json()["persisted"] is True
    data = json.loads(path.read_text())
    assert data["WEBSITE_URL"] == "https://new.example/" and data["EMAIL_RECEIVER1"] == "c@d.co"
    assert "SMTP_PASSWORD" not in data


def test_failed_write_leaves_live_settings_untouched(client, monkeypatch, tmp_path):
    monkeypatch.setenv("SITE_CHECKER_ADMIN_TOKEN", TOKEN)
    monkeypatch.setenv("SETTINGS_FILE", str(tmp_path / "missing-dir" / "settings.json"))
    before = settings_store.snapshot()
    r = post(client)
    assert r.status_code == 500 and "live settings unchanged" in r.json()["detail"]
    assert settings_store.snapshot() == before


def test_healthz_tracks_monitor_heartbeat(client, monkeypatch):
    assert client.get("/healthz").status_code == 200  # startup grace
    runner_state.heartbeat()
    assert client.get("/healthz").json()["ok"] is True
    monkeypatch.setattr(runner_state, "heartbeat_age_seconds", lambda: 10_000.0)
    r = client.get("/healthz")
    assert r.status_code == 503 and r.json()["ok"] is False
    assert "stalled" in client.get("/").text


def test_healthz_fails_if_loop_never_starts(client, monkeypatch):
    monkeypatch.setattr(runner_state, "uptime_seconds", lambda: 10_000.0)
    assert client.get("/healthz").status_code == 503


def test_check_interval_parsing(monkeypatch):
    assert admin_app.check_interval_seconds() == 300
    monkeypatch.setenv("CHECK_INTERVAL_SECONDS", "5")
    assert admin_app.check_interval_seconds() == 30
    monkeypatch.setenv("CHECK_INTERVAL_SECONDS", "junk")
    assert admin_app.check_interval_seconds() == 300
