"""Check the native accessibility contract of the instrumented Kazumi build."""

import pytest
from apps.kazumi.pages.main_page import MainPage

pytestmark = [pytest.mark.app("kazumi"), pytest.mark.mobile]


def test_navigation_identifiers_are_unique_and_keep_labels(main_page, driver):
    for label, identifier in MainPage.TAB_IDS.items():

        def unique_visible(session, tab_label=label, test_id=identifier):
            elements = session.find_elements(
                *MainPage.tab_locator(main_page.platform, tab_label)
            )
            visible = [element for element in elements if element.is_displayed()]
            assert len(visible) <= 1, f"Duplicate visible node for {test_id}"
            return visible[0] if visible else False

        element = main_page.wait_for(unique_visible, f"等待唯一导航节点：{identifier}")
        native_id = element.get_attribute(
            "name" if main_page.platform == "ios" else "resource-id"
        )
        spoken_label = element.get_attribute(
            "label" if main_page.platform == "ios" else "content-desc"
        )
        assert native_id == identifier
        assert label in spoken_label, "Test identifiers must preserve spoken labels"
