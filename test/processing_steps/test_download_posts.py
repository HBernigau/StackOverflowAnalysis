import allure
import pytest

@allure.issue('2', 'quickfix page structure')
@allure.feature('domain')
@allure.story('step_download_posts')
@pytest.mark.domain
@pytest.mark.step_download_posts
def test_extract_meta():
    assert 1 == 1