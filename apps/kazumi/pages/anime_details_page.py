"""A Kazumi anime detail page and its primary watch actions."""

from __future__ import annotations

import allure
from appium_testkit.pages.locators import native_test_id
from appium_testkit.telemetry import traced_step

from apps.kazumi.pages.kazumi_page import KazumiPage
from apps.kazumi.pages.recommendations_page import RecommendationsPage


class AnimeDetailsPage(KazumiPage):
    WATCH = "kazumi.details.watch"
    FOLLOW = "kazumi.details.follow"
    SAMPLE_SUBJECT_ID = 622288
    SAMPLE_TITLE = "FX战士久留美"

    @traced_step("从推荐进入番剧详情")
    @allure.step("打开番剧详情：{title}")
    def open_from_recommendations(
        self, title: str = SAMPLE_TITLE, subject_id: int = SAMPLE_SUBJECT_ID
    ) -> None:
        locator = RecommendationsPage(self.driver).wait_for_subject(subject_id, title)
        self.tap_locator(locator, "打开指定番剧")
        self.wait_visible(native_test_id(self.platform, self.WATCH), "等待详情观看入口")

    def watch_status_button(self):
        """Return the current follow status control (for example, 未追 or 想看)."""
        return self.wait_visible(
            native_test_id(self.platform, self.FOLLOW), "等待追番操作"
        )

    @allure.step("读取当前追番状态")
    def current_watch_status(self) -> str:
        button = self.watch_status_button()
        return str(
            button.get_attribute("label" if self.platform == "ios" else "content-desc")
        )
