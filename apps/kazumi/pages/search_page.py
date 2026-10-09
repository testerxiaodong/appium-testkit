"""Search UI: exact native controls and subject identifiers, no ranking assumptions."""

from appium.webdriver.common.appiumby import AppiumBy
from appium_testkit.pages.locators import native_test_id
from selenium.webdriver.support import expected_conditions as conditions

from apps.kazumi.pages.anime_details_page import AnimeDetailsPage
from apps.kazumi.pages.kazumi_page import KazumiPage


class SearchPage(KazumiPage):
    def input_locator(self):
        if self.platform == "android":
            return AppiumBy.CLASS_NAME, "android.widget.EditText"
        return AppiumBy.CLASS_NAME, "XCUIElementTypeTextField"

    def open(self):
        self.tap_accessibility_element("搜索")
        self.wait_visible((AppiumBy.ACCESSIBILITY_ID, "番剧搜索"), "等待搜索页")
        self.wait_visible(self.input_locator(), "等待搜索输入框")
        return self

    def search(self, query):
        self.actions.replace_text(self.input_locator(), query)
        # The accessible search button submits and unfocuses the field on both OSes.
        self.tap_accessibility_element("搜索")
        self.wait_visible((AppiumBy.ACCESSIBILITY_ID, "搜索结果"), "等待搜索结果区域")

    def result_locator(self, subject_id):
        if (
            not isinstance(subject_id, int)
            or isinstance(subject_id, bool)
            or subject_id <= 0
        ):
            raise ValueError("subject_id must be a positive integer")
        return native_test_id(self.platform, f"kazumi.search.result.{subject_id}")

    def expect_result(self, subject_id, title):
        locator = self.result_locator(subject_id)

        def result_ready(driver):
            for item in driver.find_elements(*locator):
                if item.is_displayed():
                    return item
            empty = driver.find_elements(AppiumBy.ACCESSIBILITY_ID, "没有找到番剧")
            if any(item.is_displayed() for item in empty):
                raise AssertionError(
                    f"搜索返回空列表，预期条目 {subject_id}；请检查接口响应和测试数据"
                )
            return False

        element = self.wait_for(result_ready, f"等待搜索条目 {subject_id}")
        # Verify actual card content, not the query still visible in the input.
        label = element.get_attribute(
            "label" if self.platform == "ios" else "content-desc"
        )
        if not label or title not in label:
            descendants = element.find_elements(
                *self.accessibility_contains_locator(title)
            )
            assert any(e.is_displayed() for e in descendants), (
                f"搜索条目 {subject_id} 未显示标题 {title!r}"
            )
        return element

    def open_result(self, subject_id, title):
        self.expect_result(subject_id, title)
        self.tap_locator(self.result_locator(subject_id), "打开搜索结果详情")
        details = AnimeDetailsPage(self.driver)
        details.wait_visible(native_test_id(self.platform, details.WATCH), "等待详情页")
        details.wait_for_accessibility_text(title)
        return details

    def return_from_details(self):
        self.tap_accessibility_element("返回番剧列表")
        self.wait_visible((AppiumBy.ACCESSIBILITY_ID, "搜索结果"), "返回搜索结果列表")

    def clear(self):
        locator = (AppiumBy.ACCESSIBILITY_ID, "清空搜索")
        previous_rect = None

        def settled(driver):
            nonlocal previous_rect
            element = driver.find_element(*locator)
            if not element.is_displayed() or not element.is_enabled():
                previous_rect = None
                return False
            if self.platform == "ios" and element.get_attribute("hittable") != "true":
                previous_rect = None
                return False
            rect = element.rect
            stable = rect == previous_rect
            previous_rect = rect
            return element if stable else False

        element = self.wait_for(settled, "等待搜索栏布局稳定且清空按钮可点击")
        self._click_with_overlay_guard(element, locator)
        self.wait_visible(
            self.accessibility_contains_locator("按条件查找"), "清空后返回搜索发现页"
        )
        self.wait_for(
            conditions.invisibility_of_element_located(
                (AppiumBy.ACCESSIBILITY_ID, "搜索结果")
            ),
            "清空后搜索结果区域消失",
        )

    def input_value(self):
        element = self.wait_visible(self.input_locator(), "读取搜索输入框")
        return (
            element.get_attribute("value") if self.platform == "ios" else element.text
        )
