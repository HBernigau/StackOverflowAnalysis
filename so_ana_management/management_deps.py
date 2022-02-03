"""
contains dependencies for management utils

Author: `HBernigau <https://github.com/HBernigau>`_
Date: 01.2022
"""

from dependency_injector import containers, providers
import ipaddress

import so_ana_util


def get_scheduler_address(ip_address, port):
    return r'tcp://' + f'{format(ip_address)}:{port}'


class Prod_container(containers.DeclarativeContainer):

    config = providers.Configuration()
    dask_scheduler_address = providers.Factory(get_scheduler_address,
                                               ip_address=config.dask_server_name,
                                               port=config.dask_scheduler_port)


def get_prod_container():
    dask_config = so_ana_util.get_main_config()['dask_opts']
    prod_container = Prod_container()
    prod_container.config.from_dict({'dask_scheduler_port': dask_config['dask_port'],
                                     'dask_server_name': ipaddress.ip_address(dask_config['dask_server'])})
    return prod_container

if __name__ == '__main__':
    prod_container = get_prod_container()
    address=prod_container.dask_scheduler_address()
    print(address)


