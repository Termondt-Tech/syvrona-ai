"""Mailgun sends have a timeout and cannot break the caller's request (D11)."""

import pytest
import requests

from app import utils


class Reply:
    def __init__(self, status):
        self.status_code = status
        self.ok = status < 400
        self.text = "body"


@pytest.fixture
def mail_config(app):
    app.config.update(MAILGUN_DOMAIN="mg.example.com", MAILGUN_API_KEY="key-test")
    return app


def test_send_uses_a_timeout_and_reports_success(mail_config, monkeypatch):
    seen = {}

    def fake_post(url, **kwargs):
        seen.update(kwargs, url=url)
        return Reply(200)

    monkeypatch.setattr(utils.requests, "post", fake_post)
    assert utils.send_mailgun_message("a@example.com", "Subject", "text") is True
    assert seen["timeout"] == utils.MAILGUN_TIMEOUT
    assert seen["url"] == "https://api.mailgun.net/v3/mg.example.com/messages"


def test_network_failure_is_logged_not_raised(mail_config, monkeypatch, caplog):
    def fake_post(url, **kwargs):
        raise requests.Timeout("read timed out")

    monkeypatch.setattr(utils.requests, "post", fake_post)
    assert utils.send_mailgun_message("a@example.com", "Subject", "text") is False
    assert "Mailgun send failed" in caplog.text


def test_rejection_is_logged_not_raised(mail_config, monkeypatch, caplog):
    monkeypatch.setattr(utils.requests, "post", lambda url, **kw: Reply(401))
    assert utils.send_mailgun_message("a@example.com", "Subject", "text") is False
    assert "status=401" in caplog.text
