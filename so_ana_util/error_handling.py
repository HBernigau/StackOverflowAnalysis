"""
contains several utilities for error handling

allows for storing "chained error information" without copying the entire
traceback object.

Note: module is currently not used / within a later refactoring the following error-Approach will be
implemented:

- bellow-flow level errors are never ignored / rather: throw "chained exceptions"
- within flow handlers: error handling takes place. The strategy is as follows:
  catch error / chain with "SOAnaFlowError" / log error / log trace / define default value

Author: `HBernigau <https://github.com/HBernigau>`_
Date: 01.2022
"""
import traceback
from dataclasses import dataclass
from typing import Union, List

@dataclass
class ExceptionInfo():
    """
    represents information about some exception

    :param exc_type: the exception type
    :param exc_args: arguments to the exception converted to string
    :param exc_details: List of root cause exception infos (mioght be empty)
    """
    exc_type: str
    exc_args: List[str]
    exc_details: Union[None, 'ExceptionInfo']

    @classmethod
    def from_exception(cls, exc: Exception):
        """
        constructs the exception info from some given exception

        :param exc: the exception
        :return: an instance of the current class
        """
        exc_details = getattr(exc, 'exc_details', None)
        exc_type = type(exc).__name__
        exc_args = [str(item) for item in getattr(exc, 'args', list())]
        return cls(exc_type, exc_args, exc_details)


def get_traceback(exc: Exception):
    return traceback.format_exception(value=exc, etype=type(exc), tb=exc.__traceback__)


class SoAnaException(Exception):
    """
    Base class for any user defined exception
    """

    def __init__(self, *args, exc_details=None, **kwargs):
        super().__init__(*args, **kwargs)
        if isinstance(exc_details, ExceptionInfo):
            self.exc_details = exc_details
        elif isinstance(exc_details, Exception):
            self.exc_details = ExceptionInfo.from_exception(exc_details)
        else:
            self.exc_details = None

    @property
    def exc_trace(self):
        return get_traceback(self)

    @property
    def as_exc_info(self):
        return ExceptionInfo.from_exception(self)

if __name__ == '__main__':
    # some demo code...

    class SomeHighLevelError(SoAnaException):
        pass


    def throw_error():
        """
        trow an error, append to high level error
        :return:
        """
        try:
            x = 1 / 0.0
        except Exception as exc:
            raise SomeHighLevelError('Custom exception caught', 42, exc_details=exc).with_traceback( exc.__traceback__) from exc


    def main():
        try:
            throw_error()
        except Exception as exc:
            exc_info = ExceptionInfo.from_exception(exc)
            print('All')
            print(exc_info)
            print()
            print('Details:')
            print(exc_info.exc_details)
            print()
            print('Traceback: ')
            print(''.join(get_traceback(exc)))

    main()