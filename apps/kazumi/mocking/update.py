"""Real release payload contract plus runtime update endpoint injection."""

from urllib.parse import urlparse

from appium_testkit.mocking.wiremock import WireMock

UPDATE_PATH = "/kazumi/v1/app/latest"
UPSTREAM = "https://api.kazumi.fyi"
MOCK_VERSION = "99.0.0"


def release_mapping(*, version=MOCK_VERSION, delay_ms=0, status=200):
    return {
        "name": "kazumi-update",
        "priority": 1,
        "request": {"method": "GET", "urlPath": UPDATE_PATH},
        "response": {
            "status": status,
            "fixedDelayMilliseconds": delay_ms,
            "headers": {"Content-Type": "application/json"},
            "jsonBody": {
                "tag_name": version,
                "body": "Appium WireMock controlled update",
                "html_url": "",
                "published_at": "2026-01-01T00:00:00Z",
                "assets": [],
            },
        },
    }


class UpdateMockSession:
    def __init__(self, driver, target, client: WireMock, app_url: str):
        self.driver, self.target, self.client = driver, target, client
        self.app_url = app_url
        self.mapping_id = None
        self.mapping = None

    def launch(self, *, version=MOCK_VERSION, delay_ms=0, status=200):
        # The app is stopped before rules change; no previous background requests.
        self.driver.terminate_app(self.target.app_id)
        self.client.reset()
        self.client.proxy(UPSTREAM)
        self.mapping = release_mapping(
            version=version, delay_ms=delay_ms, status=status
        )
        self.mapping_id = self.client.add(self.mapping)
        self.driver.preserved_overlays = frozenset(
            getattr(self.driver, "preserved_overlays", ())
        ) | {"update_notice"}
        uri = urlparse(self.app_url)
        if uri.scheme != "http" or not uri.hostname or uri.path or uri.query:
            raise ValueError("Expected an HTTP origin for the test update service")
        if self.target.platform == "android":
            # JSON array is passed directly to am; no shell interpolation.
            self.driver.execute_script(
                "mobile: startActivity",
                {
                    "component": f"{self.target.app_id}/com.example.kazumi.MainActivity",
                    "action": "android.intent.action.MAIN",
                    "categories": ["android.intent.category.LAUNCHER"],
                    "extras": [["s", "kazumiTestUpdateBaseUrl", self.app_url]],
                    "wait": True,
                },
            )
        else:
            self.driver.execute_script(
                "mobile: launchApp",
                {
                    "bundleId": self.target.app_id,
                    "arguments": ["--kazumi-test-update-base-url", self.app_url],
                },
            )

    def assert_served(self):
        assert self.mapping_id is not None, "Call launch() first"
        events = self.client.wait_for_mapping(self.mapping_id)
        assert all(e["request"]["url"].split("?")[0] == UPDATE_PATH for e in events)
        return events
