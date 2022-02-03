import os
import pathlib

PROJ_ROOT_PATH = os.path.abspath(
                        pathlib.Path(__file__).parents[1]
                 )
PROJ_DATA_PATH = os.path.join(PROJ_ROOT_PATH, 'data')
PROJ_CONFIG_PATH = os.path.join(PROJ_ROOT_PATH, r'data\config')
PROJ_OUTP_PATH = os.path.join(PROJ_ROOT_PATH, r'data\output')