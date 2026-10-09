from types import SimpleNamespace

import pytest
from appium_testkit.alerts import accept_known_ios_alert
from selenium.common.exceptions import NoAlertPresentException


def session(text, buttons):
    calls = []
    state = {"text": text}

    class Alert:
        @property
        def text(self):
            if state["text"] is None:
                raise NoAlertPresentException()
            return state["text"]

    def execute(command, args):
        calls.append((command, args))
        if args["action"] == "getButtons":
            return buttons
        state["text"] = None

    return SimpleNamespace(
        capabilities={"platformName": "ios"},
        switch_to=SimpleNamespace(alert=Alert()),
        execute_script=execute,
    ), calls


@pytest.mark.parametrize(
    "text", [None, "允许其他应用使用无线数据？", "Kazumi 是否删除账号？"]
)
def test_absent_or_unknown_alert_is_not_accepted(text):
    driver, calls = session(text, ["仅限无线局域网"])
    assert not accept_known_ios_alert(
        driver, text_fragments=("Kazumi", "使用无线数据"), button="仅限无线局域网"
    )
    assert calls == []


def test_known_alert_selects_named_button():
    driver, calls = session("允许 Kazumi 使用无线数据？", ["不允许", "仅限无线局域网"])
    assert accept_known_ios_alert(
        driver, text_fragments=("Kazumi", "使用无线数据"), button="仅限无线局域网"
    )
    assert calls[-1][1] == {"action": "accept", "buttonLabel": "仅限无线局域网"}


def test_missing_button_fails_without_clicking_other_action():
    driver, calls = session("允许 Kazumi 使用无线数据？", ["不允许"])
    with pytest.raises(AssertionError, match="configured button"):
        accept_known_ios_alert(
            driver, text_fragments=("Kazumi", "使用无线数据"), button="仅限无线局域网"
        )
    assert len(calls) == 1


def test_permission_case_can_preserve_wireless_alert(monkeypatch):
    from appium_testkit import alerts
    from apps.kazumi.components.update_notice_dialog import UpdateNoticeDialog
    from apps.kazumi.pages.kazumi_page import KazumiPage

    def forbidden(*args, **kwargs):
        raise AssertionError("preserved system alert must not be handled")

    monkeypatch.setattr(alerts, "accept_known_ios_alert", forbidden)
    monkeypatch.setattr(UpdateNoticeDialog, "dismiss_if_present", lambda self: False)
    driver = SimpleNamespace(preserved_overlays=("wireless_data",))
    assert not KazumiPage(driver).dismiss_transient_overlays()
