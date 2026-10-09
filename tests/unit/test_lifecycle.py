from types import SimpleNamespace

import pytest
from appium_testkit.lifecycle import Cleanup, prepared_state

pytest_plugins = ["pytester"]


def context(events):
    return SimpleNamespace(
        terminate_app=lambda _: events.append("stop"),
        activate_app=lambda _: events.append("start"),
    ), SimpleNamespace(app_id="test.app")


@pytest.mark.parametrize("launch", ["restart", "preserve"])
def test_order_and_reverse_cleanup(launch):
    events = []
    driver, target = context(events)

    class Provider:
        def prepare(self, **kwargs):
            events.append("prepare")
            kwargs["cleanup"].register("first", lambda: events.append("first"))
            kwargs["cleanup"].register("second", lambda: events.append("second"))

        def verify(self, **kwargs):
            events.append("verify")

    with prepared_state(
        driver,
        target,
        launch=launch,
        provider=Provider(),
        auth=lambda: events.append("auth"),
    ):
        events.append("test")
    prefix = ["stop", "start"] if launch == "restart" else []
    assert events == [*prefix, "prepare", "auth", "verify", "test", "second", "first"]


@pytest.mark.parametrize("phase", ["prepare", "auth", "verify", "call"])
def test_partial_failure_always_cleans_up(phase):
    events = []
    driver, target = context(events)

    def fail(name):
        if name == phase:
            raise RuntimeError(name)

    class Provider:
        def prepare(self, **kwargs):
            kwargs["cleanup"].register("release", lambda: events.append("released"))
            fail("prepare")

        def verify(self, **kwargs):
            fail("verify")

    with pytest.raises(RuntimeError, match=phase):
        with prepared_state(
            driver, target, provider=Provider(), auth=lambda: fail("auth")
        ):
            fail("call")
    assert events[-1] == "released"


def test_cleanup_attempts_every_callback_and_reports_errors():
    cleanup = Cleanup()
    events = []
    cleanup.register("first", lambda: events.append("first"))

    def broken():
        raise RuntimeError("cleanup failed")

    cleanup.register("broken", broken)
    with pytest.raises(ExceptionGroup) as result:
        cleanup.run()
    assert events == ["first"]
    assert str(result.value.exceptions[0]) == "cleanup failed"
    cleanup.run()  # callbacks are not executed twice


def test_cleanup_failure_does_not_replace_original():
    driver, target = context([])

    class Provider:
        def prepare(self, **kwargs):
            def broken():
                raise RuntimeError("cleanup")

            kwargs["cleanup"].register("broken", broken)
            raise ValueError("original")

    with pytest.raises(ValueError, match="original") as result:
        with prepared_state(driver, target, provider=Provider()):
            pytest.fail("must not execute")
    assert result.value.__notes__


def test_invalid_policy_does_not_touch_app():
    events = []
    driver, target = context(events)
    with pytest.raises(ValueError, match="Unsupported"):
        with prepared_state(driver, target, launch="unknown"):
            pass
    assert events == []


def test_pytest_fixture_order_and_cleanup_before_driver_close(pytester, monkeypatch):
    from pathlib import Path

    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[2]))
    pytester.makeconftest("""
import pytest
from types import SimpleNamespace
pytest_plugins = ['appium_testkit.pytest_plugin']
import appium_testkit.pytest_plugin as plugin
plugin.load_targets = lambda *a, **kw: [SimpleNamespace(name='fake', app_id='test', platform='android')]
events = []
@pytest.fixture
def target(): return SimpleNamespace(app_id='test')
@pytest.fixture
def driver():
    yield SimpleNamespace(terminate_app=lambda _: events.append('stop'),
                          activate_app=lambda _: events.append('start'))
    assert events[-1] == 'cleanup'
@pytest.fixture
def auth_state_provider():
    return SimpleNamespace(ensure_state=lambda **kw: events.append(kw['state']))
@pytest.fixture
def app_state_provider():
    def prepare(**kw):
        events.append('prepare')
        kw['cleanup'].register('cleanup', lambda: events.append('cleanup'))
    return SimpleNamespace(prepare=prepare, verify=lambda **kw: events.append('verify'))
""")
    pytester.makepyfile("""
import pytest
from conftest import events
@pytest.mark.auth_state('authenticated')
def test_authenticated(prepared_app, relaunched_app):
    assert prepared_app is relaunched_app
    assert events == ['stop', 'start', 'prepare', 'authenticated', 'verify']
""")
    pytester.runpytest_subprocess("-q").assert_outcomes(passed=1)


def test_overlay_registry_preserves_named_dialog_and_propagates_failure():
    from appium_testkit.overlays import OverlayHandlers

    events = []
    handlers = OverlayHandlers(
        {
            "update": lambda: events.append("update") or True,
            "permission": lambda: events.append("permission") or False,
        },
        preserved=["update"],
    )
    assert not handlers.handle()
    assert events == ["permission"]

    def broken():
        raise RuntimeError("overlay failure")

    with pytest.raises(RuntimeError, match="overlay failure"):
        OverlayHandlers({"known": broken}).handle()


def test_overlay_registry_runs_all_handlers_after_first_success():
    from appium_testkit.overlays import OverlayHandlers

    events = []
    assert OverlayHandlers(
        {
            "first": lambda: events.append(1) or True,
            "second": lambda: events.append(2) or False,
        }
    ).handle()
    assert events == [1, 2]


@pytest.mark.parametrize("state", ["authenticated", "invalid"])
def test_auth_configuration_failure_stops_before_restart(pytester, monkeypatch, state):
    from pathlib import Path

    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[2]))
    pytester.makeconftest("""
import pytest
from types import SimpleNamespace
import appium_testkit.pytest_plugin as plugin
pytest_plugins = ['appium_testkit.pytest_plugin']
plugin.load_targets = lambda *a, **kw: [SimpleNamespace(name='fake', app_id='test', platform='android')]
@pytest.fixture
def driver():
    def unexpected(*a): raise AssertionError('must not restart')
    return SimpleNamespace(terminate_app=unexpected, activate_app=unexpected)
""")
    pytester.makepyfile(f"""
import pytest
@pytest.mark.auth_state({state!r})
def test_auth(prepared_app):
    pytest.fail('body must not run')
""")
    result = pytester.runpytest_subprocess("-q")
    result.assert_outcomes(errors=1)
    output = result.stdout.str()
    assert "must not restart" not in output
    assert (
        "requires an auth_state_provider"
        if state == "authenticated"
        else "Unsupported auth_state"
    ) in output


def test_prepared_fixture_reports_original_and_cleanup_errors(pytester, monkeypatch):
    from pathlib import Path

    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[2]))
    pytester.makeconftest("""
import pytest
from pathlib import Path
from types import SimpleNamespace
import appium_testkit.pytest_plugin as plugin
pytest_plugins = ['appium_testkit.pytest_plugin']
plugin.load_targets = lambda *a, **kw: [SimpleNamespace(name='fake', app_id='test', platform='android')]
@pytest.fixture
def driver(request):
    yield SimpleNamespace(terminate_app=lambda _: None, activate_app=lambda _: None)
    with Path('closed.txt').open('a') as stream:
        stream.write(request.node.originalname + '\\n')
@pytest.fixture
def app_state_provider(request):
    def cleanup(): raise RuntimeError('cleanup-original')
    def prepare(**kw):
        kw['cleanup'].register('release', cleanup)
        if request.node.originalname == 'test_setup':
            raise ValueError('setup-original')
    return SimpleNamespace(prepare=prepare, verify=lambda **kw: None)
""")
    pytester.makepyfile("""
def test_setup(prepared_app): raise AssertionError('must not reach body')
def test_teardown(prepared_app): pass
def test_call(prepared_app): raise ValueError('call-original')
""")
    result = pytester.runpytest_subprocess("-q")
    result.assert_outcomes(passed=1, failed=1, errors=3)
    output = result.stdout.str()
    assert "setup-original" in output
    assert "call-original" in output
    assert "cleanup-original" in output
    assert (pytester.path / "closed.txt").read_text().splitlines() == [
        "test_setup",
        "test_teardown",
        "test_call",
    ]


def test_xdist_applies_device_groups_before_scheduling(pytester, monkeypatch):
    from pathlib import Path

    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[2]))
    pytester.makeconftest("""
from types import SimpleNamespace
import appium_testkit.pytest_plugin as plugin
pytest_plugins = ['appium_testkit.pytest_plugin']
plugin.load_targets = lambda *a, **kw: [
    SimpleNamespace(name=name, app_id='test', platform='android')
    for name in ('device_a', 'device_b')
]
""")
    pytester.makepyfile("""
import pytest
@pytest.mark.parametrize('case', range(4))
def test_group(target, case, request):
    assert request.node.nodeid.endswith('@' + target.name)
""")
    pytester.runpytest_subprocess(
        "-q", "-n", "2", "--dist", "loadgroup"
    ).assert_outcomes(passed=8)
