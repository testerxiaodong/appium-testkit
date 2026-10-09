"""Kazumi-only fixtures; the reusable Appium plugin stays app agnostic."""

import pytest


@pytest.fixture
def diagnostic_collectors():
    from apps.kazumi.diagnostics import collect_kazumi_network

    return [collect_kazumi_network]


@pytest.fixture
def settings_page(driver):
    from apps.kazumi.pages.settings_page import SettingsPage

    return SettingsPage(driver)


@pytest.fixture
def main_page(relaunched_app):
    from apps.kazumi.flows.onboarding_flow import OnboardingFlow
    from apps.kazumi.pages.main_page import MainPage
    from apps.kazumi.pages.onboarding_page import OnboardingPage
    from selenium.webdriver.support.ui import WebDriverWait

    page = MainPage(relaunched_app)
    onboarding = OnboardingPage(relaunched_app)
    locator = page.tab_locator(page.platform, "推荐")

    def ready(driver):
        page.dismiss_transient_overlays()
        return onboarding.is_open or page._main_navigation_is_visible(driver, locator)

    WebDriverWait(relaunched_app, 30).until(ready, message="启动后未出现引导或主导航")
    if onboarding.is_open:
        page = OnboardingFlow(relaunched_app).complete_with_defaults()
    page.wait_until_ready()
    return page


@pytest.fixture
def update_scenario(kazumi_runtime, main_page):
    """Business update tests override the default no-new-release baseline."""
    return kazumi_runtime
