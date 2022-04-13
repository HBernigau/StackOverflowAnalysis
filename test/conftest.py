import pytest
import os

@pytest.fixture
def tst_data_path(request):
    base_path = os.path.join(request.config.rootpath, request.config.getini('testpaths')[0])
    return os.path.join(base_path, 'test_data')