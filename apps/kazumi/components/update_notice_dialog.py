"""Kazumi's optional in-app version notice."""

from __future__ import annotations

from appium_testkit.pages.base_page import BasePage
from appium_testkit.telemetry import event
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.support.ui import WebDriverWait


class UpdateNoticeDialog(BasePage):
    TITLE = "发现新版本"
    DISMISS_ACTION = "稍后提醒"

    TITLE_ID = "kazumi.update.title"
    DISMISS_ID = "kazumi.update.later"

    @property
    def is_open(self) -> bool:
        return bool(self._visible_elements(self.DISMISS_ID)) or bool(
            self._visible_elements(self.TITLE_ID)
        )

    def _visible_elements(self, identifier: str):
        from appium_testkit.pages.locators import native_test_id

        try:
            elements = [
                e
                for e in self.driver.find_elements(
                    *native_test_id(self.platform, identifier)
                )
                if e.is_displayed()
            ]
        except StaleElementReferenceException:
            return []
        if len(elements) > 1:
            raise AssertionError(f"Duplicate visible semantic identifier: {identifier}")
        return elements

    def dismiss_if_present(self) -> bool:
        """Dismiss the reminder for this run without changing auto-update settings."""
        if not self.is_open:
            return False
        event("overlay.detected", title=self.TITLE, action=self.DISMISS_ACTION)
        actions = self._visible_elements(self.DISMISS_ID)
        if not actions:
            event(
                "overlay.failed", reason="dismiss_action_unavailable", title=self.TITLE
            )
            try:
                actions = WebDriverWait(
                    self.driver,
                    5,
                    ignored_exceptions=(StaleElementReferenceException,),
                ).until(lambda _driver: self._visible_elements(self.DISMISS_ID))
            except TimeoutException:
                actions = []
        if not actions:
            raise AssertionError(
                "Kazumi update notice is visible, but its '稍后提醒' action is not "
                "exposed in the accessibility tree."
            )
        try:
            actions[0].click()
        except StaleElementReferenceException:
            # A click can close the overlay while Appium is acknowledging it.
            # The wait below verifies that the dismiss action is gone.
            pass
        try:
            WebDriverWait(self.driver, 8).until(lambda _driver: not self.is_open)
        except TimeoutException as error:
            event(
                "overlay.failed", reason="still_visible_after_dismiss", title=self.TITLE
            )
            raise AssertionError(
                "Kazumi update notice remained open after '稍后提醒'"
            ) from error
        event("overlay.dismissed", title=self.TITLE, verified=True)
        return True
