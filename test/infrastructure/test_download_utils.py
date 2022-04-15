import pytest
import allure
import so_ana.infrastructure.download_utils as download_utils
import so_ana.infrastructure.download_types as download_types
from datetime import datetime
import robots

@allure.title('test successful download of allowed Stack Overflow page')
@allure.feature('application')
@allure.story('infrastructure')
@pytest.mark.application
@pytest.mark.infrastructure
@pytest.mark.requires_internet
def test_download_of_allowed_page():
    result = download_utils.get_requ_data(page_url=r'https://stackoverflow.com/questions/51193522/ddd-vs-anemic-domain-model',
                                          params={},
                                          rp=robots.RobotFileParser(),
                                          base_url=r'https://stackoverflow.com',
                                          user_agent='TestAgent',
                                          from_email='TestAgent@somewhere.com')
    assert isinstance(result, str)
    assert result.startswith('<!DOCTYPE html>')


@allure.title('test invalid request throws error')
@allure.feature('application')
@allure.story('infrastructure')
@pytest.mark.application
@pytest.mark.infrastructure
@pytest.mark.requires_internet
def test_download_of_non_existing_page_fails():
    with pytest.raises(download_types.HTTPError) as exc:
        _ = download_utils.get_requ_data(
                    page_url=r'https://stackoverflow.com/questions/something_that_is_not_there',
                    params={},
                    rp=robots.RobotFileParser(),
                    base_url=r'https://stackoverflow.com',
                    user_agent='TestAgent',
                    from_email='TestAgent@somewhere.com'
            )
    caught_exc = exc.value
    assert caught_exc.full_response.status_code == 404


@allure.title('test disallowed page throws error')
@allure.feature('application')
@allure.story('infrastructure')
@pytest.mark.application
@pytest.mark.infrastructure
@pytest.mark.requires_internet
def test_download_of_disallowed_page_fails():
    with pytest.raises(download_types.RobotsPolicyException):
        _ = download_utils.get_requ_data(
                    page_url=r'https://stackoverflow.com/questions/tagged/anemic-domain-model+domain-driven-design',
                    params={},
                    rp=robots.RobotFileParser(),
                    base_url=r'https://stackoverflow.com',
                    user_agent='TestAgent',
                    from_email='TestAgent@somewhere.com'
            )


@pytest.fixture
def test_web_downloader():
    return download_utils.WebContentDownloader(stack_exchange_ws='stackoverflow',
                                               user_agent='TestAgent',
                                               from_email='TestAgent@somewhere.com',
                                               logger=None,
                                               requ_delay=0.0,
                                               recovery_timeout=400,
                                               config_data=None)


@pytest.fixture
def test_web_downloader_with_delay():
    return download_utils.WebContentDownloader(stack_exchange_ws='stackoverflow',
                                               user_agent='TestAgent',
                                               from_email='TestAgent@somewhere.com',
                                               logger=None,
                                               requ_delay=2.0,
                                               recovery_timeout=400,
                                               config_data=None)


@allure.step('Check if result successful')
def step_check_valid_content(result):
    assert result.code == 0
    assert result.content.startswith(r'<!DOCTYPE html>')
    assert result.err_msg == ''
    assert result.circuit_closed


@allure.step('Check if first and ssecond page different')
def compare_different_pages(res, res2):
    assert res.content != res2.content


@allure.title('test high level query for metadata by topic and page works')
@allure.feature('application')
@allure.story('infrastructure')
@pytest.mark.application
@pytest.mark.infrastructure
@pytest.mark.requires_internet
def test_web_downloader_metadata_by_topic_works(test_web_downloader):
    res = test_web_downloader.metadata_by_topic_and_page(topic='anemic-domain_model',
                                                         page_nr=1)
    res2 = test_web_downloader.metadata_by_topic_and_page(topic='anemic-domain_model',
                                                          page_nr=2)
    for result in (res, res2):
        step_check_valid_content(result)
    compare_different_pages(res, res2)


@allure.title('test high level query for metadata by topic and page works')
@allure.feature('application')
@allure.story('infrastructure')
@pytest.mark.application
@pytest.mark.infrastructure
@pytest.mark.requires_internet
def test_web_downloader_metadata_by_topic_works(test_web_downloader):
    res = test_web_downloader.metadata_by_topic_and_page(topic='anemic-domain_model',
                                                         page_nr=1)
    res2 = test_web_downloader.metadata_by_topic_and_page(topic='anemic-domain_model',
                                                          page_nr=2)
    for result in (res, res2):
        step_check_valid_content(result)
    compare_different_pages(res, res2)


@allure.title('test high level query post by id obeys delay')
@allure.feature('application')
@allure.story('infrastructure')
@pytest.mark.application
@pytest.mark.infrastructure
@pytest.mark.requires_internet
def test_web_downloader_with_delay_works(test_web_downloader_with_delay):
    st_time = datetime.now()
    _ = test_web_downloader_with_delay.post_by_id(64635462)
    _ = test_web_downloader_with_delay.post_by_id(51193522)
    end_time = datetime.now()

    assert (end_time-st_time).total_seconds() >= 2.0


@allure.title('test error for wrong stack exchange type')
@allure.feature('application')
@allure.story('infrastructure')
@pytest.mark.application
@pytest.mark.infrastructure
@pytest.mark.requires_internet
def test_web_downloader_wrong_stack_exchange_ws():
    with pytest.raises(NotImplementedError):
        _ = download_utils.WebContentDownloader(stack_exchange_ws='something_unknown',
                                                user_agent='TestAgent',
                                                from_email='TestAgent@somewhere.com',
                                                logger=None,
                                                requ_delay=0.0,
                                                recovery_timeout=400,
                                                config_data=None)
