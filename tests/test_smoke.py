from xml.etree import ElementTree

import pytest
from appium_testkit.pages.base_page import BasePage


@pytest.mark.smoke
@pytest.mark.mobile
def test_app_starts_and_exposes_accessibility_tree(target, driver, test_logger):
    """Verify the configured app launches and exposes an accessibility hierarchy."""

    test_logger.info("Checking app launch on %s (%s)", target.name, target.platform)
    assert driver.session_id, "Appium did not create a driver session"
    window_size = driver.get_window_size()
    assert window_size["width"] > 0
    assert window_size["height"] > 0

    accessibility_tree = BasePage(driver).wait_for_accessibility_tree()
    root = ElementTree.fromstring(accessibility_tree)
    assert root.tag, "Appium returned an empty accessibility tree"
