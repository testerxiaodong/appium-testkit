"""First-run controls addressed by stable semantics identifiers."""

from appium_testkit.pages.locators import native_test_id

from apps.kazumi.pages.kazumi_page import KazumiPage


class OnboardingPage(KazumiPage):
    PROGRESS = "kazumi.onboarding.progress"
    PRIMARY = "kazumi.onboarding.primary"
    SKIP_RULES = "kazumi.onboarding.skip_rules"

    def control_locator(self, identifier):
        return native_test_id(self.platform, identifier)

    @property
    def is_open(self) -> bool:
        return self.has_control(self.PROGRESS)

    def wait_until_open(self) -> None:
        self.wait_visible(
            self.control_locator(self.PROGRESS), "重装后应出现首次启动引导"
        )

    def has_control(self, identifier: str) -> bool:
        return any(
            e.is_displayed()
            for e in self.driver.find_elements(*self.control_locator(identifier))
        )

    def progress(self) -> str:
        element = self.wait_visible(self.control_locator(self.PROGRESS), "等待引导进度")
        # Progress is semantic state, not text used to locate the element.
        return str(
            element.get_attribute("value" if self.platform == "ios" else "content-desc")
        )

    def continue_setup(self) -> None:
        self.tap_locator(self.control_locator(self.PRIMARY), "继续首次启动引导")
