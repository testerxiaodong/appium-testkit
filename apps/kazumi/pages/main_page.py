"""Home shell and primary navigation for Kazumi."""

from __future__ import annotations

from typing import ClassVar

import allure
from appium_testkit.pages.locators import native_test_id
from appium_testkit.telemetry import traced_step
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait

from apps.kazumi.pages.kazumi_page import KazumiPage


class MainPage(KazumiPage):
    @staticmethod
    def tab_locator(platform: str, label: str):
        return native_test_id(platform, MainPage.TAB_IDS[label])

    TAB_IDS: ClassVar[dict[str, str]] = {
        "推荐": "kazumi.nav.recommendations",
        "时间表": "kazumi.nav.schedule",
        "追番": "kazumi.nav.watchlist",
        "我的": "kazumi.nav.my",
    }
    TABS = ("推荐", "时间表", "追番", "我的")

    @traced_step("等待 Kazumi 主导航就绪")
    def wait_until_ready(self) -> None:
        locator = self.tab_locator(self.platform, "推荐")

        # Kazumi can show the update notice after the home shell first renders.
        # Keep checking it while waiting for the navigation instead of waiting
        # on a button that is blocked by the late-arriving overlay.
        def home_is_ready(driver):
            # dismiss_if_present waits until the dialog has closed. Check the
            # navigation immediately afterward instead of forcing another
            # polling interval.
            self.dismiss_transient_overlays()
            return self._main_navigation_is_visible(driver, locator)

        WebDriverWait(self.driver, 30).until(
            home_is_ready,
            message="Kazumi main navigation did not become available",
        )

    @staticmethod
    def _main_navigation_is_visible(driver, locator) -> bool:
        try:
            return any(
                element.is_displayed() for element in driver.find_elements(*locator)
            )
        except StaleElementReferenceException:
            # Flutter may replace the accessibility node between lookup and
            # visibility check. The next wait poll obtains a fresh element.
            return False

    def wait_for_tab_selected(self, label: str) -> bool:
        locator = self.tab_locator(self.platform, label)
        return bool(
            self.wait_for(
                lambda driver: (
                    driver.find_element(*locator).get_attribute("selected") == "true"
                ),
                f"确认主导航选中：{label}",
                locator=locator,
            )
        )

    @traced_step("切换 Kazumi 主导航并确认选中状态")
    @allure.step("切换主导航：{label}")
    def select_tab(self, label: str) -> bool:
        if label not in self.TABS:
            raise ValueError(f"Unknown Kazumi main tab: {label}")
        locator = self.tab_locator(self.platform, label)

        def activate(driver):
            try:
                self.dismiss_transient_overlays()
                element = driver.find_element(*locator)
                if element.get_attribute("selected") != "true":
                    self._click_with_overlay_guard(element, locator)
                return True
            except StaleElementReferenceException:
                return False

        # WDA can acknowledge a successful click after the polling deadline.
        # Start result verification after the action returns; do not repeatedly
        # click from the result predicate or mistake a slow command for failure.
        WebDriverWait(self.driver, 15).until(
            activate, message=f"无法点击主导航：{label}"
        )

        def selected(driver):
            try:
                self.dismiss_transient_overlays()
                return driver.find_element(*locator).get_attribute("selected") == "true"
            except StaleElementReferenceException:
                return False

        return bool(
            WebDriverWait(self.driver, 15).until(
                selected, message=f"点击后主导航未选中：{label}"
            )
        )
