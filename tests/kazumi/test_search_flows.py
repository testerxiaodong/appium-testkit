"""Search UI contracts: controlled keyword response, live ID lookup and details."""

import allure
import pytest
from apps.kazumi.pages.anime_details_page import AnimeDetailsPage
from apps.kazumi.pages.search_page import SearchPage

pytestmark = [pytest.mark.app("kazumi"), pytest.mark.mobile, pytest.mark.regression]
SUBJECT_ID = AnimeDetailsPage.SAMPLE_SUBJECT_ID
TITLE = AnimeDetailsPage.SAMPLE_TITLE


@pytest.fixture
def search_page(main_page, driver, kazumi_runtime):
    main_page.select_tab("推荐")
    mapping_id = kazumi_runtime.client.add(
        {
            "priority": 1,
            "request": {
                "method": "POST",
                "urlPath": "/v0/search/subjects",
                "bodyPatterns": [
                    {
                        "matchesJsonPath": {
                            "expression": "$.keyword",
                            "equalTo": TITLE,
                        }
                    }
                ],
            },
            "response": {
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "jsonBody": {
                    "total": 1,
                    "limit": 20,
                    "offset": 0,
                    "data": [
                        {
                            "id": SUBJECT_ID,
                            "type": 2,
                            "name": TITLE,
                            "name_cn": TITLE,
                            "date": "2026-01-01",
                            "summary": "Controlled search fixture",
                            "images": {
                                "large": "",
                                "common": "",
                                "medium": "",
                                "small": "",
                                "grid": "",
                            },
                            "rating": {
                                "rank": 100,
                                "score": 7.2,
                                "total": 10,
                                "count": [],
                            },
                            "tags": [],
                        }
                    ],
                },
            },
        }
    )
    page = SearchPage(driver, timeout=30).open()
    page.keyword_mapping_id = mapping_id
    page.mock_client = kazumi_runtime.client
    return page


@allure.feature("搜索")
def test_keyword_search_displays_matching_subject(search_page):
    search_page.search(TITLE)
    search_page.mock_client.wait_for_mapping(search_page.keyword_mapping_id)
    search_page.expect_result(SUBJECT_ID, TITLE)


@allure.feature("搜索")
def test_id_search_opens_details_and_returns_to_results(search_page):
    query = f"id:{SUBJECT_ID}"
    search_page.search(query)
    search_page.open_result(SUBJECT_ID, TITLE)
    search_page.return_from_details()
    search_page.expect_result(SUBJECT_ID, TITLE)
    assert search_page.input_value() == query


@allure.feature("搜索")
def test_clear_search_returns_to_discovery(search_page):
    search_page.search(f"id:{SUBJECT_ID}")
    search_page.expect_result(SUBJECT_ID, TITLE)
    search_page.clear()
    # iOS can expose the placeholder as the empty field's value.
    assert search_page.input_value() in ("", None, "搜索番剧名称")
    assert not any(
        e.is_displayed()
        for e in search_page.driver.find_elements(
            *search_page.result_locator(SUBJECT_ID)
        )
    )


@allure.feature("搜索")
def test_replacing_query_reloads_the_results(search_page):
    search_page.search(f"id:{SUBJECT_ID}")
    search_page.expect_result(SUBJECT_ID, TITLE)
    search_page.search(TITLE)
    search_page.mock_client.wait_for_mapping(search_page.keyword_mapping_id)
    assert search_page.input_value() == TITLE
    search_page.expect_result(SUBJECT_ID, TITLE)
