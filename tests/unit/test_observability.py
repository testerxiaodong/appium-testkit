"""Failure evidence, including the real pytest fixture lifecycle."""

import json
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest
from appium_testkit.observability import capture_failure, redact_xml
from appium_testkit.telemetry import (
    Observation,
    PageStateError,
    observe_commands,
    redact,
    step,
)
from apps.kazumi.diagnostics import collect_kazumi_network
from apps.kazumi.pages.main_page import MainPage
from apps.kazumi.pages.recommendations_page import (
    RecommendationsPage,
    recommendation_state,
)

pytest_plugins = ["pytester"]


def test_page_xml_remains_parseable_and_secure_input_is_masked():
    source = '<root><node password="true" text="hidden"/><node password="false" text="推荐"/></root>'
    result = redact_xml(source)
    root = ElementTree.fromstring(result)
    assert "hidden" not in result
    assert root[1].get("text") == "推荐"


def test_allure_and_traced_step_preserve_named_method_arguments():
    with pytest.raises(ValueError, match="Unknown Kazumi"):
        MainPage(SimpleNamespace()).select_tab("invalid-tab")


def target():
    return SimpleNamespace(
        name="android-test", platform="android", app_id="example.app"
    )


def test_command_timeline_preserves_failure_without_recording_typed_secret(tmp_path):
    recorder = Observation(tmp_path, "run", "case", target())

    def execute(command, params=None):
        if command == "clickElement":
            raise RuntimeError("token=private-value")
        return {"value": "private-response"}

    driver = SimpleNamespace(execute=execute, session_id="session", capabilities={})
    observe_commands(driver, recorder)
    token = recorder.bind()
    try:
        with pytest.raises(RuntimeError):
            with step("business action"):
                driver.execute("sendKeysToElement", {"text": "private-input"})
                driver.execute("clickElement", {})
    finally:
        recorder.unbind(token)
    raw = (tmp_path / "events.jsonl").read_text()
    assert "private-input" not in raw
    assert "private-response" not in raw
    assert "private-value" not in raw
    events = [json.loads(line) for line in raw.splitlines()]
    assert events[-1]["event"] == "step.failed"
    assert events[-2]["event"] == "command.failed"
    assert events[-1]["step_id"] == events[-2]["step_id"]
    assert events[-1]["session_id"] == "session"


@pytest.mark.parametrize(
    "secret",
    [
        {"api_key": "hidden"},
        {"Authorization": "hidden"},
        'password="hidden"',
        '{"token": "hidden"}',
        "https://example.test/?token=hidden&limit=1",
        "Bearer hidden",
    ],
)
def test_redaction_handles_structured_and_text_credentials(secret):
    assert "hidden" not in str(redact(secret))


def test_failed_screenshot_does_not_prevent_other_evidence(tmp_path):
    driver = SimpleNamespace(
        save_screenshot=lambda _: False,
        page_source="<hierarchy />",
        capabilities={"token": "secret"},
    )
    capture_failure(driver, tmp_path, system_logs=False)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert "screenshot.png" in manifest["unavailable"]
    assert (tmp_path / "page-source.xml").exists()
    assert "secret" not in (tmp_path / "capabilities.json").read_text()


def test_visible_network_error_fails_before_title_lookup():
    driver = SimpleNamespace(
        page_source='<hierarchy><node content-desc="暂时无法加载番剧" /></hierarchy>',
        capabilities={"platformName": "android"},
        find_elements=lambda *args: [],
    )
    page = RecommendationsPage(driver, timeout=0.1)
    page.dismiss_transient_overlays = lambda: False
    with pytest.raises(PageStateError, match="data_load_failed"):
        page.wait_for_subject(622288, "FX战士久留美")


def test_hidden_error_does_not_override_visible_content():
    source = '<root><node visible="false"><node label="暂时无法加载番剧" /></node><node label="title" /></root>'
    assert recommendation_state(source, "title")[0] == "content_ready"


def test_network_diagnostics_preserves_unknown_instead_of_inventing_cause(tmp_path):
    (tmp_path / "app-log-excerpt.txt").write_text(
        "16:33:41 HTTP: <-- unknown GET https://api.example/list 669ms\n"
    )
    result = collect_kazumi_network(tmp_path)
    assert result["requests"][0]["status"] == "unknown"
    assert result["requests"][0]["duration"] == "669"


def test_evidence_survives_setup_call_teardown_and_session_creation_failure(
    pytester, monkeypatch
):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("PYTHONPATH", str(root))
    pytester.makeconftest("""
import pytest
from types import SimpleNamespace
import appium_testkit.pytest_plugin as plugin
pytest_plugins = ["appium_testkit.pytest_plugin"]
target = SimpleNamespace(name="fake", platform="android", app_id="example.app",
                         udid="fake", lock_key="observability-unit-device")
plugin.load_targets = lambda *a, **kw: [target]
class Driver:
    session_id = "fake-session"
    capabilities = {"platformName": "android"}
    page_source = "<hierarchy/>"
    def execute(self, command, params=None): return {}
    def save_screenshot(self, path):
        from pathlib import Path
        Path(path).write_bytes(b"fake-png")
        return True
    def quit(self): self.execute("quit")
plugin.create_driver = lambda _, **kwargs: Driver()
@pytest.fixture(scope="session")
def appium_service(): yield None
@pytest.fixture(autouse=True)
def no_device_logs(monkeypatch):
    import appium_testkit.observability as obs
    def unavailable(*a, **kw): raise OSError("collector unavailable")
    monkeypatch.setattr(obs.subprocess, "run", unavailable)
@pytest.fixture
def broken_setup(driver): raise RuntimeError("setup-original")
@pytest.fixture
def broken_teardown(driver):
    yield
    raise RuntimeError("teardown-original")
@pytest.fixture
def broken_creation(monkeypatch):
    def fail(_, **kwargs): raise RuntimeError("creation-original")
    monkeypatch.setattr(plugin, "create_driver", fail)
""")
    pytester.makepyfile("""
def test_setup(broken_setup): pass
def test_call(driver): raise RuntimeError("call-original")
def test_teardown(broken_teardown): pass
def test_creation(broken_creation, driver): pass
""")
    evidence = pytester.path / "evidence"
    result = pytester.runpytest_subprocess(
        "-q", "--artifacts-dir", str(evidence), "--run-id", "lifecycle"
    )
    result.assert_outcomes(passed=1, failed=1, errors=3)
    failures = [json.loads(p.read_text()) for p in evidence.rglob("failure.json")]
    assert {f["message"] for f in failures} == {
        "setup-original",
        "call-original",
        "teardown-original",
        "creation-original",
    }
    assert {f["phase"] for f in failures} == {"setup", "call", "teardown"}
    assert list(evidence.rglob("before-session-close/page-source.xml"))
    manifests = [json.loads(p.read_text()) for p in evidence.rglob("manifest.json")]
    assert any("driver" in m["unavailable"] for m in manifests)
