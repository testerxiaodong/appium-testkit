"""Explicit iOS system-alert rules; never blanket-accept unknown alerts."""

from selenium.common.exceptions import NoAlertPresentException
from selenium.webdriver.support.ui import WebDriverWait

from appium_testkit.telemetry import event


def accept_known_ios_alert(
    driver, *, text_fragments: tuple[str, ...], button: str
) -> bool:
    if str(driver.capabilities.get("platformName", "")).lower() != "ios":
        return False
    if not text_fragments or any(not text for text in text_fragments):
        raise ValueError("Alert matching requires nonempty text fragments")
    try:
        text = driver.switch_to.alert.text
    except NoAlertPresentException:
        return False
    if not all(fragment in text for fragment in text_fragments):
        return False
    buttons = driver.execute_script("mobile: alert", {"action": "getButtons"})
    if button not in buttons:
        raise AssertionError(f"Known system alert has no configured button: {button}")
    event("system_alert.detected", button=button)
    driver.execute_script("mobile: alert", {"action": "accept", "buttonLabel": button})

    def closed(_driver):
        try:
            return _driver.switch_to.alert.text != text
        except NoAlertPresentException:
            return True

    WebDriverWait(driver, 5).until(closed, message="Known system alert remained open")
    event("system_alert.handled", button=button, verified=True)
    return True
