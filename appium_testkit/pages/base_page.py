"""Shared explicit-wait helpers; implicit waits remain disabled."""

from __future__ import annotations

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webelement import WebElement
from selenium.webdriver.support import expected_conditions as conditions
from selenium.webdriver.support.ui import WebDriverWait

from appium_testkit.telemetry import step


class BasePage:
    def __init__(self, driver, timeout: float = 15) -> None:
        from appium_testkit.pages.actions import MobileActions

        self.driver = driver
        self.actions = MobileActions(self)
        self.wait = WebDriverWait(driver, timeout)

    def wait_for(self, condition, description: str, **details):
        with step(description, page=type(self).__name__, **details):
            return self.wait.until(condition, message=description)

    @property
    def platform(self) -> str:
        return str(self.driver.capabilities.get("platformName", "")).lower()

    def find_accessibility_element(self, label: str) -> WebElement:
        return self.wait_for(
            conditions.visibility_of_element_located(
                (AppiumBy.ACCESSIBILITY_ID, label)
            ),
            f"等待可见元素：{label}",
        )

    def accessibility_contains_locator(self, label: str, *, button: bool = False):
        from appium_testkit.pages.locators import accessible_label

        return accessible_label(self.platform, label, button=button)

    def find_accessibility_element_containing(
        self, label: str, *, button: bool = False
    ) -> WebElement:
        locator = self.accessibility_contains_locator(label, button=button)
        return self.wait_for(
            conditions.visibility_of_element_located(locator),
            f"等待可见元素：{label}",
            locator=locator,
        )

    def tap_accessibility_element(self, label: str) -> None:
        self.wait.until(
            conditions.element_to_be_clickable((AppiumBy.ACCESSIBILITY_ID, label))
        ).click()

    def tap_accessibility_element_containing(
        self, label: str, *, button: bool = False
    ) -> WebElement:
        element = self.find_accessibility_element_containing(label, button=button)
        element.click()
        return element

    def wait_for_accessibility_text(self, text: str) -> WebElement:
        return self.find_accessibility_element_containing(text)

    def wait_for_accessibility_tree(self) -> str:
        def read_tree(driver):
            source = driver.page_source
            return source if source.strip() else False

        return self.wait.until(read_tree)
