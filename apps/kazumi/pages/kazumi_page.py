"""Kazumi page base with app-specific transient overlay handling."""

from __future__ import annotations

from appium_testkit.overlays import OverlayHandlers
from appium_testkit.pages.base_page import BasePage
from appium_testkit.telemetry import event, step
from selenium.common.exceptions import ElementClickInterceptedException


class KazumiPage(BasePage):
    """Dismiss Kazumi's known optional update notice at action boundaries.

    This stays in the app adapter: the reusable Appium framework must not know
    about a particular app's dialogs. Unknown dialogs are deliberately surfaced.
    """

    def dismiss_transient_overlays(self) -> bool:
        from appium_testkit.alerts import accept_known_ios_alert

        from apps.kazumi.components.update_notice_dialog import UpdateNoticeDialog

        preserved = getattr(self.driver, "preserved_overlays", ())
        system_handled = False
        if "wireless_data" not in preserved:
            system_handled = accept_known_ios_alert(
                self.driver,
                text_fragments=("Kazumi", "使用无线数据"),
                button="仅限无线局域网",
            )
        app_handled = OverlayHandlers(
            {
                "update_notice": UpdateNoticeDialog(
                    self.driver, timeout=3
                ).dismiss_if_present
            },
            preserved=getattr(self.driver, "preserved_overlays", ()),
        ).handle()
        return system_handled or app_handled

    def wait_for(self, condition, description: str, **details):
        def guarded(driver):
            self.dismiss_transient_overlays()
            return condition(driver)

        return super().wait_for(guarded, description, **details)

    def _click_with_overlay_guard(self, element, locator):
        from selenium.webdriver.support import expected_conditions as conditions

        try:
            element.click()
        except ElementClickInterceptedException:
            # An intercepted click did not reach its target. Dismiss the known
            # notice, resolve a fresh node, and make one safe retry.
            if not self.dismiss_transient_overlays():
                raise
            event(
                "interaction.retry",
                reason="known_overlay_intercepted_click",
                attempt=2,
                locator=locator,
            )
            self.wait.until(conditions.element_to_be_clickable(locator)).click()

    def tap_locator(self, locator, description: str):
        from selenium.webdriver.support import expected_conditions as conditions

        with step(description, locator=locator):
            element = self.wait_for(
                conditions.element_to_be_clickable(locator),
                description,
                locator=locator,
            )
            self._click_with_overlay_guard(element, locator)
        return element

    def wait_visible(self, locator, description: str):
        from selenium.webdriver.support import expected_conditions as conditions

        return self.wait_for(
            conditions.visibility_of_element_located(locator),
            description,
            locator=locator,
        )

    def tap_accessibility_element(self, label: str) -> None:
        from appium.webdriver.common.appiumby import AppiumBy

        self.tap_locator((AppiumBy.ACCESSIBILITY_ID, label), f"点击元素：{label}")

    def tap_accessibility_element_containing(self, label: str, *, button: bool = False):
        return self.tap_locator(
            self.accessibility_contains_locator(label, button=button),
            f"点击元素：{label}",
        )
