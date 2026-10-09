"""On-demand backend fixture: independent instance and port per worker."""

from __future__ import annotations

from uuid import uuid4

import pytest

from appium_testkit.mocking.wiremock import WireMock


def pytest_addoption(parser):
    group = parser.getgroup("wiremock")
    group.addoption(
        "--run-integration",
        action="store_true",
        help="Include framework infrastructure integration tests",
    )
    group.addoption(
        "--wiremock-app-host",
        default=None,
        help="Device-reachable host; required for iOS real devices",
    )
    group.addoption("--wiremock-image", default="wiremock/wiremock:3.13.2")


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: framework infrastructure checks")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-integration"):
        return
    deselected = [item for item in items if item.get_closest_marker("integration")]
    items[:] = [item for item in items if not item.get_closest_marker("integration")]
    if deselected:
        config.hook.pytest_deselected(items=deselected)


@pytest.fixture(scope="session")
def wiremock_server(request):
    name = f"appium-testkit-wm-{uuid4().hex[:12]}"
    bind = "0.0.0.0" if request.config.getoption("--wiremock-app-host") else "127.0.0.1"

    # Import lazily: ordinary unit tests do not require a Docker connection.
    from testcontainers.core.container import DockerContainer

    container = DockerContainer(
        request.config.getoption("--wiremock-image"),
        name=name,
        extra_hosts={"host.docker.internal": "host-gateway"},
    )
    # Docker SDK supports (host IP, port); None requests an ephemeral port.
    container.ports["8080/tcp"] = (bind, None)
    try:
        container.start()
        port = int(container.get_exposed_port(8080))
        client = WireMock(f"http://{container.get_container_host_ip()}:{port}")
        client.wait_ready()
        yield client, port
    finally:
        container.stop()
