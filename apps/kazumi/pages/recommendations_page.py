"""Recommendation data readiness is distinct from main-navigation readiness."""

from xml.etree import ElementTree

from appium_testkit.pages.locators import native_test_id
from appium_testkit.telemetry import PageStateError, event

from apps.kazumi.pages.kazumi_page import KazumiPage


def visible_labels(source):
    root = ElementTree.fromstring(source)
    labels = []

    def visit(node):
        attributes = node.attrib
        if (
            attributes.get("visible", attributes.get("displayed", "true")).lower()
            == "false"
        ):
            return
        labels.extend(
            attributes[k]
            for k in ("label", "text", "content-desc")
            if attributes.get(k)
        )
        for child in node:
            visit(child)

    visit(root)
    return labels


def recommendation_state(source, title):
    labels = visible_labels(source)
    for label in labels:
        if "暂时无法加载番剧" in label:
            return "data_load_failed", label
    if title in labels:
        return "content_ready", title
    # The UI does not expose enough information to distinguish empty data from
    # loading or a changed live ranking. Do not invent a successful/empty state.
    return "target_not_visible", f"等待推荐条目 {title!r}；尚未确认数据就绪"


class RecommendationsPage(KazumiPage):
    @staticmethod
    def subject_locator(platform: str, subject_id: int):
        if (
            isinstance(subject_id, bool)
            or not isinstance(subject_id, int)
            or subject_id <= 0
        ):
            raise ValueError("subject_id must be a positive integer")
        return native_test_id(platform, f"kazumi.subject.{subject_id}")

    def wait_for_subject(self, subject_id: int, expected_title: str):
        locator = self.subject_locator(self.platform, subject_id)

        def ready(driver):
            visible = [
                element
                for element in driver.find_elements(*locator)
                if element.is_displayed()
            ]
            if len(visible) > 1:
                raise AssertionError(
                    f"Duplicate visible subject identifier: {subject_id}"
                )
            if visible:
                return visible[0]
            state, detail = recommendation_state(driver.page_source, expected_title)
            if state == "data_load_failed":
                event("page.state", page="recommendations", state=state, detail=detail)
                raise PageStateError("recommendations", state, detail)
            return False

        element = self.wait_for(
            ready,
            f"等待推荐番剧 {subject_id} 可见；检查网络或榜单数据",
            locator=locator,
        )
        label = element.get_attribute(
            "label" if self.platform == "ios" else "content-desc"
        )
        assert expected_title in label, (
            f"番剧 {subject_id} 的标题与测试数据不一致：{label}"
        )
        return locator
