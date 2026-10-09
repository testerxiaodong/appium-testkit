"""Package selection and pre-session rejection without real devices."""

import plistlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
import yaml
from appium_testkit.config import load_devices, load_targets
from appium_testkit.preflight import supports, validate_package, validate_profile

pytest_plugins = ["pytester"]


def target(path, simulator=True):
    return SimpleNamespace(
        name="ios-test",
        platform="ios",
        app_path=path,
        app_id="app.test",
        is_simulator=simulator,
        udid="phone",
    )


def bundle(tmp_path, platform="iPhoneSimulator", app_id="app.test"):
    path = tmp_path / "Test.app"
    path.mkdir()
    (path / "Info.plist").write_bytes(
        plistlib.dumps(
            {"CFBundleIdentifier": app_id, "CFBundleSupportedPlatforms": [platform]}
        )
    )
    return path


def test_simulator_package_passes_without_signing_tools(tmp_path):
    validate_package(target(bundle(tmp_path)))


@pytest.mark.parametrize(
    "simulator,platform", [(False, "iPhoneSimulator"), (True, "iPhoneOS")]
)
def test_wrong_platform_is_rejected_before_signing(tmp_path, simulator, platform):
    with pytest.raises(ValueError, match="device requires"):
        validate_package(target(bundle(tmp_path, platform), simulator))


def test_bundle_identifier_mismatch(tmp_path):
    with pytest.raises(ValueError, match="bundle ID mismatch"):
        validate_package(target(bundle(tmp_path, app_id="wrong")))


def test_real_package_requires_profile(tmp_path):
    with pytest.raises(ValueError, match="missing embedded"):
        validate_package(target(bundle(tmp_path, "iPhoneOS"), False))


def test_ipa_metadata_is_read_without_extracting(tmp_path):
    path = tmp_path / "Test.ipa"
    with ZipFile(path, "w") as z:
        z.writestr(
            "Payload/Test.app/Info.plist",
            plistlib.dumps(
                {
                    "CFBundleIdentifier": "app.test",
                    "CFBundleSupportedPlatforms": ["iPhoneOS"],
                }
            ),
        )
    with pytest.raises(ValueError, match="device requires"):
        validate_package(target(path))


@pytest.mark.parametrize(
    "change,message",
    [
        ({"ExpirationDate": datetime(2000, 1, 1)}, "expired"),
        ({"ProvisionedDevices": ["other"]}, "does not allow"),
        ({"Entitlements": {"application-identifier": "TEAM.other"}}, "does not match"),
    ],
)
def test_bad_profiles(change, message):
    profile = {
        "ExpirationDate": datetime.now(UTC) + timedelta(days=1),
        "ProvisionedDevices": ["phone"],
        "Entitlements": {"application-identifier": "TEAM.app.*"},
    }
    validate_profile(profile, target(Path("Test.app"), False))
    with pytest.raises(ValueError, match=message):
        validate_profile(profile | change, target(Path("Test.app"), False))


@pytest.mark.parametrize(
    "platform,simulator,expected",
    [
        ("ios", False, False),
        ("ios", True, True),
        ("android", False, True),
        ("android", True, True),
    ],
)
def test_clear_data_capability(platform, simulator, expected):
    assert (
        supports(
            SimpleNamespace(platform=platform, is_simulator=simulator), "clear_app_data"
        )
        is expected
    )


def matrices(tmp_path):
    devices = tmp_path / "devices.yaml"
    apps = tmp_path / "apps.yaml"
    devices.write_text(
        yaml.safe_dump(
            {
                "devices": [
                    {
                        "name": "sim",
                        "platform": "ios",
                        "udid": "sim",
                        "is_simulator": True,
                    },
                    {
                        "name": "phone",
                        "platform": "ios",
                        "udid": "phone",
                        "is_simulator": False,
                    },
                ]
            }
        )
    )
    apps.write_text(
        yaml.safe_dump(
            {
                "apps": [
                    {
                        "name": "test",
                        "ios": {
                            "app_id": "app.test",
                            "simulator_app": "sim.app",
                            "device_app": "phone.app",
                        },
                    }
                ]
            }
        )
    )
    return devices, apps


def test_variants_and_explicit_override(tmp_path):
    devices, apps = matrices(tmp_path)
    assert [t.app_path.name for t in load_targets(devices, apps)] == [
        "sim.app",
        "phone.app",
    ]
    assert [
        t.app_path.name
        for t in load_targets(devices, apps, app_override="override.app")
    ] == ["override.app", "override.app"]


def test_missing_variant_names_device_and_field(tmp_path):
    devices, apps = matrices(tmp_path)
    data = yaml.safe_load(apps.read_text())
    del data["apps"][0]["ios"]["device_app"]
    apps.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="device_app"):
        load_targets(devices, apps)


def test_boolean_string_cannot_silently_select_wrong_package(tmp_path):
    devices, _ = matrices(tmp_path)
    data = yaml.safe_load(devices.read_text())
    data["devices"][0]["is_simulator"] = "false"
    devices.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="YAML boolean"):
        load_devices(devices)


def test_bad_package_aborts_once_without_creating_driver(pytester, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[2]))
    path = bundle(pytester.path)
    pytester.makeconftest(f"""
from pathlib import Path
import appium_testkit.pytest_plugin as plugin
from appium_testkit.config import DeviceSpec, TestTarget
pytest_plugins=['appium_testkit.pytest_plugin']
plugin.load_targets=lambda *a,**kw:[TestTarget('test',Path({str(path)!r}),'app.test',DeviceSpec('phone','ios','phone','http://localhost:4723'))]
def forbidden(*a): raise AssertionError('DRIVER MUST NOT START')
plugin.create_driver=forbidden
""")
    pytester.makepyfile("""
def test_one(driver): pass
def test_two(driver): pass
""")
    result = pytester.runpytest_subprocess("-q")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    assert "Preflight failed" in result.stderr.str()
    assert result.stderr.str().count("device requires") == 1
    assert "DRIVER MUST NOT START" not in result.stdout.str()


def test_unsupported_case_skipped_before_fixtures(pytester, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[2]))
    pytester.makeconftest("""
from pathlib import Path
import appium_testkit.pytest_plugin as plugin
from appium_testkit.config import DeviceSpec, TestTarget
pytest_plugins=['appium_testkit.pytest_plugin']
plugin.load_targets=lambda *a,**kw:[TestTarget('test',Path('missing.app'),'app.test',DeviceSpec('phone','ios','phone','http://localhost:4723'))]
""")
    pytester.makepyfile("""
import pytest
@pytest.mark.app_state('clear_data')
def test_fresh(driver): raise AssertionError('must not execute')
""")
    pytester.runpytest_subprocess("-q").assert_outcomes(skipped=1)
    strict = pytester.runpytest_subprocess("-q", "--strict-capabilities")
    assert strict.ret == pytest.ExitCode.USAGE_ERROR
    assert "unsupported capability" in strict.stderr.str()


def test_real_app_checks_signature_after_valid_profile(tmp_path, monkeypatch):
    import appium_testkit.preflight as preflight

    path = bundle(tmp_path, "iPhoneOS")
    (path / "embedded.mobileprovision").write_bytes(b"profile")
    profile = {
        "ExpirationDate": datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1),
        "ProvisionedDevices": ["phone"],
        "Entitlements": {"application-identifier": "TEAM.app.test"},
    }
    calls = []

    def run(*args):
        calls.append(args[0])
        if args[0] == "security":
            return plistlib.dumps(profile)
        raise ValueError("unsigned executable")

    monkeypatch.setattr(preflight, "_run", run)
    with pytest.raises(ValueError, match="unsigned executable"):
        validate_package(target(path, False))
    assert calls == ["security", "codesign"]


def test_android_apk_validation(tmp_path):
    path = tmp_path / "test.apk"
    t = SimpleNamespace(name="android", platform="android", app_path=path)
    path.write_text("not an APK")
    with pytest.raises(ValueError, match="invalid APK"):
        validate_package(t)
    with ZipFile(path, "w") as z:
        z.writestr("AndroidManifest.xml", b"binary manifest")
    validate_package(t)


def test_real_device_signing_options(tmp_path):
    from appium_testkit.config import DeviceSpec, TestTarget
    from appium_testkit.driver_factory import build_driver_options

    path = bundle(tmp_path, "iPhoneOS")
    device = DeviceSpec(
        "phone",
        "ios",
        "phone",
        "http://localhost:4724",
        xcode_team_id="TESTTEAM",
        wda_bundle_id="app.test.wda",
        allow_provisioning_updates=True,
        ios_wait_for_idle_timeout=1.0,
        wda_local_port=8120,
    )
    caps = build_driver_options(
        TestTarget("test", path, "app.test", device)
    ).to_capabilities()
    assert caps["appium:xcodeOrgId"] == "TESTTEAM"
    assert caps["appium:updatedWDABundleId"] == "app.test.wda"
    assert caps["appium:allowProvisioningDeviceRegistration"] is True
    assert caps["appium:showXcodeLog"] is True
    assert caps["appium:wdaLocalPort"] == 8120
    assert caps["appium:waitForIdleTimeout"] == 1.0


def test_real_device_rejects_simulator_only_permissions(tmp_path):
    devices, _ = matrices(tmp_path)
    data = yaml.safe_load(devices.read_text())
    data["devices"][1]["ios_permissions"] = {"camera": "YES"}
    devices.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="ios_permissions requires an iOS simulator"):
        load_devices(devices)


def test_slow_successful_navigation_gets_separate_verification_budget(monkeypatch):
    import selenium.webdriver.support.wait as waits
    from apps.kazumi.pages.main_page import MainPage

    state = {"selected": False, "clicks": 0}

    class Element:
        def get_attribute(self, name):
            return "true" if state["selected"] else "false"

        def click(self):
            state["clicks"] += 1
            state["selected"] = True

    driver = SimpleNamespace(
        capabilities={"platformName": "ios"}, find_element=lambda *a: Element()
    )
    page = MainPage(driver)
    monkeypatch.setattr(page, "dismiss_transient_overlays", lambda: False)
    # Simulate a click acknowledgement taking 20 seconds without sleeping.
    monkeypatch.setattr(waits.time, "monotonic", lambda: 20 if state["selected"] else 0)
    assert page.select_tab("我的")
    assert state["clicks"] == 1


def test_slow_watchlist_click_is_not_repeated_or_timed_out(monkeypatch):
    import selenium.webdriver.support.wait as waits
    from apps.kazumi.pages.watchlist_page import WatchlistPage

    state = {"selected": False, "clicks": 0}

    class Element:
        def is_displayed(self):
            return True

        def get_attribute(self, name):
            return "true" if state["selected"] else "false"

        def click(self):
            state["clicks"] += 1
            state["selected"] = True

    element = Element()
    driver = SimpleNamespace(
        capabilities={"platformName": "ios"}, find_elements=lambda *a: [element]
    )
    page = WatchlistPage(driver)
    monkeypatch.setattr(page, "dismiss_transient_overlays", lambda: False)
    monkeypatch.setattr(waits.time, "monotonic", lambda: 20 if state["selected"] else 0)
    assert page.select_status("想看") is element
    assert state["clicks"] == 1


@pytest.mark.parametrize("value", [-1, True, "1", float("inf")])
def test_invalid_idle_timeout_rejected(tmp_path, value):
    devices, _ = matrices(tmp_path)
    data = yaml.safe_load(devices.read_text())
    data["devices"][0]["ios_wait_for_idle_timeout"] = value
    devices.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="ios_wait_for_idle_timeout"):
        load_devices(devices)


def test_settings_entry_waits_for_stable_position(monkeypatch):
    from apps.kazumi.pages.settings_page import SettingsPage

    positions = iter([{"x": 1}, {"x": 2}, {"x": 2}])
    clicked = []

    class Element:
        def is_displayed(self):
            return True

        def is_enabled(self):
            return True

        def get_attribute(self, name):
            return "true"

        @property
        def rect(self):
            return next(positions)

        def click(self):
            clicked.append(True)

    element = Element()
    driver = SimpleNamespace(
        capabilities={"platformName": "ios"}, find_element=lambda *a: element
    )
    page = SettingsPage(driver)

    def wait(condition, *a, **kw):
        assert not condition(driver)
        assert not condition(driver)
        return condition(driver)

    monkeypatch.setattr(page, "wait_for", wait)
    monkeypatch.setattr(page, "wait_visible", lambda *args: None)
    page.open_all_settings()
    assert clicked == [True]
