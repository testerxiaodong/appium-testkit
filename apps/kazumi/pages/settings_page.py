"""Settings hub and appearance settings page."""

import allure
from appium_testkit.pages.locators import native_test_id
from selenium.common.exceptions import StaleElementReferenceException

from apps.kazumi.pages.kazumi_page import KazumiPage


class SettingsPage(KazumiPage):
    ENTRY = "kazumi.settings.entry"
    BACK = "kazumi.settings.back"

    @staticmethod
    def ready_locator(platform: str):
        return native_test_id(platform, "kazumi.settings.category.keyboard")

    @staticmethod
    def appearance_locator(platform: str):
        return native_test_id(platform, "kazumi.settings.category.theme")

    @staticmethod
    def appearance_ready_locator(platform: str):
        return native_test_id(platform, "kazumi.settings.dark_mode")

    @allure.step("返回上一级设置")
    def go_back(self) -> None:
        """Use Kazumi's accessible in-app back button on both platforms."""
        self.tap_locator(native_test_id(self.platform, self.BACK), "返回上一级设置")

    @allure.step("打开全部设置")
    def open_all_settings(self) -> None:
        locator = native_test_id(self.platform, self.ENTRY)
        previous_rect = None

        def entry_ready(driver):
            nonlocal previous_rect
            try:
                element = driver.find_element(*locator)
                if not element.is_displayed() or not element.is_enabled():
                    previous_rect = None
                    return False
                if (
                    self.platform == "ios"
                    and element.get_attribute("hittable") != "true"
                ):
                    previous_rect = None
                    return False
                rect = element.rect
                stable = rect == previous_rect
                previous_rect = rect
                return element if stable else False
            except StaleElementReferenceException:
                previous_rect = None
                return False

        element = self.wait_for(
            entry_ready, "等待设置入口可交互且位置稳定", locator=locator
        )
        self._click_with_overlay_guard(element, locator)
        # "外观设置" also exists on My: it cannot prove navigation completed.
        self.wait_visible(self.ready_locator(self.platform), "等待设置页就绪")

    @allure.step("进入外观设置")
    def open_appearance_settings(self) -> None:
        self.tap_locator(self.appearance_locator(self.platform), "打开外观设置")
        self.wait_visible(
            self.appearance_ready_locator(self.platform), "等待外观设置就绪"
        )
