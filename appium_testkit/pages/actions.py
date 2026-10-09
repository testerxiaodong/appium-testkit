"""Reusable touch operations; locators and business outcomes belong to pages."""

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput
from selenium.webdriver.support import expected_conditions as conditions
from selenium.webdriver.support.ui import WebDriverWait

from appium_testkit.telemetry import step


class MobileActions:
    def __init__(self, page):
        self.page = page
        self.driver = page.driver

    def replace_text(self, locator, value: str):
        # Do not put input values into step names or metadata.
        with step("替换输入框内容", locator=locator):
            element = self.page.wait_for(
                conditions.element_to_be_clickable(locator), "等待输入框可交互"
            )
            element.click()
            element.clear()
            element.send_keys(value)

    def hide_keyboard(self):
        with step("收起软键盘"):
            if self.driver.is_keyboard_shown():
                self.driver.hide_keyboard()
                self.page.wait_for(
                    lambda driver: not driver.is_keyboard_shown(), "等待键盘关闭"
                )

    def _touch(self):
        return ActionBuilder(self.driver, mouse=PointerInput("touch", "finger"))

    def press(self, locator, *, duration=0.8, count=1):
        """Long press by default; count=2 and duration=0.05 performs a double tap."""
        if duration <= 0 or count not in (1, 2):
            raise ValueError("duration must be positive; count must be 1 or 2")
        with step("触屏按压", locator=locator, duration=duration, count=count):
            element = self.page.wait_for(
                conditions.element_to_be_clickable(locator), "等待按压目标"
            )
            rect = element.rect
            actions = self._touch()
            pointer = actions.pointer_action
            pointer.move_to_location(
                int(rect["x"] + rect["width"] / 2),
                int(rect["y"] + rect["height"] / 2),
            )
            for index in range(count):
                if index:
                    pointer.pause(0.1)
                pointer.pointer_down()
                pointer.pause(duration)
                pointer.pointer_up()
            actions.perform()

    def long_press(self, locator, duration=0.8):
        self.press(locator, duration=duration)

    def double_tap(self, locator):
        self.press(locator, duration=0.05, count=2)

    def swipe(self, direction, *, container=None, duration_ms=450):
        """Direction describes finger movement; coordinates stay inside bounds."""
        points = {
            "up": (0.5, 0.8, 0.5, 0.2),
            "down": (0.5, 0.2, 0.5, 0.8),
            "left": (0.8, 0.5, 0.2, 0.5),
            "right": (0.2, 0.5, 0.8, 0.5),
        }
        if direction not in points or duration_ms <= 0:
            raise ValueError("Invalid swipe direction or duration")
        with step("滑动", direction=direction, container=container):
            if container is None:
                rect = self.driver.get_window_rect()
            else:
                rect = self.page.wait_for(
                    conditions.visibility_of_element_located(container),
                    "等待滑动区域",
                ).rect
            x1, y1, x2, y2 = points[direction]
            actions = self._touch()
            pointer = actions.pointer_action
            pointer.move_to_location(
                int(rect["x"] + rect["width"] * x1),
                int(rect["y"] + rect["height"] * y1),
            )
            pointer.pointer_down()
            pointer.pause(0.1)
            # W3C pointer move duration is milliseconds.
            actions.pointer_inputs[0].create_pointer_move(
                duration=duration_ms,
                x=int(rect["x"] + rect["width"] * x2),
                y=int(rect["y"] + rect["height"] * y2),
                origin="viewport",
            )
            pointer.pointer_up()
            actions.perform()

    def scroll_to(self, locator, *, direction="up", container=None, max_swipes=5):
        if max_swipes < 0:
            raise ValueError("max_swipes must not be negative")
        with step("滚动查找元素", locator=locator, max_swipes=max_swipes):
            for attempt in range(max_swipes + 1):
                try:
                    return WebDriverWait(self.driver, 1).until(
                        conditions.visibility_of_element_located(locator)
                    )
                except TimeoutException:
                    if attempt == max_swipes:
                        raise TimeoutException(
                            f"Element {locator!r} not visible after {max_swipes} swipes"
                        ) from None
                self.swipe(direction, container=container)

    def background_and_resume(self, app_id: str, *, seconds=2):
        if seconds <= 0:
            raise ValueError("seconds must be positive")
        with step("应用切后台并恢复", app_id=app_id, seconds=seconds):
            self.driver.background_app(seconds)
            self.page.wait_for(
                lambda driver: driver.query_app_state(app_id) == 4,
                "等待应用返回前台",
            )
