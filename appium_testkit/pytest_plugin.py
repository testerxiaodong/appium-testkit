"""Pytest integration: device matrix, leases, lifecycle and failure evidence."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from appium_testkit.appium_service import managed_appium_server
from appium_testkit.config import PROJECT_ROOT, TestTarget, load_targets
from appium_testkit.device_lock import DEFAULT_LOCK_DIR, device_lease
from appium_testkit.driver_factory import create_driver
from appium_testkit.observability import (
    application_metadata,
    attach_evidence,
    capture_failure,
    configure_logging,
    test_artifact_dir,
)
from appium_testkit.preflight import supports, validate_package
from appium_testkit.telemetry import Observation, observe_commands, redact, step


def pytest_addoption(parser):
    group = parser.getgroup("appium", "cross-platform Appium options")
    group.addoption(
        "--preflight-only",
        action="store_true",
        help="Validate selected packages without starting Appium",
    )
    group.addoption(
        "--strict-capabilities",
        action="store_true",
        help="Fail collection instead of skipping unsupported device capabilities",
    )
    group.addoption(
        "--platform",
        choices=("android", "ios"),
        default=None,
        help="Filter target platform",
    )
    group.addoption(
        "--device",
        action="append",
        default=[],
        help="Configured device name; repeat to select more than one",
    )
    group.addoption(
        "--device-udid", default=None, help="Override UDID for selected targets"
    )
    group.addoption(
        "--device-matrix",
        default=None,
        help="YAML device matrix (default config/devices.yaml)",
    )
    group.addoption(
        "--app-matrix", default=None, help="YAML app matrix (default config/apps.yaml)"
    )
    group.addoption(
        "--app-name",
        action="append",
        default=[],
        help="App profile name; repeat to select more than one",
    )
    group.addoption(
        "--appium-server-url",
        default=None,
        help="Override Appium URL for selected targets",
    )
    group.addoption(
        "--no-appium-service",
        action="store_true",
        help="Do not start a missing local Appium server",
    )
    group.addoption("--app", default=None, help="Override selected app package path")
    group.addoption("--artifacts-dir", default=None, help="Artifact root directory")
    group.addoption(
        "--device-lock-timeout",
        type=float,
        default=0,
        help="Seconds to wait for a busy device lock",
    )
    group.addoption(
        "--run-id", default=None, help="Stable identifier used to group artifacts"
    )
    group.addoption(
        "--app-state",
        choices=("preserve", "clear_data", "reinstall"),
        default=None,
        help="Default app-data policy; test marker app_state overrides it",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "platform(name): run only for a platform")
    config.addinivalue_line("markers", "device(name): run only for a configured device")
    config.addinivalue_line("markers", "app(name): run only for an app profile")
    config.addinivalue_line(
        "markers",
        "update_notice_test: leave the Kazumi update notice open for a dedicated test",
    )
    config.addinivalue_line(
        "markers",
        "app_state(policy): preserve, clear_data, or reinstall before this test",
    )
    config.addinivalue_line(
        "markers",
        "auth_state(state): preserve, anonymous, or authenticated login state",
    )
    config.addinivalue_line(
        "markers",
        "permission_state(policy, *services): preserve, grant, or reset permissions",
    )
    config.addinivalue_line(
        "markers", "app_launch(policy): restart or preserve process"
    )
    config.addinivalue_line(
        "markers", "preserve_overlays(*names): leave named overlays for assertions"
    )
    config.addinivalue_line(
        "markers", "requires_capability(*names): required device capabilities"
    )
    config._appium_run_id = (
        getattr(config, "workerinput", {}).get("appium_run_id")
        or config.getoption("--run-id")
        or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    )


@pytest.hookimpl(optionalhook=True)
def pytest_configure_node(node):
    node.workerinput["appium_run_id"] = node.config._appium_run_id


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_protocol(item, nextitem):
    callspec = getattr(item, "callspec", None)
    target = callspec.params.get("target") if callspec else None
    if target is None:
        yield
        return
    root = Path(item.config.getoption("--artifacts-dir") or PROJECT_ROOT / "artifacts")
    recorder = Observation(
        test_artifact_dir(root, item.config._appium_run_id, item.nodeid, target),
        item.config._appium_run_id,
        item.nodeid,
        target,
        getattr(item.config, "workerinput", {}).get("workerid", "main"),
    )
    item._observation = recorder
    item._observation_target = target
    item._observation_server_log = (
        root / item.config._appium_run_id / "_appium" / f"{target.name}-server.log"
    )
    token = recorder.bind()
    recorder.emit("test.started")
    try:
        yield
    finally:
        recorder.emit("test.finished")
        recorder.unbind(token)


def pytest_runtest_setup(item):
    if hasattr(item, "_observation"):
        item._observation.phase = "setup"


def pytest_runtest_call(item):
    if hasattr(item, "_observation"):
        item._observation.phase = "call"


def pytest_runtest_teardown(item):
    if hasattr(item, "_observation"):
        item._observation.phase = "teardown"


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items):
    """Keep each device's parametrized tests on one xdist worker."""
    for item in items:
        callspec = getattr(item, "callspec", None)
        target = callspec.params.get("target") if callspec else None
        if target is not None:
            item.add_marker(pytest.mark.xdist_group(target.name))
            platform_marker = item.get_closest_marker("platform")
            device_marker = item.get_closest_marker("device")
            app_marker = item.get_closest_marker("app")
            if (
                platform_marker
                and platform_marker.args
                and platform_marker.args[0] != target.platform
            ):
                item.add_marker(
                    pytest.mark.skip(
                        reason=f"requires platform {platform_marker.args[0]}"
                    )
                )
            if (
                device_marker
                and device_marker.args
                and device_marker.args[0] != target.device.name
            ):
                item.add_marker(
                    pytest.mark.skip(reason=f"requires device {device_marker.args[0]}")
                )
            if app_marker and app_marker.args and app_marker.args[0] != target.app_name:
                item.add_marker(
                    pytest.mark.skip(reason=f"requires app {app_marker.args[0]}")
                )


@pytest.hookimpl(trylast=True)
def pytest_collection_finish(session):
    if session.config.option.collectonly:
        return
    targets = {}
    errors = set()
    for item in session.items:
        callspec = getattr(item, "callspec", None)
        target = callspec.params.get("target") if callspec else None
        if not isinstance(target, TestTarget) or item.get_closest_marker("skip"):
            continue
        required = {
            name
            for marker in item.iter_markers("requires_capability")
            for name in marker.args
        }
        marker = item.get_closest_marker("app_state")
        policy = (
            marker.args[0]
            if marker and marker.args
            else session.config.getoption("--app-state")
        )
        if policy == "clear_data":
            required.add("clear_app_data")
        unsupported = []
        for name in sorted(required):
            try:
                if not supports(target, name):
                    unsupported.append(name)
            except ValueError as error:
                errors.add(str(error))
        if unsupported:
            reason = f"{target.name}: unsupported capability {', '.join(unsupported)} on {target.platform} real device"
            if session.config.getoption("--strict-capabilities"):
                errors.add(reason)
            else:
                item.add_marker(pytest.mark.skip(reason=reason))
            continue
        targets[target.name] = target
    for target in targets.values():
        try:
            validate_package(target)
        except ValueError as error:
            errors.add(str(error))
    if errors:
        raise pytest.UsageError(
            "Preflight failed before creating any sessions:\n"
            + "\n".join(sorted(errors))
        )
    if session.config.getoption("--preflight-only"):
        pytest.exit(
            f"Preflight passed for {len(targets)} target(s); device connectivity and WDA startup not exercised",
            returncode=0,
        )


def pytest_generate_tests(metafunc):
    if "target" not in metafunc.fixturenames:
        return
    platform = metafunc.config.getoption("--platform") or os.getenv("APPIUM_PLATFORM")
    matrix = Path(
        metafunc.config.getoption("--device-matrix")
        or PROJECT_ROOT / "config" / "devices.yaml"
    )
    app_matrix = Path(
        metafunc.config.getoption("--app-matrix")
        or PROJECT_ROOT / "config" / "apps.yaml"
    )
    try:
        targets = load_targets(
            matrix,
            app_matrix,
            platform=platform,
            devices=set(metafunc.config.getoption("--device")) or None,
            apps=set(metafunc.config.getoption("--app-name")) or None,
            udid_override=metafunc.config.getoption("--device-udid"),
            server_override=metafunc.config.getoption("--appium-server-url"),
            app_override=metafunc.config.getoption("--app"),
        )
    except ValueError as error:
        if metafunc.config.option.collectonly:
            metafunc.parametrize(
                "target",
                [
                    pytest.param(
                        None,
                        id="target-not-configured",
                        marks=pytest.mark.skip(reason=str(error)),
                    )
                ],
            )
            return
        raise pytest.UsageError(str(error)) from error
    metafunc.parametrize(
        "target", targets, ids=[target.name for target in targets], scope="session"
    )


@pytest.fixture
def artifacts_dir(request, target):
    if hasattr(request.node, "_observation"):
        return request.node._observation.path
    root = Path(
        request.config.getoption("--artifacts-dir") or PROJECT_ROOT / "artifacts"
    )
    return test_artifact_dir(
        root, request.config._appium_run_id, request.node.nodeid, target
    )


@pytest.fixture
def test_logger(artifacts_dir, request, target):
    handler = configure_logging(
        artifacts_dir, request.config._appium_run_id, request.node.nodeid, target
    )
    logger = logging.getLogger("appium_testkit")
    try:
        yield logger
    finally:
        logger.removeHandler(handler)
        handler.close()


@pytest.fixture(scope="session")
def appium_service(target, request):
    lock_dir = DEFAULT_LOCK_DIR
    artifacts_root = Path(
        request.config.getoption("--artifacts-dir") or PROJECT_ROOT / "artifacts"
    )
    run_id = request.config._appium_run_id
    log_file = artifacts_root / run_id / "_appium" / f"{target.name}-server.log"
    with managed_appium_server(
        target,
        auto_start=not request.config.getoption("--no-appium-service"),
        lock_dir=lock_dir,
        log_file=log_file,
    ) as service:
        yield service


@pytest.fixture
def diagnostic_collectors():
    """Apps may supply functions accepting an evidence directory, returning JSON."""
    return []


@pytest.fixture
def session_capabilities():
    """App adapters may provide launch-time options before session creation."""
    return {}


@pytest.fixture
def app_launcher():
    """Optional app-specific launch callback, preserving injected configuration."""
    return None


@pytest.fixture
def driver(
    target,
    appium_service,
    request,
    artifacts_dir,
    test_logger,
    diagnostic_collectors,
    session_capabilities,
):
    lock_dir = DEFAULT_LOCK_DIR
    with device_lease(
        target.lock_key, lock_dir, request.config.getoption("--device-lock-timeout")
    ):
        app_state_marker = request.node.get_closest_marker("app_state")
        app_state = (
            app_state_marker.args[0]
            if app_state_marker and app_state_marker.args
            else request.config.getoption("--app-state") or "preserve"
        )
        if app_state not in {"preserve", "clear_data", "reinstall"}:
            raise pytest.UsageError(f"Unsupported app_state policy: {app_state}")
        if (
            app_state == "clear_data"
            and target.platform == "ios"
            and not target.is_simulator
        ):
            raise pytest.UsageError(
                "app_state('clear_data') on iOS requires a simulator; "
                "real-device data clearing is not supported by this strategy"
            )
        if app_state == "clear_data" and target.platform == "android":
            _clear_android_app_data(target, test_logger)
        test_logger.info(
            "creating Appium session platform=%s udid=%s", target.platform, target.udid
        )
        with step("创建 Appium session", platform=target.platform):
            if app_state == "reinstall":
                with step("卸载并重新安装应用", app_id=target.app_id, policy=app_state):
                    session = create_driver(
                        target, reinstall=True, capabilities=session_capabilities
                    )
            else:
                session = create_driver(target, capabilities=session_capabilities)
        request.node._observed_driver = session
        try:
            session.preserved_overlays = frozenset(
                name
                for marker in request.node.iter_markers("preserve_overlays")
                for name in marker.args
            )
            observe_commands(session, request.node._observation)
            request.node._observation.emit("app.build", **application_metadata(target))
            if app_state == "clear_data" and target.platform == "ios":
                session.execute_script("mobile: clearApp", {"bundleId": target.app_id})
                if session_capabilities.get("appium:autoLaunch", True):
                    session.activate_app(target.app_id)
                test_logger.info("cleared iOS simulator app data for %s", target.app_id)
            _apply_permission_policy(request, target, session, test_logger)
            yield session
        finally:
            # A later fixture finalizer can fail after this session is closed.
            # Preserve an explicitly timestamped pre-close view, not a claim
            # that it represents the state after that later failure.
            try:
                capture_failure(
                    session,
                    artifacts_dir / "before-session-close",
                    target,
                    system_logs=False,
                )
            except Exception as error:
                request.node._observation.emit("evidence.failed", error=str(error))
            try:
                with step("关闭 Appium session"):
                    session.quit()
            finally:
                request.node._session_closed = True
                test_logger.info("Appium session closed")


def _clear_android_app_data(target, logger):
    installed = _run_adb(target, ["shell", "pm", "path", target.app_id])
    if "package:" not in installed.stdout:
        logger.info(
            "app %s is not installed on %s; fresh install already provides clean data",
            target.app_id,
            target.name,
        )
        return
    result = _run_adb(target, ["shell", "pm", "clear", target.app_id])
    if "Success" not in result.stdout:
        raise pytest.UsageError(
            f"Android did not clear app data on {target.name}: {result.stdout.strip()} {result.stderr.strip()}"
        )
    logger.info("cleared Android app data for %s", target.app_id)


def _run_adb(target, args):
    command = ["adb", "-s", target.udid, *args]
    try:
        result = subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise pytest.UsageError(
            f"Android command failed on {target.name}: {error}"
        ) from error
    return result


def _apply_permission_policy(request, target, session, logger):
    marker = request.node.get_closest_marker("permission_state")
    if marker is None:
        return
    policy = marker.args[0] if marker.args else "preserve"
    services = marker.args[1:]
    if policy == "preserve":
        return
    if policy == "grant":
        if target.platform == "android" and target.auto_grant_permissions:
            return
        if target.platform == "ios" and target.is_simulator and target.ios_permissions:
            return
        raise pytest.UsageError(
            "permission_state('grant') must be configured through device capabilities: Android auto_grant_permissions or iOS simulator ios_permissions"
        )
    if policy != "reset":
        raise pytest.UsageError(f"Unsupported permission_state policy: {policy}")
    if not services:
        raise pytest.UsageError(
            "permission_state('reset', ...) requires one or more permission service names"
        )
    if target.platform == "ios":
        for service in services:
            session.execute_script(
                "mobile: resetPermission",
                {"service": service, "bundleId": target.app_id},
            )
    else:
        for permission in services:
            if "." not in permission:
                raise pytest.UsageError(
                    "Android permission reset requires full permission names, e.g. "
                    "android.permission.CAMERA"
                )
            _run_adb(target, ["shell", "pm", "revoke", target.app_id, permission])
            _run_adb(
                target,
                [
                    "shell",
                    "pm",
                    "clear-permission-flags",
                    target.app_id,
                    permission,
                    "user-set",
                    "user-fixed",
                ],
            )
    logger.info("reset permission state: %s", ", ".join(services))


@pytest.fixture
def auth_state_provider():
    """Override in project conftest.py to inject an app-specific test account provider."""
    return


@pytest.fixture
def app_state_provider():
    """Override with prepare/verify methods; register cleanup during prepare."""
    return None


@pytest.fixture
def prepared_app(driver, target, request, app_state_provider, app_launcher):
    from appium_testkit.lifecycle import prepared_state

    marker = request.node.get_closest_marker("app_launch")
    launch = marker.args[0] if marker and marker.args else "restart"
    marker = request.node.get_closest_marker("auth_state")
    state = marker.args[0] if marker and marker.args else "preserve"
    if state not in {"preserve", "anonymous", "authenticated"}:
        raise pytest.UsageError(f"Unsupported auth_state: {state}")
    auth = None
    if state != "preserve":
        provider = request.getfixturevalue("auth_state_provider")
        if provider is None:
            raise pytest.UsageError(
                f"auth_state({state!r}) requires an auth_state_provider fixture"
            )

        def auth():
            provider.ensure_state(state=state, driver=driver, target=target)

    with prepared_state(
        driver,
        target,
        launch=launch,
        provider=app_state_provider,
        auth=auth,
        launch_app=app_launcher,
    ) as session:
        yield session


@pytest.fixture
def relaunched_app(prepared_app):
    """Compatibility alias; prefer prepared_app and app_launch markers."""
    return prepared_app


@pytest.fixture(autouse=True)
def requested_auth_state(request):
    marker = request.node.get_closest_marker("auth_state")
    if marker and marker.args and marker.args[0] != "preserve":
        request.getfixturevalue("prepared_app")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)
    recorder = getattr(item, "_observation", None)
    if recorder is None:
        return
    recorder.emit("phase.completed", phase=report.when, outcome=report.outcome)
    capture_skip = report.skipped and item.get_closest_marker("update_notice_test")
    if not report.failed and not capture_skip:
        if report.when == "teardown":
            attach_evidence(recorder.path, "timeline-final")
        return
    session = getattr(item, "_observed_driver", None)
    if getattr(item, "_session_closed", False):
        session = None
    path = recorder.path / report.when
    path.mkdir(parents=True, exist_ok=True)
    error = call.excinfo.value if call.excinfo else None
    failure = {
        **recorder.context,
        "phase": report.when,
        "outcome": report.outcome,
        "error_type": type(error).__name__,
        "category": "precondition_unverified"
        if capture_skip
        else getattr(error, "state", "unclassified"),
        "message": str(error),
        "traceback": str(report.longrepr),
    }
    recorder.emit("test.skipped" if capture_skip else "test.failed", **failure)
    try:
        (path / "failure.json").write_text(
            json.dumps(redact(failure), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        capture_failure(
            session,
            path,
            item._observation_target,
            started=recorder.started,
            server_log=item._observation_server_log,
        )
        for collector in item.funcargs.get("diagnostic_collectors", []):
            try:
                diagnostics = collector(path)
                (path / f"{collector.__name__}.json").write_text(
                    json.dumps(redact(diagnostics), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception as error:
                recorder.emit(
                    "diagnostics.failed", collector=collector.__name__, error=str(error)
                )
        attach_evidence(path, report.when)
        attach_evidence(recorder.path, f"timeline-at-{report.when}-{report.outcome}")
        preclose = recorder.path / "before-session-close"
        if report.when == "teardown" and preclose.exists():
            attach_evidence(preclose, "before-session-close (earlier snapshot)")
    except Exception as error:
        recorder.emit("evidence.failed", error=str(error))
    report.sections.append(("Appium artifacts", str(path)))
