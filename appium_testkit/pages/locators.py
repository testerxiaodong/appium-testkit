"""Native locator builders shared by application adapters."""

from appium.webdriver.common.appiumby import AppiumBy


def accessible_label(platform: str, label: str, *, button: bool = False):
    if platform == "android":
        import json

        selector = "new UiSelector()"
        if button:
            selector += '.className("android.widget.Button")'
        return (
            AppiumBy.ANDROID_UIAUTOMATOR,
            selector + f".descriptionContains({json.dumps(label, ensure_ascii=False)})",
        )
    if platform == "ios":
        escaped = label.replace("\\", "\\\\").replace("'", "\\'")
        predicate = f"label CONTAINS[c] '{escaped}'"
        if button:
            predicate = "type == 'XCUIElementTypeButton' AND " + predicate
        return AppiumBy.IOS_PREDICATE, predicate
    raise ValueError(f"Unsupported locator platform: {platform}")


def native_test_id(platform: str, identifier: str):
    """Resolve Flutter Semantics.identifier without Android ID auto-prefixing."""
    import json

    if not identifier:
        raise ValueError("Empty test identifier")
    if platform == "android":
        return (
            AppiumBy.ANDROID_UIAUTOMATOR,
            f"new UiSelector().resourceId({json.dumps(identifier)})",
        )
    if platform == "ios":
        return AppiumBy.ACCESSIBILITY_ID, identifier
    raise ValueError(f"Unsupported locator platform: {platform}")
