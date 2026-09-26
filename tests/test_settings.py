from __future__ import annotations

import json
import os
import stat
from email.message import Message

import pytest
from pydantic import ValidationError

import runner_state
import settings_store
from settings_validation import RuntimeSettingsPayload

BASE = {"website_url": "https://a.example/", "email_sender": "a@b.co", "email_receiver1": "c@d.co"}


# ------------------------------------------------------------------ validation
def test_valid_payload_defaults_optional_fields():
    p = RuntimeSettingsPayload.model_validate(BASE)
    assert (p.website_url_2, p.email_receiver2, p.email_receiver3) == ("", "", "")


@pytest.mark.parametrize(
    "field,value",
    [
        ("website_url", "ftp://a.example/"),
        ("website_url", "https://"),
        ("website_url", "https://user:pw@a.example/"),
        ("website_url", "https://a.example/\nX-Injected: 1"),
        ("website_url", "   "),
        ("website_url_2", "javascript:alert(1)"),
        ("email_receiver2", "not-an-email"),
    ],
)
def test_invalid_payloads_rejected(field, value):
    with pytest.raises(ValidationError):
        RuntimeSettingsPayload.model_validate({**BASE, field: value})


def test_smtp_keys_rejected():
    with pytest.raises(ValidationError):
        RuntimeSettingsPayload.model_validate({**BASE, "SMTP_PASSWORD": "x"})


def test_optional_receiver_is_normalized_not_raw():
    raw = '"a\nBcc: x@y" <x@y.com>'
    try:
        p = RuntimeSettingsPayload.model_validate({**BASE, "email_receiver2": raw})
    except ValidationError:
        return  # rejecting it outright is also safe
    assert "\n" not in p.email_receiver2
    msg = Message()
    msg["To"] = p.email_receiver2
    msg.as_string()  # must not raise HeaderParseError


# ------------------------------------------------------------------ store
def test_placeholder_url_is_not_monitored(monkeypatch):
    monkeypatch.setenv("WEBSITE_URL", "The website address you would like to check")
    monkeypatch.setenv("WEBSITE_URL_2", "https://b.example/")
    settings_store.load_from_environ()
    assert settings_store.get_monitored_urls() == ["https://b.example/"]


def test_receivers_skip_empty_and_duplicates(monkeypatch):
    monkeypatch.setenv("EMAIL_RECEIVER1", "a@example.com")
    monkeypatch.setenv("EMAIL_RECEIVER3", "a@example.com")
    monkeypatch.setenv("EMAIL_RECEIVER4", "b@example.com")
    settings_store.load_from_environ()
    assert settings_store.get_receiver_emails() == ["a@example.com", "b@example.com"]


def test_settings_file_overlays_env_and_roundtrips(monkeypatch, tmp_path):
    path = tmp_path / "settings.json"
    monkeypatch.setenv("WEBSITE_URL", "https://env.example/")
    monkeypatch.setenv("EMAIL_SENDER", "env@example.com")
    monkeypatch.setenv("SETTINGS_FILE", str(path))
    settings_store.write_file(str(path), {"WEBSITE_URL": "https://file.example/", "EMAIL_RECEIVER1": "f@example.com"})
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    settings_store.load_from_environ()
    assert settings_store.loaded_from_file()
    url, _, sender, r1, *_ = settings_store.snapshot()
    # The file stores every key, so an empty sender in the file wins over env.
    assert (url, sender, r1) == ("https://file.example/", "", "f@example.com")


def test_corrupt_settings_file_is_ignored(monkeypatch, tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not json")
    monkeypatch.setenv("SETTINGS_FILE", str(path))
    monkeypatch.setenv("WEBSITE_URL", "https://env.example/")
    settings_store.load_from_environ()
    assert not settings_store.loaded_from_file()
    assert settings_store.get_monitored_urls() == ["https://env.example/"]
    path.write_text(json.dumps(["not", "an", "object"]))
    settings_store.load_from_environ()
    assert not settings_store.loaded_from_file()


# ------------------------------------------------------------------ runner_state
def test_format_local_handles_bad_input():
    assert runner_state.format_local(None) == ""
    assert runner_state.format_local("garbage") == "garbage"
    assert runner_state.format_local("2026-05-22T13:51:21.618624Z").startswith("2026-05-22 ")


def test_history_is_newest_first_and_capped():
    for i in range(runner_state.RECENT_POLL_MAX + 5):
        runner_state.record_poll(ok=True, md5_hex=f"{i:032x}", url="https://a/")
    rows = runner_state.get_recent_polls(1000)
    assert len(rows) == runner_state.RECENT_POLL_MAX
    assert rows[0].md5_full == f"{runner_state.RECENT_POLL_MAX + 4:032x}"


def test_record_change_marks_latest_row_for_url():
    runner_state.record_poll(ok=True, md5_hex="a" * 32, url="https://a/")
    runner_state.record_poll(ok=True, md5_hex="b" * 32, url="https://b/")
    runner_state.record_change("https://a/")
    rows = runner_state.get_recent_polls()
    assert [r.changed for r in rows] == [False, True]
    assert runner_state.get_poll_snapshot().last_change_url == "https://a/"
