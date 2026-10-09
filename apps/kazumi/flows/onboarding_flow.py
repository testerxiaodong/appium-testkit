"""Complete onboarding using stable controls and observable state changes."""

import allure
from selenium.webdriver.support.ui import WebDriverWait

from apps.kazumi.pages.main_page import MainPage
from apps.kazumi.pages.onboarding_page import OnboardingPage


class OnboardingFlow:
    def __init__(self, driver):
        self.driver = driver
        self.page = OnboardingPage(driver)

    @allure.step("使用默认选项完成首次启动设置")
    def complete_with_defaults(self) -> MainPage:
        home = MainPage(self.driver)
        locator = home.tab_locator(home.platform, "推荐")
        last_clicked = None

        def advance(driver):
            nonlocal last_clicked
            self.page.dismiss_transient_overlays()
            # A modal hides the progress node; its absence is not completion.
            if self.page.has_control(self.page.SKIP_RULES):
                self.page.tap_locator(
                    self.page.control_locator(self.page.SKIP_RULES),
                    "确认使用内置规则",
                )
                last_clicked = None
                return False
            if home._main_navigation_is_visible(driver, locator):
                return True
            if self.page.is_open:
                progress = self.page.progress()
                if progress != last_clicked:
                    self.page.continue_setup()
                    last_clicked = progress
            return False

        WebDriverWait(self.driver, 90).until(
            advance, message="首次启动引导未完成：未出现主导航"
        )
        return home
