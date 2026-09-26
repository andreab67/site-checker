from __future__ import annotations

from typing import ClassVar

import pytest
import requests

import monitor
import runner_state
import settings_store


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self.content = body
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"{self.status_code} Error")
            err.response = self
            raise err


class FakeSMTP:
    instances: ClassVar[list[FakeSMTP]] = []
    fail = False

    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.timeout = host, port, timeout
        self.sent = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        if FakeSMTP.fail:
            raise OSError("connection refused")
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        pass

    def sendmail(self, sender, receivers, msg):
        self.sent.append((sender, list(receivers), msg))


@pytest.fixture()
def smtp(monkeypatch):
    FakeSMTP.instances = []
    FakeSMTP.fail = False
    monkeypatch.setattr(monitor.smtplib, "SMTP_SSL", FakeSMTP)
    return FakeSMTP


@pytest.fixture()
def pages(monkeypatch):
    bodies: dict[str, object] = {}
    calls = []

    def fake_get(url, timeout=None):
        calls.append((url, timeout))
        b = bodies[url]
        if isinstance(b, Exception):
            raise b
        return FakeResponse(*b) if isinstance(b, tuple) else FakeResponse(b)

    monkeypatch.setattr(monitor.requests, "get", fake_get)
    return bodies, calls


URL = "https://watch.example/page"


def test_fetch_uses_timeout_and_records_poll(configured, pages):
    bodies, calls = pages
    bodies[URL] = b"hello"
    h = monitor.fetch_website_content(URL)
    assert h == "5d41402abc4b2a76b9719d911017c592"
    assert calls[0][1] == monitor.FETCH_TIMEOUT
    row = runner_state.get_recent_polls()[0]
    assert (row.ok, row.http_status, row.content_length) == (True, 200, 5)


def test_fetch_failure_records_status(configured, pages):
    bodies, _ = pages
    bodies[URL] = (b"nope", 503)
    assert monitor.fetch_website_content(URL) is None
    row = runner_state.get_recent_polls()[0]
    assert row.ok is False and row.http_status == 503 and "HTTPError" in row.error_detail


def test_send_email_with_single_receiver(configured, smtp):
    # Original code joined [RECEIVER1, None] and raised TypeError when
    # EMAIL_RECEIVER2 was unset.
    assert monitor.send_email("s", "b") is True
    inst = smtp.instances[0]
    assert inst.timeout == monitor.SMTP_TIMEOUT and inst.port == 465
    assert inst.sent[0][1] == ["me@example.com"]
    assert runner_state.get_poll_snapshot().last_email_ok is True


def test_send_email_without_receivers_fails_cleanly(smtp, monkeypatch):
    monkeypatch.setenv("EMAIL_SENDER", "alerts@example.com")
    settings_store.load_from_environ()
    assert monitor.send_email("s", "b") is False
    assert smtp.instances == []
    assert runner_state.get_poll_snapshot().last_email_ok is False


def test_baseline_then_change_sends_one_alert(configured, pages, smtp):
    bodies, _ = pages
    state: dict[str, str] = {}
    bodies[URL] = b"v1"
    monitor.check_once(state)
    assert smtp.instances == [] and URL in state
    monitor.check_once(state)
    assert smtp.instances == []
    bodies[URL] = b"v2"
    monitor.check_once(state)
    assert len(smtp.instances) == 1
    assert "watch.example/page" in smtp.instances[0].sent[0][2]
    monitor.check_once(state)
    assert len(smtp.instances) == 1
    assert runner_state.get_recent_polls()[1].changed is True


def test_failed_alert_is_retried_next_poll(configured, pages, smtp):
    bodies, _ = pages
    state: dict[str, str] = {}
    bodies[URL] = b"v1"
    monitor.check_once(state)
    bodies[URL] = b"v2"
    smtp.fail = True
    monitor.check_once(state)
    assert state[URL] == monitor.hashlib.md5(b"v1").hexdigest()
    smtp.fail = False
    monitor.check_once(state)
    assert state[URL] == monitor.hashlib.md5(b"v2").hexdigest()
    assert sum(len(i.sent) for i in smtp.instances) == 1


def test_fetch_error_does_not_reset_baseline(configured, pages, smtp):
    bodies, _ = pages
    state: dict[str, str] = {}
    bodies[URL] = b"v1"
    monitor.check_once(state)
    bodies[URL] = requests.ConnectionError("down")
    monitor.check_once(state)
    bodies[URL] = b"v1"
    monitor.check_once(state)
    assert smtp.instances == []


def test_url_changes_from_gui_are_picked_up(configured, pages, smtp):
    bodies, _ = pages
    state: dict[str, str] = {}
    bodies[URL] = b"v1"
    monitor.check_once(state)
    other = "https://other.example/"
    bodies[other] = b"x"
    settings_store.apply_updates(website_url=other, website_url_2="", email_sender="a@b.co",
                                 email_receiver1="c@d.co", email_receiver2="", email_receiver3="",
                                 email_receiver4="")
    monitor.check_once(state)
    assert list(state) == [other]  # old URL dropped, new one baselined (no alert)
    assert smtp.instances == []


def test_no_urls_is_a_noop(pages):
    state: dict[str, str] = {}
    monitor.check_once(state)
    assert state == {} and pages[1] == []
