import pytest
import allure
import os
from typing import Any
import so_ana.infrastructure.config_access as config_access


@allure.title('test configuration pathes')
@allure.feature('application')
@allure.story('infrastructure')
@pytest.mark.application
@pytest.mark.infrastructure
@pytest.mark.parametrize('path_val', [config_access.PROJ_CONFIG_PATH,
                                      config_access.PROJ_DATA_PATH,
                                      config_access.PROJ_ROOT_PATH,
                                      config_access.PROJ_OUTP_PATH])
def test_is_valid_path(path_val: str):
    assert os.path.isdir(path_val)


@allure.step('Check key presence for key {0}')
def step_check_key_pres(key: str, res: Any):
    assert key in res.keys()


@allure.title('plausibility check for parameter file')
@allure.feature('application')
@allure.story('infrastructure')
@pytest.mark.application
@pytest.mark.infrastructure
def test_main_parameterfile_for_plausibility():
    res = config_access.get_main_config()
    for key in ('so_urls', 'dask_opts', 'db_opts'):
        step_check_key_pres(key, res)
