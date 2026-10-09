"""Kazumi's categorized follow list (追番)."""

from __future__ import annotations

from typing import ClassVar

import allure
from appium_testkit.pages.locators import native_test_id
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait

from apps.kazumi.pages.kazumi_page import KazumiPage


class WatchlistPage(KazumiPage):
    @staticmethod
    def status_locator(platform: str, label: str):
        return native_test_id(
            platform, "kazumi.watchlist.filter." + WatchlistPage.STATUS_IDS[label]
        )

    STATUS_IDS: ClassVar[dict[str, str]] = {
        "全部": "all",
        "在看": "watching",
        "想看": "planToWatch",
        "看过": "watched",
        "搁置": "onHold",
        "抛弃": "abandoned",
    }
    STATUSES = ("全部", "在看", "想看", "看过", "搁置", "抛弃")

    @allure.step("筛选追番状态：{status}")
    def select_status(self, status: str):
        if status not in self.STATUSES:
            raise ValueError(f"Unknown Kazumi watchlist status: {status}")
        # Kazumi exposes these chips as accessible text/other elements rather
        # than native buttons on iOS, so use the shared cross-platform label.
        locator = self.status_locator(self.platform, status)

        def activate(driver):
            try:
                self.dismiss_transient_overlays()
                for element in driver.find_elements(*locator):
                    if element.is_displayed():
                        if element.get_attribute("selected") != "true":
                            self._click_with_overlay_guard(element, locator)
                        return True
            except StaleElementReferenceException:
                return False
            return False

        WebDriverWait(self.driver, 15).until(
            activate, message=f"无法点击追番筛选：{status}"
        )

        def selected(driver):
            try:
                self.dismiss_transient_overlays()
                for element in driver.find_elements(*locator):
                    if (
                        element.is_displayed()
                        and element.get_attribute("selected") == "true"
                    ):
                        return element
            except StaleElementReferenceException:
                return False
            return False

        return WebDriverWait(self.driver, 15).until(
            selected, message=f"点击后追番筛选未选中：{status}"
        )
