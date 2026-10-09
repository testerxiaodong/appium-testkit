"""Container ownership and cleanup without contacting Docker."""

from types import SimpleNamespace

import pytest
from appium_testkit.mocking import pytest_plugin as plugin


@pytest.mark.parametrize("fail_ready", [False, True])
def test_container_cleanup_and_loopback_binding(monkeypatch, fail_ready):
    from testcontainers.core import container as module

    events = []

    class Container:
        def __init__(self, image, **kwargs):
            self.ports = {}
            assert image == "wiremock/wiremock:3.13.2"

        def start(self):
            assert self.ports == {"8080/tcp": ("127.0.0.1", None)}
            events.append("start")

        def get_exposed_port(self, port):
            return "12345"

        def get_container_host_ip(self):
            return "127.0.0.1"

        def stop(self):
            events.append("stop")

    class Client:
        def __init__(self, url):
            assert url == "http://127.0.0.1:12345"

        def wait_ready(self):
            if fail_ready:
                raise RuntimeError("not ready")

    monkeypatch.setattr(module, "DockerContainer", Container)
    monkeypatch.setattr(plugin, "WireMock", Client)
    options = {
        "--wiremock-app-host": None,
        "--wiremock-image": "wiremock/wiremock:3.13.2",
    }
    request = SimpleNamespace(config=SimpleNamespace(getoption=options.get))
    fixture = plugin.wiremock_server.__wrapped__(request)
    if fail_ready:
        with pytest.raises(RuntimeError, match="not ready"):
            next(fixture)
    else:
        assert next(fixture)[1] == 12345
        with pytest.raises(StopIteration):
            next(fixture)
    assert events == ["start", "stop"]
