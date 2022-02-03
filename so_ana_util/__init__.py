import os
import pathlib
import yaml

PROJ_ROOT_PATH = os.path.abspath(
                        pathlib.Path(__file__).parents[1]
                 )
PROJ_DATA_PATH = os.path.join(PROJ_ROOT_PATH, 'data')
PROJ_CONFIG_PATH = os.path.join(PROJ_ROOT_PATH, r'data\config')
PROJ_OUTP_PATH = os.path.join(PROJ_ROOT_PATH, r'data\output')

def get_main_config():
    with open(os.path.join(PROJ_CONFIG_PATH, 'so_ana_config.yaml'), 'r') as file:
        return yaml.safe_load(file)

