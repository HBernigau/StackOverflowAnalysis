import so_ana.infrastructure.domain
import pytest
import allure
import os

import so_ana.infrastructure.domain


@allure.issue('1', 'demo test')
@allure.feature('domain')
@allure.story('infrastructure')
@pytest.mark.domain
@pytest.mark.infrastructure
def test_dummy_func():
    assert so_ana.infrastructure.domain.dummy_func() == 42


@allure.feature('domain')
@allure.story('infrastructure')
@pytest.mark.domain
@pytest.mark.infrastructure
def test_dummy2(tst_data_path):
    assert os.path.isfile(os.path.join(tst_data_path, 'dummy.txt'))

