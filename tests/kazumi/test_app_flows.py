"""Cross-platform Kazumi user journeys backed by stable accessibility semantics."""

import allure
import pytest
from apps.kazumi.flows.onboarding_flow import OnboardingFlow
from apps.kazumi.pages.main_page import MainPage
from apps.kazumi.pages.onboarding_page import OnboardingPage
from selenium.webdriver.support.ui import WebDriverWait

pytestmark = pytest.mark.app("kazumi")


@allure.epic("Kazumi")
@allure.feature("首次启动")
@allure.story("使用默认配置完成初始化")
@pytest.mark.smoke
@pytest.mark.mobile
@pytest.mark.app_state("reinstall")
def test_first_launch_can_reach_home_with_default_setup(driver, target, test_logger):
    """Reinstall the app, verify onboarding, and complete first-run setup."""
    onboarding = OnboardingPage(driver, timeout=5)
    onboarding.wait_until_open()

    test_logger.info("Completing first-run setup on %s", target.name)
    assert "免责声明" in driver.page_source
    OnboardingFlow(driver).complete_with_defaults()
    MainPage(driver, timeout=30).wait_until_ready()
    assert MainPage(driver).wait_for_tab_selected("推荐")


@allure.epic("Kazumi")
@allure.feature("主导航")
@allure.title("主导航切换到 {tab}")
@pytest.mark.smoke
@pytest.mark.mobile
@pytest.mark.parametrize(
    "tab", MainPage.TABS, ids=("recommendations", "schedule", "watchlist", "my")
)
def test_primary_navigation_selects_requested_tab(driver, main_page, tab, test_logger):
    """Each primary destination is reachable and exposes its selected state."""
    main_page.wait_until_ready()
    test_logger.info("Opening Kazumi tab %s", tab)
    assert main_page.select_tab(tab)


@allure.epic("Kazumi")
@allure.feature("主导航")
@allure.story("重复选择当前标签")
@pytest.mark.mobile
@pytest.mark.parametrize(
    "tab", MainPage.TABS, ids=("recommendations", "schedule", "watchlist", "my")
)
def test_reselecting_current_tab_keeps_it_selected(main_page, tab):
    """Tapping a selected destination again should leave it as the active tab."""
    assert main_page.select_tab(tab)

    assert main_page.select_tab(tab)


@allure.epic("Kazumi")
@allure.feature("主导航")
@allure.story("从次级标签返回推荐")
@pytest.mark.mobile
@pytest.mark.parametrize("tab", MainPage.TABS[1:], ids=("schedule", "watchlist", "my"))
def test_secondary_tab_can_return_to_recommendations(main_page, tab, test_logger):
    """Every secondary destination can navigate back to the recommendations tab."""
    test_logger.info("Checking tab round trip: 推荐 -> %s -> 推荐", tab)
    main_page.select_tab(tab)
    assert main_page.select_tab("推荐")


@allure.epic("Kazumi")
@allure.feature("主导航")
@allure.story("标签之间连续切换")
@pytest.mark.mobile
def test_all_primary_tabs_remain_reachable_in_sequence(main_page):
    """A sequence of route changes must leave each requested tab selected."""
    for tab in MainPage.TABS:
        selected = main_page.select_tab(tab)
        assert selected, f"Expected {tab!r} to be selected after switching tabs"


@allure.epic("Kazumi")
@allure.feature("设置")
@allure.story("打开外观设置")
@pytest.mark.smoke
@pytest.mark.mobile
def test_my_page_opens_appearance_settings(
    driver, main_page, settings_page, test_logger
):
    """The settings route opens from My and exposes appearance controls."""
    main_page.wait_until_ready()
    main_page.select_tab("我的")
    test_logger.info("Opening appearance settings")
    settings_page.open_all_settings()
    settings_page.open_appearance_settings()
    assert "深色模式" in driver.page_source
    assert "配色方案" in driver.page_source


@allure.epic("Kazumi")
@allure.feature("设置")
@allure.story("外观设置选项可访问")
@allure.title("外观设置显示 {setting}")
@pytest.mark.mobile
@pytest.mark.parametrize(
    "setting", ("深色模式", "配色方案"), ids=("dark-mode", "color-scheme")
)
def test_appearance_settings_expose_expected_control(
    driver, main_page, settings_page, setting
):
    """The appearance screen exposes its documented controls to assistive tools."""
    main_page.select_tab("我的")
    settings_page.open_all_settings()
    settings_page.open_appearance_settings()

    assert setting in driver.page_source


@allure.epic("Kazumi")
@allure.feature("设置")
@allure.story("从外观设置返回主导航")
@pytest.mark.mobile
def test_nested_settings_routes_return_to_my_tab(
    driver, main_page, settings_page, test_logger
):
    """System back exits appearance and settings routes to the My tab."""
    main_page.select_tab("我的")
    settings_page.open_all_settings()
    settings_page.open_appearance_settings()
    test_logger.info("Returning from nested appearance settings")

    settings_page.go_back()
    WebDriverWait(driver, 10).until(
        lambda session: (
            "操作设置" in session.page_source and "深色模式" not in session.page_source
        )
    )
    settings_page.go_back()
    assert main_page.select_tab("我的")
