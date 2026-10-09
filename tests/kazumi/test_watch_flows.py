"""Business-facing Kazumi discovery and watchlist navigation scenarios."""

from __future__ import annotations

import allure
import pytest
from appium_testkit.pages.locators import native_test_id
from apps.kazumi.pages.anime_details_page import AnimeDetailsPage
from apps.kazumi.pages.watchlist_page import WatchlistPage

pytestmark = pytest.mark.app("kazumi")


@allure.epic("Kazumi")
@allure.feature("追番")
@allure.story("按追番状态筛选列表")
@allure.title("追番列表可选择 {status} 状态")
@pytest.mark.mobile
@pytest.mark.regression
@pytest.mark.parametrize("status", WatchlistPage.STATUSES)
def test_watchlist_can_select_each_status(main_page, driver, status):
    """A viewer can switch among all six tracking states in the follow list."""
    main_page.select_tab("追番")
    selected_status = WatchlistPage(driver).select_status(status)

    assert selected_status.get_attribute("selected") == "true"


@allure.epic("Kazumi")
@allure.feature("观看")
@allure.story("从推荐打开番剧详情")
@pytest.mark.mobile
@pytest.mark.regression
def test_recommended_anime_details_expose_watch_and_follow_actions(main_page, driver):
    """A recommended anime opens its details with watch and follow controls."""
    main_page.select_tab("推荐")
    details = AnimeDetailsPage(driver)
    details.open_from_recommendations()

    assert details.SAMPLE_TITLE in driver.page_source
    assert "开始观看" in driver.page_source
    assert details.current_watch_status() == "未追"

    # Kazumi exposes a visible playback action through accessibility semantics.
    details.wait_visible(
        native_test_id(details.platform, details.WATCH), "观看按钮可见"
    )
