"""Small WireMock Admin API client; each worker owns an independent instance."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener


class WireMock:
    def __init__(self, admin_url: str):
        self.admin_url = admin_url.rstrip("/")
        self._http = build_opener(ProxyHandler({}))

    def api(self, method: str, path: str, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        req = Request(
            f"{self.admin_url}/__admin{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with self._http.open(req, timeout=10) as response:
            body = response.read()
        return json.loads(body) if body else None

    def wait_ready(self, timeout: float = 60):
        deadline = time.monotonic() + timeout
        while True:
            try:
                self.api("GET", "/mappings")
                return
            except (URLError, OSError):
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        f"WireMock not ready: {self.admin_url}"
                    ) from None
                time.sleep(0.25)

    def reset(self):
        """Only use on an exclusively leased instance, with the app stopped."""
        self.api("DELETE", "/mappings")
        self.api("POST", "/scenarios/reset")
        self.api("DELETE", "/requests")

    def add(self, mapping: dict) -> str:
        return self.api("POST", "/mappings", mapping)["id"]

    def remove(self, mapping_id: str):
        self.api("DELETE", f"/mappings/{mapping_id}")

    @contextmanager
    def override(self, mapping: dict):
        mapping_id = self.add(mapping)
        try:
            yield mapping_id
        finally:
            self.remove(mapping_id)

    def proxy(self, upstream: str) -> str:
        return self.add(
            {
                "priority": 100,
                "request": {"method": "ANY", "urlPattern": ".*"},
                "response": {"proxyBaseUrl": upstream},
            }
        )

    def events(self) -> list[dict]:
        return self.api("GET", "/requests")["requests"]

    def wait_for_mapping(self, mapping_id: str, timeout: float = 40) -> list[dict]:
        """Verify this exact rule was served, rather than only checking a URL."""
        deadline = time.monotonic() + timeout
        while True:
            matched = [
                e
                for e in self.events()
                if e.get("stubMapping", {}).get("id") == mapping_id
                and e.get("timing", {}).get("totalTime", -1) >= 0
            ]
            if matched:
                return matched
            if time.monotonic() >= deadline:
                raise AssertionError(f"App did not complete WireMock rule {mapping_id}")
            time.sleep(0.25)

    def evidence(self) -> dict:
        # Allowlist metadata: never export tokens, cookies or response bodies.
        return {
            "requests": [
                {
                    "method": e.get("request", {}).get("method"),
                    "path": e.get("request", {}).get("url", "").split("?")[0],
                    "matched": e.get("wasMatched"),
                    "mapping_id": e.get("stubMapping", {}).get("id"),
                    "status": e.get("responseDefinition", {}).get("status"),
                    "timing": e.get("timing"),
                }
                for e in self.events()
            ]
        }
