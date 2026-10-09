"""Interruption scenarios: resuming must preserve the user's current route."""

import allure
import pytest
from appium_testkit.pages.locators import native_test_id
from apps.kazumi.pages.main_page import MainPage
from apps.kazumi.pages.watchlist_page import WatchlistPage

pytestmark = [pytest.mark.app("kazumi"), pytest.mark.mobile, pytest.mark.regression]


@allure.feature("前后台恢复")
@pytest.mark.parametrize("tab", MainPage.TABS)
def test_resume_preserves_current_tab(main_page, target, tab):
    main_page.select_tab(tab)
    main_page.actions.background_and_resume(target.app_id)
    # Observe selection without clicking again, which would mask a reset.
    assert main_page.wait_for_tab_selected(tab)


@allure.feature("追番")
@pytest.mark.parametrize("status", WatchlistPage.STATUSES)
def test_resume_preserves_watchlist_filter(main_page, driver, target, status):
    main_page.select_tab("追番")
    page = WatchlistPage(driver)
    page.select_status(status)
    page.actions.background_and_resume(target.app_id)
    assert main_page.wait_for_tab_selected("追番")
    locator = page.status_locator(page.platform, status)
    page.wait_for(
        lambda session: any(
            element.is_displayed() and element.get_attribute("selected") == "true"
            for element in session.find_elements(*locator)
        ),
        "恢复后保留追番筛选",
    )


@allure.feature("设置")
def test_resume_preserves_nested_settings(main_page, settings_page, target):
    main_page.select_tab("我的")
    settings_page.open_all_settings()
    settings_page.open_appearance_settings()
    settings_page.actions.background_and_resume(target.app_id)
    settings_page.wait_visible(
        settings_page.appearance_ready_locator(settings_page.platform),
        "恢复后仍在外观设置",
    )
    settings_page.go_back()
    settings_page.wait_visible(
        settings_page.ready_locator(settings_page.platform), "返回设置列表"
    )
    settings_page.go_back()
    assert main_page.wait_for_tab_selected("我的")


@allure.feature("设置")
def test_settings_category_can_be_found_after_swipe(main_page, settings_page):
    main_page.select_tab("我的")
    settings_page.open_all_settings()
    settings_page.actions.swipe("up")
    locator = settings_page.appearance_locator(settings_page.platform)
    settings_page.actions.scroll_to(locator, direction="down", max_swipes=4)
    settings_page.open_appearance_settings()
    settings_page.wait_visible(
        native_test_id(settings_page.platform, "kazumi.settings.color_scheme"),
        "滚动定位后能打开配色设置页面",
    )
