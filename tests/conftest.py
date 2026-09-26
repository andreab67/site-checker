from __future__ import annotations

import pytest

import runner_state
import settings_store

ENV_KEYS = (
    *settings_store.KEYS,
    "SETTINGS_FILE",
    "SITE_CHECKER_ADMIN_TOKEN",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_HOST",
    "CHECK_INTERVAL_SECONDS",
)


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    for k in ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    settings_store.load_from_environ()
    runner_state.reset_for_tests()
    yield
    runner_state.reset_for_tests()


@pytest.fixture()
def configured(monkeypatch):
    monkeypatch.setenv("WEBSITE_URL", "https://watch.example/page")
    monkeypatch.setenv("EMAIL_SENDER", "alerts@example.com")
    monkeypatch.setenv("EMAIL_RECEIVER1", "me@example.com")
    settings_store.load_from_environ()
