"""
a command line application for interacting with prefect and the data bases

Author: `HBernigau <https://github.com/HBernigau>`_
Date: 01.2022
"""

import logging
from datetime import timedelta, datetime
from sqlalchemy import delete
import os
import threading
import nltk

from dask.distributed import Client, LocalCluster
import prefect
from prefect import task, Flow, Parameter
from prefect import Client as PrefectClient
import prefect.engine.state as pref_state
from prefect.engine.executors import DaskExecutor
import click

import so_ana_management.management_deps as management_deps
import so_ana_management.flow as so_ana_flow
from sqlalchemy_models.db_deps import prod_db_deps_container


###################### Sample flow tasks and flow

@task
def provide_iterator(nr_mapped):
    return [i for i in range(nr_mapped)]

@task
def try_dummy2(i):
    print(f'I am starting [{i}].')
    res = i+2
    print(f'I am done with [{i}].')
    return res

@task
def dummy_sum(lst):
    return sum(lst)



def get_sample_flow():
    mng_prod_container = management_deps.get_prod_container()
    dask_scheduler_address = mng_prod_container.dask_scheduler_address()

    with Flow("sample_flow",
              executor=DaskExecutor(dask_scheduler_address)) as flow:
        nr_mapped=Parameter('nr_mapped')
        smpl_iterator = provide_iterator(nr_mapped)
        final_results = try_dummy2.map(smpl_iterator)
        dummy_sum(final_results)

    return flow

############ Dask-cluster helper functions ( to be started in separate cmd window)

def init_cluster():
    """Helper function to be called, when cluster is started"""
    so_ana_flow.init_logging()
    print(f'Worker initialized - pid={os.getpid()}, thread-id={threading.get_ident()}')

def tear_down_sessions():
    """Helper function to be called, when cluster is started"""
    so_ana_flow.tear_down()
    print(f'Session removed on worker - pid={os.getpid()}, thread-id={threading.get_ident()}')

def start_cluster(n_workers: int, scheduler_port: int):
    cluster = LocalCluster(n_workers=n_workers,
                           threads_per_worker=1,
                           scheduler_port=scheduler_port)
    client = Client(cluster)
    print('Dask started')
    print('************')
    print()
    client.run(init_cluster)
    return client

def print_connection_details(client):
    print('*************************************************************')
    print('Dask infos')
    print('*************************************************************')
    print(f'dask client: {client}')
    print(f'running scheduler on address: "{client.scheduler.address}"')
    print(f'dashboard-link: "{client.dashboard_link}"')
    print('*************************************************************')
    print()


############ Click-commands


@click.group()
def exc_comm():
    pass

@exc_comm.command()
@click.argument('n_workers', type=click.INT, default=4)
def start_dask_cluster(n_workers):
    """starts a local dask cluster with N_WORKER worker processes"""
    mng_prod_container = management_deps.get_prod_container()
    scheduler_port = mng_prod_container.config.dask_scheduler_port()
    client = start_cluster(n_workers=n_workers, scheduler_port=scheduler_port)
    while True:
        print_connection_details(client)
        new_val = input('Do you want to \n'
                        '  - exit -> Press "y" \n'
                        '  - restart client -> "r" \n'
                        '  - tear down session -> t\n\n'
                        ' -> ')
        if new_val.lower() == 'y':
            break
        elif new_val.lower() == 'r':
            client.restart()
        elif new_val.lower() == 't':
            client.run(tear_down_sessions)
        else:
            print(f'unhandled command: "{new_val}" -> try again.')

@exc_comm.command()
@click.argument('nr_mapped',
                type=click.INT,
                default=100)
def run_sample(nr_mapped):
    """runs a simple sample flow where NR_MAPPED dummy tasks are mapped over"""
    start_tmest=datetime.now()
    print(' -> Start', start_tmest)
    flow = get_sample_flow()
    status=flow.run(parameters=dict(nr_mapped=nr_mapped))
    end_tmest = datetime.now()
    print(' -> End:  ', end_tmest)
    print(' -> Duration: ', end_tmest-start_tmest)
    for key, value in status.result.items():
        print(f'status of "{key}" is "{value}" result is {value.result}')

@exc_comm.command()
def register_sample():
    """registers the sample flow on prefect server"""
    flow = get_sample_flow()
    flow.register(project_name='so_analysis')


@exc_comm.command()
def install_nltk_deps():
    """downlad required nltk data"""
    nltk.download('wordnet')


@exc_comm.command()
def visualize_sample():
    """visualizes the sample flow on prefect server"""
    flow = get_sample_flow()
    flow.visualize()


@exc_comm.command()
def register():
    """Registers the flow with prefect server"""
    flow = so_ana_flow.get_flow()
    client = PrefectClient()
    client.create_project('so_analysis', 'This project contains the relevant flows for stack overflow analysis.')
    flow.register(project_name='so_analysis')


@exc_comm.command()
def visualize():
    """visualizes the sample flow graph"""
    flow = so_ana_flow.get_flow()
    flow.visualize()


@exc_comm.command()
@click.argument('config_yaml')
@click.argument('user_agent')
@click.argument('from_email')
@click.option('--test/--prod', default=True, help='--test implies that the flow is executed in test modus / '
                                                  '--prod implies that it is executed in prod modus')

def run(config_yaml, user_agent, from_email, test):
    """
    excecutes the main flow in a dask cluster using the configuration config_yaml in configuration folder.
    """
    prefect.config.flows.checkpointing = True
    flow = so_ana_flow.get_flow()
    if test:
        modus = 'test'
    else:
        modus = 'prod'

    start_tmest = datetime.now()
    print(' -> Start', start_tmest)
    with prefect.context(modus = modus):
        status = flow.run(parameters=dict(config_yaml=config_yaml,
                                          user_agent=user_agent,
                                          from_email=from_email))
    end_tmest = datetime.now()

    res_dict = {'success': [], 'mapped_succ': [], 'other': []}

    for key, value in status.result.items():
        if type(value) is pref_state.Success:
            res_dict['success'].append((key, value))
        elif type(value) is pref_state.Mapped:
            for i, m_value in enumerate(value.map_states):
                if type(m_value) is pref_state.Success:
                    res_dict['mapped_succ'].append((key, i, m_value))
                else:
                    res_dict['other'].append((key, i, m_value))
        else:
            res_dict['other'].append((key, None, value))

    print('-----------------------------------')
    print('Successfull')
    print('-----------------------------------')
    for key, value in res_dict['success']:
        print(f'Overview: key="{key}", type="{type(key)}", value="{value}", type="{type(value)}"')
        print(f'Slug: {key.slug}')
        print(' -> result: ', value.result)
        print(' ---> location: ', value._result.location)
        print()

    print('-----------------------------------')
    print('Mapped and successfull')
    print('-----------------------------------')
    for key, idx, value in res_dict['mapped_succ']:
        print(f'Overview: key="{key}", type="{type(key)}", value="{value}", type="{type(value)}"')
        print(f'Slug: {key.slug}')
        print(f'idx: {idx}')
        print(' -> result: ', value.result)
        print(' ---> location: ', value._result.location)
        print()

    print('-----------------------------------')
    print('Others')
    print('-----------------------------------')
    for key, idx, value in res_dict['other']:
        print(f'Overview: key="{key}", type="{type(key)}", value="{value}", type="{type(value)}"')
        print(f'Slug: {key.slug}')
        print(f'idx: {idx}')
        print(f'State: {value}')
        print()
    print('-----------------------------------')
    print('Success of step 8')
    print('-----------------------------------')
    final_flow = flow.get_tasks(name='finish_flow_run')[0]
    value=status.result[final_flow]
    print(f'Final state: {value}')
    print('Results: ')
    if hasattr(value, 'message'):
        print(f'  -> message: {value.message}')
    if hasattr(value, '_result'):
        print()
        print(f'  -> location: {value._result.location}')
        print()
        print(' -> End:  ', end_tmest)
        print(' -> Duration: ', end_tmest - start_tmest)


@exc_comm.command()
@click.option('--test/--prod', default=True, help='--test implies that all test data is deleted from pg and es / '
                                                  '--prod implies that all prod data is deleted.')
def clear_db_data(test):
    """
    Clears data in all data base data
    """
    if test:
        modus_txt='test'
    else:
        modus_txt = 'prod'
    logging.basicConfig()
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    deps = prod_db_deps_container()

    # postgresql
    for schema, reg in deps.tbl_specs.items():
        for tbl_name, tbl in reg.build_tables.items():
            if 'modus' in [item.name for item in tbl.c]:
                stmt = delete(tbl).where(tbl.c.modus == modus_txt)
                deps.conn.execute(stmt)
    deps.conn.close()

    #elastic search
    res_2 = deps.d2es.delete_by_query(DC='_all', query_dict={'query': {'bool': {'filter': [{'term': {'modus': modus_txt}}]}}})
    print(f'delete_result es: "{res_2}"')

if __name__ == '__main__':
    #smpl_res = get_result()
    #smpl_res.write(int)
    exc_comm()