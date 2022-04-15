"""
contains types and exceptions related to downloads

Author: `HBernigau <https://github.com/HBernigau>`_
Date: 04.2022
"""

from dataclasses import dataclass
from typing import Any
import so_ana.infrastructure.error_handling as error_handling

# *********************************************
# dataclasses
# *********************************************


@dataclass
class RequResult:
    """
    Represents the result of a request
    """
    code: int
    content: str
    err_msg: str
    circuit_closed: bool = True


# *********************************************
# Exceptions
# *********************************************


class RobotsPolicyException(error_handling.SoAnaException):
    """Exception raised, if the HTTP request is not in line with robots.py specification of page"""
    pass


class HTTPError(error_handling.SoAnaException):
    """HTTP error"""

    def __init__(self, *args, full_response: Any):
        arg_lst = list(*args) + [full_response]
        super().__init__(arg_lst)
        self.full_response = full_response
