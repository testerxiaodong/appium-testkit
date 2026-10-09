"""Kazumi backend baseline, shared by business and generic smoke tests."""

import json

import allure
import pytest

from apps.kazumi.mocking.update import UpdateMockSession


@pytest.fixture(scope="session")
def kazumi_installed_builds():
    return set()


@pytest.fixture
def kazumi_backend(target, request):
    if target.app_name != "kazumi":
        return None
    client, port = request.getfixturevalue("wiremock_server")
    host = request.config.getoption("--wiremock-app-host")
    if not host:
        if target.platform == "android" and target.is_simulator:
            host = "10.0.2.2"
        elif target.platform == "ios" and target.is_simulator:
            host = "127.0.0.1"
        else:
            raise pytest.UsageError(
                "Kazumi real-device tests require --wiremock-app-host <reachable host IP>"
            )
    return client, f"http://{host}:{port}"


@pytest.fixture
def session_capabilities(kazumi_backend):
    # No uncontrolled first request, including when noReset retains a running app.
    return {"appium:autoLaunch": False} if kazumi_backend else {}


@pytest.fixture
def kazumi_runtime(
    driver, target, kazumi_backend, kazumi_installed_builds, request, artifacts_dir
):
    if kazumi_backend is None:
        yield None
        return
    client, url = kazumi_backend
    session = UpdateMockSession(driver, target, client, url)
    previous = getattr(driver, "preserved_overlays", frozenset())
    try:
        driver.terminate_app(target.app_id)
        binary = (
            target.app_path / "Runner" if target.app_path.is_dir() else target.app_path
        )
        stat = binary.stat()
        key = (target.lock_key, str(target.app_path), stat.st_mtime_ns, stat.st_size)
        if key not in kazumi_installed_builds:
            driver.install_app(str(target.app_path))
            kazumi_installed_builds.add(key)
        # prepared_app performs the controlled launch itself. Direct driver users
        # (first-launch and smoke tests) need this launch before entering the test.
        if "prepared_app" not in request.fixturenames:
            session.launch(version="0.0.0")
        yield session
        # Do not treat a missing request as proof of 'no update'. A fresh smoke test
        # may stop at onboarding, before the app has scheduled its update check.
        from apps.kazumi.pages.onboarding_page import OnboardingPage

        completed = all(
            getattr(request.node, f"rep_{phase}", None) is not None
            and getattr(request.node, f"rep_{phase}").passed
            for phase in ("setup", "call")
        )
        if completed and session.mapping_id and not OnboardingPage(driver).is_open:
            session.assert_served()
    finally:
        try:
            driver.terminate_app(target.app_id)
        finally:
            driver.preserved_overlays = previous
            try:
                evidence = client.evidence()
                evidence["scenario"] = session.mapping
                text = json.dumps(evidence, ensure_ascii=False, indent=2)
                (artifacts_dir / "wiremock.json").write_text(text, encoding="utf-8")
                allure.attach(
                    text, "WireMock scenario and requests", allure.attachment_type.JSON
                )
            finally:
                client.reset()


@pytest.fixture(autouse=True)
def initialize_kazumi_runtime(request):
    # Avoid parametrizing or starting devices for unit/infrastructure tests.
    if "driver" in request.fixturenames:
        request.getfixturevalue("kazumi_runtime")


@pytest.fixture
def app_launcher(kazumi_runtime):
    if kazumi_runtime is None:
        return None
    return lambda: kazumi_runtime.launch(version="0.0.0")
