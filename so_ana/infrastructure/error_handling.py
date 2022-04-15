import traceback
from dataclasses import dataclass, asdict
from typing import List, Optional, Union
import yaml


def get_traceback(exc: Exception) -> List[str]:
    """
    returns traceback from exception

    :param exc: some exception

    :return: list of lines of the traceback
    """
    return traceback.format_exception(value=exc, etype=type(exc), tb=exc.__traceback__)


@dataclass
class ExceptionInfo:
    """
    represents information about some exception

    :param exc_type: the exception type
    :param exc_args: arguments to the exception converted to string
    :param exc_details: List of root cause exception infos (mioght be empty)
    """
    exc_type: str
    exc_args: List[str]
    exc_details: Optional['ExceptionInfo']

    @classmethod
    def from_exception(cls, exc: Exception) -> 'ExceptionInfo':
        """
        constructs the exception info from some given exception

        :param exc: the exception
        :return: an instance of the current class
        """
        exc_details = getattr(exc, 'exc_details', None)
        exc_type = type(exc).__name__
        exc_args = [str(item) for item in getattr(exc, 'args', list())]
        return cls(exc_type, exc_args, exc_details)


@dataclass
class ErrorLogEntry:
    """
    Log entry for Errors

    :param error_info: Error information
    :trace_back: list of traceback entries
    """
    error_info: ExceptionInfo
    trace_back: List[str]


class SoAnaException(Exception):
    """
    Base class for any user defined exception
    """

    def __init__(self,
                 *args,
                 exc_details: Optional[Union[Exception, ExceptionInfo]] = None,
                 **kwargs):
        """
        :param args: args to be passed to Exception super class
        :param exc_details: details for the error (typically a lower level error)
        :param kwargs: kwargs to be passed to Exception super class
        """
        super().__init__(*args, **kwargs)

        if isinstance(exc_details, Exception):
            self.exc_details = ExceptionInfo.from_exception(exc_details)
        else:
            self.exc_details = exc_details

    @property
    def exc_trace(self):
        """
        :return: traceback as list of lines
        """
        return get_traceback(self)

    @property
    def as_exc_info(self):
        """
        :return: custom exception as user defined exception
        """
        return ExceptionInfo.from_exception(self)


def print_formated_error_info(exc: SoAnaException) -> None:
    """
    Prints SoAna Exception in pretty format

    :param exc: the exception to be printed
    """
    err_info = ExceptionInfo.from_exception(exc)
    trb = [item for item in get_traceback(exc)]
    res = asdict(ErrorLogEntry(err_info, trb))
    print(yaml.safe_dump(res))
