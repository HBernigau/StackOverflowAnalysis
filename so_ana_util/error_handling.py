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
from so_ana.infrastructure.error_handling import main

if __name__ == '__main__':
    # some demo code...

    main()