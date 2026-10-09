"""Reset policy and locator contracts without connected devices."""

import pytest
from appium_testkit.config import DeviceSpec
from appium_testkit.config import TestTarget as Target
from appium_testkit.driver_factory import build_driver_options
from appium_testkit.pages.locators import accessible_label, native_test_id
from apps.kazumi.pages.main_page import MainPage
from apps.kazumi.pages.settings_page import SettingsPage
from apps.kazumi.pages.watchlist_page import WatchlistPage


@pytest.mark.parametrize(
    "platform,simulator",
    [("ios", False), ("ios", True), ("android", False), ("android", True)],
)
def test_reinstall_overrides_no_reset_only_for_requested_case(
    tmp_path, platform, simulator
):
    package = tmp_path / "app"
    package.touch()
    target = Target(
        "sample",
        package,
        "com.example.app",
        DeviceSpec(
            "device",
            platform,
            "udid",
            "http://localhost:4723",
            no_reset=True,
            is_simulator=simulator,
        ),
    )
    caps = build_driver_options(target, reinstall=True).to_capabilities()
    assert caps["appium:fullReset"] is True
    assert caps["appium:noReset"] is False
    ordinary = build_driver_options(target).to_capabilities()
    assert ordinary["appium:noReset"] is True
    assert "appium:fullReset" not in ordinary
    assert target.no_reset is True


@pytest.mark.parametrize("platform", ["ios", "android"])
def test_named_dynamic_locators_match_shared_builder(platform):
    assert MainPage.tab_locator(platform, "我的") == native_test_id(
        platform, "kazumi.nav.my"
    )
    assert WatchlistPage.status_locator(platform, "想看") == native_test_id(
        platform, "kazumi.watchlist.filter.planToWatch"
    )
    assert SettingsPage.ready_locator(platform) == native_test_id(
        platform, "kazumi.settings.category.keyboard"
    )


def test_locator_escapes_labels_and_rejects_unknown_platform():
    assert "\\'" in accessible_label("ios", "a'b")[1]
    assert '\\"' in accessible_label("android", 'a"b')[1]
    with pytest.raises(ValueError, match="Unsupported"):
        accessible_label("unknown", "name")


@pytest.mark.parametrize("identifier", ["kazumi.nav.my", 'subject."quoted"'])
def test_native_identifier_is_exact_and_escaped(identifier):
    import json

    from appium.webdriver.common.appiumby import AppiumBy

    assert native_test_id("ios", identifier) == (AppiumBy.ACCESSIBILITY_ID, identifier)
    assert native_test_id("android", identifier) == (
        AppiumBy.ANDROID_UIAUTOMATOR,
        f"new UiSelector().resourceId({json.dumps(identifier)})",
    )


def test_native_identifier_rejects_empty_and_unknown_platform():
    with pytest.raises(ValueError, match="Empty"):
        native_test_id("ios", "")
    with pytest.raises(ValueError, match="Unsupported"):
        native_test_id("web", "id")


def test_subject_identifier_does_not_depend_on_xml_ancestor_visibility():
    from types import SimpleNamespace

    from apps.kazumi.pages.recommendations_page import RecommendationsPage

    element = SimpleNamespace(
        is_displayed=lambda: True, get_attribute=lambda name: "FX战士久留美"
    )
    driver = SimpleNamespace(
        capabilities={"platformName": "ios"}, find_elements=lambda *args: [element]
    )
    page = RecommendationsPage(driver)
    page.dismiss_transient_overlays = lambda: False
    assert page.wait_for_subject(622288, "FX战士久留美") == native_test_id(
        "ios", "kazumi.subject.622288"
    )
