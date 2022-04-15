import so_ana.infrastructure.error_handling as error_handling
import pytest
import allure
from typing import Optional


class SomeHighLevelError(error_handling.SoAnaException):
    """Sample high-level error"""
    pass


def throw_error():
    """
    generate a sample error, handle and append to higher-level error
    :return:
    """
    try:
        return 1 / 0.0
    except Exception as exc:
        raise SomeHighLevelError('Custom exception caught',
                                 42,
                                 exc_details=exc).with_traceback(exc.__traceback__) from exc


@allure.title('check that sample error is raised')
@allure.feature('domain')
@allure.story('infrastructure')
@pytest.mark.domain
@pytest.mark.infrastructure
def test_error_is_raised():
    with pytest.raises(error_handling.SoAnaException):
        throw_error()


@allure.step('check if details are appended')
def step_det_app(exc_value: Optional[error_handling.SoAnaException]):
    assert hasattr(exc_value, 'exc_details')


@allure.step('check if trace is of expected type')
def step_trace_type(exc_value: Optional[error_handling.SoAnaException]):
    assert len(exc_value.exc_trace)>0
    for item in exc_value.exc_trace:
        assert isinstance(item, str)


@allure.step('extract exception info')
def exc_info_from_exception(exc_value: error_handling.SoAnaException) -> error_handling.ExceptionInfo:
    return exc_value.as_exc_info


@allure.step('check exception info attributes')
def step_exc_info_attr(exc_info: error_handling.ExceptionInfo):
    for man_attr in ['exc_type', 'exc_args', 'exc_details']:
        assert hasattr(exc_info, man_attr)


@allure.step('check exception info content')
def step_exc_info_cont(exc_info: error_handling.ExceptionInfo):
    assert exc_info.exc_type == 'SomeHighLevelError'
    assert len(exc_info.exc_args) == 2
    assert exc_info.exc_details.exc_type == 'ZeroDivisionError'


@allure.title('check content of exception info')
@allure.feature('domain')
@allure.story('infrastructure')
@pytest.mark.domain
@pytest.mark.infrastructure
def test_content_of_cust_error():
    try:
        throw_error()
        exc_value = None
    except error_handling.SoAnaException as exc:
        exc_value = exc

    step_det_app(exc_value)
    step_trace_type(exc_value)
    exc_info = exc_info_from_exception(exc_value)
    step_exc_info_attr(exc_info)
    step_exc_info_cont(exc_info)
