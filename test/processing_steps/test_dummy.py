import so_ana.dummy
import pytest
import allure
import os

@allure.issue('1', 'demo test')
@allure.feature('custom')
@allure.story('domain')
@pytest.mark.domain
@pytest.mark.infrastructure

def test_dummy_func():
    assert so_ana.dummy.dummy_func() == 42

def test_dummy2(tst_data_path):
    assert os.path.isfile(os.path.join(tst_data_path, 'dummy.txt'))

