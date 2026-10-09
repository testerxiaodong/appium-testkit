"""Exercise the actual pinned image: override, forwarding and cleanup."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.request import ProxyHandler, build_opener

import pytest

pytestmark = pytest.mark.integration


def test_override_then_restore_forwarding(wiremock_server):
    class Upstream(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"real-upstream")

        def log_message(self, *args):
            pass

    upstream = ThreadingHTTPServer(("0.0.0.0", 0), Upstream)
    thread = Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    client, _ = wiremock_server
    http = build_opener(ProxyHandler({}))

    def get(path):
        with http.open(client.admin_url + path, timeout=10) as response:
            return response.read().decode()

    try:
        client.reset()
        client.proxy(f"http://host.docker.internal:{upstream.server_port}")
        assert get("/other") == "real-upstream"
        with client.override(
            {
                "priority": 1,
                "request": {"method": "GET", "urlPath": "/update"},
                "response": {"status": 200, "body": "mock-update"},
            }
        ) as mapping_id:
            assert get("/update") == "mock-update"
            assert get("/other") == "real-upstream"
            assert client.wait_for_mapping(mapping_id, timeout=3)
        assert get("/update") == "real-upstream"
        # The context also removes the exact rule on failed assertions.
        with pytest.raises(AssertionError, match="intentional"):
            with client.override(
                {
                    "priority": 1,
                    "request": {"method": "GET", "urlPath": "/update"},
                    "response": {"status": 200, "body": "temporary"},
                }
            ):
                raise AssertionError("intentional")
        assert get("/update") == "real-upstream"
    finally:
        client.reset()
        upstream.shutdown()
        upstream.server_close()
        thread.join(timeout=5)
