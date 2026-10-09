"""Lifecycle and payload contract tests without Docker or mobile devices."""

from types import SimpleNamespace

import pytest
from appium_testkit.mocking.wiremock import WireMock
from apps.kazumi.mocking.update import UpdateMockSession, release_mapping


def test_override_removes_exact_rule_after_failure(monkeypatch):
    client = WireMock("http://localhost:1")
    removed = []
    monkeypatch.setattr(client, "add", lambda _: "owned-id")
    monkeypatch.setattr(client, "remove", removed.append)
    with pytest.raises(ValueError):
        with client.override({}) as mapping_id:
            assert mapping_id == "owned-id"
            raise ValueError("test")
    assert removed == ["owned-id"]


def test_evidence_does_not_export_credentials(monkeypatch):
    client = WireMock("http://localhost:1")
    monkeypatch.setattr(
        client,
        "events",
        lambda: [
            {
                "request": {
                    "method": "GET",
                    "url": "/update?token=secret",
                    "headers": {"Authorization": "secret"},
                    "body": "secret",
                },
                "response": {"body": "secret"},
                "wasMatched": True,
                "stubMapping": {"id": "id"},
            }
        ],
    )
    assert "secret" not in str(client.evidence())
    assert client.evidence()["requests"][0]["path"] == "/update"


def test_missing_rule_does_not_pass(monkeypatch):
    client = WireMock("http://localhost:1")
    monkeypatch.setattr(client, "events", lambda: [])
    with pytest.raises(AssertionError, match="did not complete"):
        client.wait_for_mapping("missing", timeout=0)


def test_release_payload_matches_app_contract():
    mapping = release_mapping(version="99.0.0", delay_ms=15000)
    assert mapping["request"]["urlPath"] == "/kazumi/v1/app/latest"
    assert mapping["response"]["jsonBody"]["tag_name"] == "99.0.0"
    assert mapping["response"]["fixedDelayMilliseconds"] == 15000
    assert mapping["priority"] < 100


@pytest.mark.parametrize("platform", ["android", "ios"])
def test_rules_exist_before_device_launch(platform):
    calls = []
    driver = SimpleNamespace(
        terminate_app=lambda _: calls.append("stop"),
        execute_script=lambda command, args: calls.append((command, args)),
    )
    client = SimpleNamespace(
        reset=lambda: calls.append("reset"),
        proxy=lambda _: calls.append("proxy"),
        add=lambda _: calls.append("add") or "mapping-id",
    )
    target = SimpleNamespace(platform=platform, app_id="app.id")
    session = UpdateMockSession(driver, target, client, "http://127.0.0.1:8089")
    session.launch()
    assert calls[:4] == ["stop", "reset", "proxy", "add"]
    command, args = calls[4]
    if platform == "android":
        assert command == "mobile: startActivity"
        assert "intent" not in args
        assert args["component"] == "app.id/com.example.kazumi.MainActivity"
        assert args["extras"] == [["s", "kazumiTestUpdateBaseUrl", session.app_url]]
    else:
        assert command == "mobile: launchApp"
        assert args["arguments"] == ["--kazumi-test-update-base-url", session.app_url]
