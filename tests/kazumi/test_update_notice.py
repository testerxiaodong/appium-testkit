"""Update notice behavior with controlled backend preconditions."""

import time

import allure
import pytest
from apps.kazumi.components.update_notice_dialog import UpdateNoticeDialog
from apps.kazumi.pages.main_page import MainPage
from selenium.webdriver.support.ui import WebDriverWait

pytestmark = [pytest.mark.app("kazumi"), pytest.mark.mobile]


@allure.feature("版本提示")
def test_delayed_update_keeps_current_tab_after_dismiss(update_scenario):
    update_scenario.launch(delay_ms=15000)
    page = MainPage(update_scenario.driver)
    page.wait_until_ready()
    assert page.select_tab("我的")
    notice = UpdateNoticeDialog(update_scenario.driver)
    WebDriverWait(update_scenario.driver, 35).until(lambda _: notice.is_open)
    update_scenario.assert_served()
    assert "99.0.0" in update_scenario.driver.page_source
    assert notice.dismiss_if_present()
    assert page.wait_for_tab_selected("我的")


@allure.feature("版本提示")
@pytest.mark.parametrize(
    "version,status",
    [("0.0.0", 200), ("99.0.0", 500)],
    ids=["no-new-release", "server-error"],
)
def test_no_update_dialog_for_non_actionable_response(update_scenario, version, status):
    update_scenario.launch(version=version, status=status)
    update_scenario.assert_served()
    page = MainPage(update_scenario.driver)
    page.wait_until_ready()
    notice = UpdateNoticeDialog(update_scenario.driver)
    # Bounded absence observation after a confirmed completed server response.
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        assert not notice.is_open
        time.sleep(0.2)
    assert page.select_tab("我的")


@allure.epic("Kazumi")
@allure.feature("版本提示")
@allure.story("稍后提醒关闭版本提示")
@pytest.mark.mobile
def test_update_notice_can_be_dismissed_and_reappear(update_scenario):
    """A controlled newer release produces a dismissible notice on every run."""
    update_scenario.launch()
    notice = UpdateNoticeDialog(update_scenario.driver, timeout=3)
    WebDriverWait(update_scenario.driver, 30).until(lambda _: notice.is_open)
    update_scenario.assert_served()
    assert "99.0.0" in update_scenario.driver.page_source
    assert notice.dismiss_if_present()
    assert not notice.is_open
    # Another controlled launch must show the notice again.
    # Reuse the launch adapter to restore exactly the same per-process config.
    update_scenario.launch()
    WebDriverWait(update_scenario.driver, 30).until(lambda _: notice.is_open)
    update_scenario.assert_served()
    assert notice.dismiss_if_present()
