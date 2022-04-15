import os
import pathlib
import yaml
from typing import Any

#: Root path to the project
PROJ_ROOT_PATH = os.path.abspath(
                        pathlib.Path(__file__).parents[2]
                 )

#: Path to project data
PROJ_DATA_PATH = os.path.join(PROJ_ROOT_PATH, 'data')

#: Path to configuration
PROJ_CONFIG_PATH = os.path.join(PROJ_ROOT_PATH, r'data\config')

#: Path to output folder
PROJ_OUTP_PATH = os.path.join(PROJ_ROOT_PATH, r'data\output')


def get_main_config() -> Any:
    """
    Returns main configuration
    :return: main configuration as nested dictionary
    """
    with open(os.path.join(PROJ_CONFIG_PATH, 'so_ana_config.yaml'), 'r') as file:
        return yaml.safe_load(file)


