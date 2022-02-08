"""
defines the prefect flow carrying out the stack-overflow analysis

Author: `HBernigau <https://github.com/HBernigau>`_
Date: 01.2022
"""

from datetime import timedelta, datetime
import uuid
import json
import yaml
from dataclasses import is_dataclass, asdict
from typing import Any, List, Dict, Union
import prefect
from prefect import task, Flow, Parameter, case, unmapped, apply_map
from prefect.engine.result.base import Result
from prefect.tasks.control_flow import merge
from prefect.executors import DaskExecutor
from prefect.triggers import always_run, all_successful
from prefect.utilities.logging import get_logger
import itertools
import os
import importlib
from collections import defaultdict
import traceback
import sys
import marshmallow_dataclass

import so_ana_management.management_utils as so_ana_mu
import so_ana_management.management_deps as management_deps
import so_ana_util
from so_ana_sqlalchemy_models.db_deps import prod_db_deps_container, dict_to_es_key
from so_ana_util.common_types import CustomLogHandler,fill_dc_from_obj
from so_ana_util.data_access import get_doc_iterator, IteratorFromGenerator
from so_ana_doc_worker import schemas as so_ana_worker_schemas
from so_ana_doc_worker import so_ana_process_posts, so_ana_reporting, extr_post_deps, extract_posts, LDA


serializer = so_ana_mu.get_proj_serializer()

def get_deps(**kwargs):
    return prod_db_deps_container(modus=getattr(prefect.context, 'modus', 'test'), **kwargs)


def init_logging():
    """
    Append own logging handler
    places to call:

    - in main script (works in local cmd shell, but not in pycharm and on server)
    - on each worker (works in Pycharm and in cmd shell but not on server)
    - in initial task (works everywhere but the first log entries are lost, starting flow, parameter tasks and start of
      task that appends handler)
    """
    root_logger = get_logger()
    deps = get_deps(script_logger_name='prefect')
    cust_handler = CustomLogHandler(deps.get_logging_session, modus=getattr(prefect.context, 'modus', 'test'))

    for hndl in root_logger.handlers:
        if type(hndl) is type(cust_handler):
            break
    else:
        root_logger.addHandler(cust_handler)
    #if sql alchemy logging shall be enabled
    #logging.basicConfig()
    #logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
    #logging.getLogger('sqlalchemy.pool').setLevel(logging.INFO)

def tear_down():
    deps = get_deps()
    deps.session.close()
    logging_session = deps.get_logging_session()
    logging_session.close()


class PGResult(Result):
    """
    Result that stores data in a postgresql data base
    compare: `Prefect documentation <https://docs.prefect.io/api/latest/engine/result.html#result>`_
    """

    def __init__(self, extended: bool=False, *args, **kwargs):
        self.extended = extended
        super().__init__(serializer=serializer, *args, **kwargs)

    def exists(self, location: str, **kwargs) -> bool:
        """
        checks if a given "location" exists in the data base

        :param location: the location string
        :param kwargs: additional key-value parameters for Prefect's result base class

        :return: boolean value indicating if the location exists
        """
        print(f'PGResult: calling exists with location="{location}"')
        return super().exists(location, **kwargs)

    def read(self, location: str):
        """
        read result from location
        :param location: location string

        :return: result
        """
        print(f'PGResult: calling read with location="{location}"')
        return super().read(location)

    def write(self, value_, **kwargs):
        """
        writing result to specified location

        :param value_: the value to be written
        :param kwargs: additional parameter to super class Result of prefect

        :return: result
        """

        db_res = fill_dc_from_obj(DC=so_ana_mu.FullResult,
                                  obj=prefect.context,
                                  add_dict={'result_as_json': json.loads(self.serializer.serialize(value_, as_bytes=False))},
                                  excl_lst = ['pid', 'thread', 'timestamp'],
                                  get_default = lambda x: -1 if x in ['map_index', 'task_loop_count'] else None
                                  )
        deps = get_deps()
        session = deps.session
        session.add(db_res)
        session.commit()
        session.close()
        if self.extended:
            location = fill_dc_from_obj(DC=so_ana_mu.ExtendedKey,
                                        obj=prefect.context,
                                        add_dict={'result_as_json': self.serializer.serialize(value_, as_bytes=False)},
                                        get_default=lambda x: -1 if x == 'map_index' else None
                                        )
        else:
            location = fill_dc_from_obj(DC=so_ana_mu.LocationKey,
                                        obj=prefect.context,
                                        get_default=lambda x: -1 if x == 'map_index' else None
                                        )
        return Result(value=value_, location=str(location))


@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful, result=PGResult())
def start_step(step2info: Dict[str, so_ana_mu.StepRequest], label: str)->so_ana_mu.StepRequest:
    deps = get_deps(db_logger_name='start_step.db')
    step_info = step2info[label]
    if step_info.request_type == step_info.request_type==so_ana_mu.REQU_TYPE_LST[0]:
        session = deps.session
        curr_step = session.get(so_ana_mu.JobStepOverview, {'step': step_info.step, 'step_label': step_info.label})
        curr_step.started_at_timest = datetime.now()
        session.commit()
    return step_info

def _asdict(data: Any)->Any:
    if is_dataclass(data):
        return asdict(data)
    elif isinstance(data, str) or isinstance(data, int) or isinstance(data, float) or isinstance(data, bool):
        return data
    elif isinstance(data, list):
        return [_asdict(item) for item in data]
    elif isinstance(data, dict):
        return {key: _asdict(value) for key, value in data.items()}


def finish_step(step_info: so_ana_mu.StepRequest,
                exit_code: int,
                exit_message: str,
                result: Any)->so_ana_mu.StepFinishedReport:
    deps = get_deps(db_logger_name='finish_step.db')
    if step_info.request_type == so_ana_mu.REQU_TYPE_LST[0]:

        session = deps.session

        curr_step = session.get(so_ana_mu.JobStepOverview, {'step': step_info.step, 'step_label': step_info.label})
        curr_step.finished_at_timest = datetime.now()
        curr_step.result = _asdict(result)
        curr_step.exit_code = exit_code
        curr_step.exit_message = exit_message
        session.commit()
    return so_ana_mu.StepFinishedReport(step=step_info.step,
                                        label=step_info.label,
                                        exit_code=exit_code,
                                        msg=exit_message,
                                        result=result)

@task(result=PGResult(extended=True))
def get_param(config_yaml: str):
    """receives option for some option keys / create new options in flow_config.py"""

    flow_data_schema = marshmallow_dataclass.class_schema(so_ana_mu.FlowOptions)()
    with open(os.path.join(so_ana_util.PROJ_CONFIG_PATH, config_yaml), 'r') as file:
        data = flow_data_schema.load(yaml.safe_load(file))
        return data

@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful, result=PGResult())
def prepare_job_run(des_config: so_ana_mu.FlowOptions,
                    user_agent: str,
                    from_email: str) -> Dict[str, so_ana_mu.StepRequest]:
    """
    Prepares job run
    :param des_config: config object
    :return: dictionary with excecution option for individual steps (Dict[str, so_ana_mu.StepRequest]
    """
    def get_std_label(des_config, step):
        if step <= '#3':
            return des_config.download_opts.opts_label + f'_{step}'
        elif step == '#4':
            return des_config.pre_proc_opts.opts_label
        elif step == '#5':
            return des_config.vect_opts.opts_label
        elif step == '#6':
            return des_config.ml_opts.opts_label
        elif step == '#7':
            return des_config.rep_opts.opts_label
        elif step == '#8':
            return 'reporting_'+str(uuid.uuid4())
        else:
            raise RuntimeError(f'invalid step, {step}')

    deps = get_deps(db_logger_name='prepare_job_run.log_db')
    logger = prefect.context.get('logger')
    res = so_ana_mu.JobOverview(
                    description = des_config.description,
                    flow_name = prefect.context.flow_name,
                    flow_id = prefect.context.flow_id,
                    flow_run_id = prefect.context.flow_run_id,
                    flow_run_name=prefect.context.flow_run_name,
                    stack_exchange_type = des_config.stack_exchange_type,
                    topic=des_config.topic,
                    download_opts = asdict(des_config.download_opts),
                    pre_proc_opts= asdict(des_config.pre_proc_opts),
                    vect_opts= asdict(des_config.vect_opts),
                    ml_opts= asdict(des_config.ml_opts),
                    rep_opts= asdict(des_config.rep_opts),
                    use_step_step=getattr(des_config.use_step, 'step', None),
                    use_step_label=getattr(des_config.use_step, 'label', None),
                    started_at_timest=datetime.now(),
                    finished_at_timst=None,
                    exit_code=None,
                    exit_msg=None,
                    modus=prefect.context.modus,
                    result=None,
                    flow_opts=asdict(des_config),
                    step_2_info={},
                    user_agent=user_agent,
                    from_email=from_email
    )
    session = deps.session

    exc_dict = {}
    if res.use_step_step is not None:
        job_step_res = session.get(so_ana_mu.JobStepOverview, {'step': res.use_step_step, 'step_label': res.use_step_label})
        if job_step_res is None:
            raise ValueError(f'no entry exists for step="{res.use_step_step}" and label="{res.use_step_label}"')
        elif not(job_step_res.exit_code == 0):
            raise ValueError(f'step="{job_step_res.step}" and label="{job_step_res.step_label}" did not terminate successfully.')
        else:
            # fill steps that shall not be excecuted
            for i, label in enumerate(job_step_res.prev_step_lbls):
                step = f'#{i+1}'
                exc_dict[step]=so_ana_mu.StepRequest(   step=step,
                                                        label=label,
                                                        request_type=so_ana_mu.REQU_TYPE_LST[1]
                                    )
                exc_dict[step].set_artefacts_from_db(session=session, serializer=serializer)
            step = res.use_step_step
            exc_dict[step]=so_ana_mu.StepRequest(   step=step,
                                                    label=res.use_step_label,
                                                    request_type=so_ana_mu.REQU_TYPE_LST[1]
                                              )
            exc_dict[step].set_artefacts_from_db(session=session, serializer=serializer)

    # fill remaining steps
    nr_st_steps = len(exc_dict.keys())

    qu_dict = {}
    for i in range(1 + nr_st_steps, 9):
        step = f'#{i}'
        label = get_std_label(des_config=des_config,
                              step=step)
        exc_dict[f'#{i}']=so_ana_mu.StepRequest(step=step,
                                                label=label,
                                                request_type=so_ana_mu.REQU_TYPE_LST[0],

                          )
        qu_dict[f'step_{i}'] = step
        qu_dict[f'label_{i}'] = label

    # check if requested steps exist - if so raise ValueError
    cond = ' or '.join([f'(step=%(step_{i})s and step_label=%(label_{i})s)' for i in range(1 + nr_st_steps, 9)])
    q = 'select count(*) from so_ana_management.steps_overview where ' + cond

    res_ex_qu = deps.conn.execute(q, qu_dict).fetchone()[0]

    if res_ex_qu > 0:
        raise ValueError(f'{res_ex_qu} of the requested steps exist: "{qu_dict}"')
    deps.conn.close()
    # generate step infos and write to db

    prev_lst = [exc_dict[f'#{step}'].label for step in range(1, 1 + nr_st_steps)]
    for i in range(1 + nr_st_steps, 9):
        step=f'#{i}'
        step_label = exc_dict[step].label
        new_entry = so_ana_mu.JobStepOverview(
                                flow_name = prefect.context.flow_name,
                                flow_id = prefect.context.flow_name,
                                flow_run_id = prefect.context.flow_run_id,
                                flow_run_name = prefect.context.flow_run_name,
                                step = step,
                                step_label = step_label,
                                placed_at_timest=datetime.now(),
                                started_at_timest = None,
                                finished_at_timest=None,
                                result=None,
                                exit_code=None,
                                exit_msg=None,
                                prev_step_lbls=prev_lst.copy(),
                                modus=prefect.context.modus
        )
        session.add(new_entry)
        prev_lst.append(step_label)

    res.step_2_info = _asdict(exc_dict)
    session.add(res)
    session.commit()
    session.close()

    # create target folders
    target_folder = os.path.join(so_ana_util.PROJ_OUTP_PATH, prefect.context.flow_run_id)
    os.mkdir(target_folder)

    lbl_set = set()

    for var in [des_config.vect_opts.storage_location,
                 des_config.ml_opts.storage_location,
                 des_config.rep_opts.wc_base_location,
                 des_config.rep_opts.LDAvis_base_location]:
        if not(var is None):
            lbl_set.add(var)

    for lbl in lbl_set:
        os.mkdir(os.path.join(target_folder, lbl))

    return exc_dict

@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=always_run, result=PGResult(extended=True))
def finish_flow_run(step_info, item_list):
    deps = get_deps(db_logger_name='finish_flow_run.db')

    curr_job = deps.session.get(so_ana_mu.JobOverview, {'flow_run_id': prefect.context.flow_run_id})

    exit_code = 0
    for item in item_list:
        exit_code = exit_code | item.exit_code
    msg = ';'.join([item.msg for item in item_list if not (item.msg is None or len(item.msg)==0)])

    curr_job.exit_code = exit_code
    curr_job.exit_msg=msg
    curr_job.finished_at_timst = datetime.now()
    curr_job.result = _asdict(item_list)
    deps.session.commit()
    deps.session.close()

    return finish_step( step_info=step_info,
                        exit_code=exit_code,
                        exit_message=msg,
                        result=item_list)



@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful,
      result=PGResult())
def get_page_number(step_info: so_ana_mu.StepRequest,
                    flow_info: so_ana_mu.FlowOptions,
                    user_agent: str,
                    from_email: str) -> List[so_ana_mu.PageCountReport]:
    deps = get_deps(db_logger_name='so_ana_extract_posts.db')

    prod_container = extr_post_deps.Prod_container()
    prod_container.config.from_dict({'logger': deps.script_logger,
                                     'stack_exchange_ws': flow_info.stack_exchange_type,
                                     'user_agent': user_agent,
                                     'from_email': from_email,
                                     'requ_delay': flow_info.download_opts.download_rate_delay,
                                     'recovery_timeout': flow_info.download_opts.error_retry_delay
                                     })
    downloader=prod_container.page_downloader()
    logger=deps.script_logger

    # tst_outp_handler = tst_container.tst_handler()
    # tst_outp_handler.reset_loglist()
    topic=flow_info.topic

    nr_pages = extract_posts.extract_nr_pages(logger=logger,
                                              downloader=downloader,
                                              topic=topic)
    logger.info(f'Number of pages: {nr_pages}')
    batches = [so_ana_mu.PageCountReport(   step=step_info.step,
                                            label=step_info.label,
                                            exit_code=0,
                                            msg='',
                                            page_number_total=nr_pages,
                                            divisor=flow_info.download_opts.batch_count,
                                            batch_id = i
                                            )
               for i in range(flow_info.download_opts.batch_count)
               ]
    return batches

@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful, result=PGResult())
def skip_extract_page_number(step_info: so_ana_mu.StepRequest,
                             flow_info: so_ana_mu.FlowOptions) -> List[so_ana_mu.PageCountReport]:
    batches = [so_ana_mu.SkipPageCountReport(step=step_info.step,
                                             label=step_info.label,
                                             exit_code=0,
                                             msg='',
                                             page_number_total=0,
                                             divisor=flow_info.download_opts.batch_count,
                                             batch_id=i
                                             )
               for i in range(flow_info.download_opts.batch_count)
               ]
    return batches

@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful, result=PGResult())
def exc_condition(step_info: so_ana_mu.StepRequest):
    if step_info.request_type == so_ana_mu.REQU_TYPE_LST[0]:
        return True # execute step
    else:
        return False

class OptionalFlow:

    def __init__(self, reg_task, skip_task, cond_name):
        self.succ_task = reg_task
        self.skip_task = skip_task
        self.cond_name = cond_name

    def __call__(self, step_info: so_ana_mu.StepRequest, *args, **kwargs):
        cond = exc_condition(step_info, task_args=dict(name=self.cond_name))

        with case(cond, True):
            res1 = self.succ_task(step_info, *args, **kwargs)
        with case(cond, False):
            res2 = self.skip_task(step_info, *args, **kwargs)
        return merge(res1, res2)


@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful,
      result=PGResult())
def download_pages(step_info: so_ana_mu.StepRequest,
                   flow_info: so_ana_mu.FlowOptions,
                   batch: so_ana_mu.PageCountReport,
                   user_agent: str,
                   from_email: str):
    batch_id = batch.batch_id
    step = step_info.step
    step_label = step_info.label
    page_nr = batch.page_number_total
    topic = flow_info.topic

    if page_nr==0:
        raise RuntimeError(f'Invalid page number {page_nr} found!')

    deps = get_deps(db_logger_name=f'so_ana_extract_posts_[{batch_id}].db',
                    script_logger_name= f'so_ana_extract_posts_[{batch_id}].script')

    prod_container = extr_post_deps.Prod_container()
    prod_container.config.from_dict({'logger': deps.script_logger,
                                     'stack_exchange_ws': flow_info.stack_exchange_type,
                                     'user_agent': user_agent,
                                     'from_email': from_email,
                                     'requ_delay': flow_info.download_opts.download_rate_delay,
                                     'recovery_timeout': flow_info.download_opts.error_retry_delay
                                     })
    downloader=prod_container.page_downloader()
    logger=deps.script_logger
    ord_key_generator=itertools.count(start=batch_id, step=batch.divisor)

    dwnl_page_succ_report = so_ana_mu.PageDownloadsSuccessReport(   step=step_info.step,
                                                                    label=step_info.label,
                                                                    divisor=batch.divisor,
                                                                    batch_id=batch_id
                                                                )
    result_class_name_dwnl_page = so_ana_worker_schemas.DownloadPageResult.__name__
    result_class_name_extr_post = so_ana_worker_schemas.ExtractResult.__name__
    for i in range(batch_id, page_nr, batch.divisor):
        try:
            logger.info(f'Extracting page {i + 1}')
            dwnl_page_res = extract_posts.download_page(downloader=downloader,
                                                        topic=topic,
                                                        logger=logger,
                                                        step=step,
                                                        step_label=step_label,
                                                        ord_key=i,
                                                        modus=prefect.context.modus
                                                        )
            res_log_entry = so_ana_mu.PageResult(   step=step,
                                                    step_label=step_label,
                                                    ord_key=i,
                                                    flow_run_id=prefect.context.flow_run_id,
                                                    flow_run_name=prefect.context.flow_run_name,
                                                    result_class_name = result_class_name_dwnl_page,
                                                    exit_code=dwnl_page_res.dwnl_page_result.exit_code,
                                                    exit_msg=dwnl_page_res.dwnl_page_result.exit_message,
                                                    modus=prefect.context.modus,
                                                    page_nr=i+1
                                                )
            deps.save_to_db(data=res_log_entry,
                            key_lst=['step', 'step_label', 'ord_key', 'result_class_name'],
                            to_pg=True,
                            to_es=False
                            )

            logger.info(f'Result of download for page {i + 1}: {dwnl_page_res.dwnl_page_result}')
        except Exception as exc:
            res_log_entry = so_ana_mu.PageResult(step=step,
                                                 step_label=step_label,
                                                 ord_key=i,
                                                 flow_run_id=prefect.context.flow_run_id,
                                                 flow_run_name=prefect.context.flow_run_name,
                                                 result_class_name=result_class_name_dwnl_page,
                                                 exit_code=1,
                                                 exit_msg=f'{exc}',
                                                 modus=prefect.context.modus,
                                                 page_nr=i + 1
                                                 )
            deps.save_to_db(data=res_log_entry,
                            key_lst=['step', 'step_label', 'ord_key', 'result_class_name'],
                            to_pg=True,
                            to_es=False
                       )

        try:
            logger.info(f'Start extracting results from page {i+1}')
            extr_pages_info = extract_posts.extract_meta(dwnl_page_res.raw_page_content,
                                                         logger=logger,
                                                         step=step,
                                                         step_label=step_label,
                                                         ord_key_generator=ord_key_generator,
                                                         test_fraction=flow_info.ml_opts.test_fraction,
                                                         val_fraction=flow_info.ml_opts.val_fraction,
                                                         modus=prefect.context.modus
                                                         )
        except Exception as exc:
            logger.error(f'Error when extracting posts on page {i+1} (ord_key={i})' )

        write_success = 0
        write_failure = 0
        for item in extr_pages_info:
            try:
                deps.save_to_db(data=item.extract_data,
                                key_lst=['step', 'step_label', 'ord_key'],
                                to_pg = True,
                                to_es = True
                           )
                write_success += 1
            except Exception as exc:
                write_failure += 1
                logger.error(f'Error when extracting post infos from page {i+1}  / item "{item}": "{exc}"')

            try:
                res_log_entry_on_post = so_ana_mu.PostResult(   step=step,
                                                                step_label=step_label,
                                                                ord_key=item.extract_data.ord_key,
                                                                flow_run_id=prefect.context.flow_run_id,
                                                                flow_run_name=prefect.context.flow_run_name,
                                                                result_class_name = result_class_name_extr_post,
                                                                exit_code=item.extract_result.exit_code,
                                                                exit_msg=item.extract_result.exit_message,
                                                                modus=prefect.context.modus,
                                                                post_id=item.extract_data.post_id,
                                                                ml_tag=item.extract_result.ml_tag
                                                           )
                deps.save_to_db(data=res_log_entry_on_post,
                                key_lst=['step', 'step_label', 'ord_key', 'result_class_name'],
                                to_pg=True,
                                to_es=False
                           )

            except Exception as exc:
                res_log_entry_on_post = so_ana_mu.PostResult(step=step,
                                                             step_label=step_label,
                                                             ord_key=getattr(item.extract_data, 'ord_key', -1),
                                                             flow_run_id=prefect.context.flow_run_id,
                                                             flow_run_name=prefect.context.flow_run_name,
                                                             result_class_name=result_class_name_extr_post,
                                                             exit_code=1,
                                                             exit_msg=f'{exc}',
                                                             modus=prefect.context.modus,
                                                             post_id=getattr(item.extract_data, 'post_id', -1)
                                                             )
                deps.save_to_db(data=res_log_entry_on_post,
                                key_lst=['step', 'step_label', 'ord_key', 'result_class_name'],
                                to_pg=True,
                                to_es=False
                           )

        logger.info(f'Finished: extracting results from page {i + 1}. Data for {write_success} posts written to '
                    f'pg and es / problems for {write_failure} posts.')
        dwnl_page_succ_report.nr_success += sum([1 for item in extr_pages_info if item.extract_result.exit_code==0])
        dwnl_page_succ_report.nr_failure += sum([1 for item in extr_pages_info if item.extract_result.exit_code>0])

    if dwnl_page_succ_report.nr_failure > flow_info.download_opts.max_dwnl_errors_per_batch:
        dwnl_page_succ_report.exit_code = 1
        dwnl_page_succ_report.msg = f'Error threshold for download of pages reached.'
    else:
        dwnl_page_succ_report.exit_code = 0
        dwnl_page_succ_report.msg = ''

    return dwnl_page_succ_report

@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful,
      result=PGResult())
def skip_download_pages(step_info: so_ana_mu.StepRequest,
                        flow_info: so_ana_mu.FlowOptions,
                        batch: so_ana_mu.PageCountReport,
                        user_agent: str,
                        from_email: str):
    return so_ana_mu.SkipPageDownloadsSuccessReport(step=step_info.step,
                                                    label=step_info.label,
                                                    divisor=batch.divisor,
                                                    batch_id=batch.batch_id
                                                    )

@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful,
      result=PGResult())
def finish_dwnl_step(step_info: so_ana_mu.StepRequest,
                     res_lst: List[Union[so_ana_mu.PageDownloadsSuccessReport, so_ana_mu.PostDownloadsSuccessReport]])\
                     ->so_ana_mu.StepFinishedReport:
    if step_info.step == '#1':
        res_obj = so_ana_mu.PageDownloadsSuccessReport
        add_dict = dict(divisor=res_lst[0].divisor, batch_id=None)
    elif step_info.step == '#2':
        res_obj = so_ana_mu.PostDownloadsSuccessReport
        add_dict = dict()
    else:
        raise NotImplementedError(f'"{step_info.step}" is not a valid download step!')
    ret = res_obj(  step=step_info.step,
                    label=step_info.label,
                    exit_code=0,
                    msg='',
                    nr_success=0,
                    nr_failure=0,
                    **add_dict
                  )
    for item in res_lst:
        ret.exit_code = ret.exit_code | item.exit_code
        ret.msg += '' if item.msg is None or item.msg == '' else  f';{item.msg}'
        ret.nr_success += item.nr_success
        ret.nr_failure += item.nr_failure

    return finish_step(step_info, exit_code=ret.exit_code, exit_message=ret.msg, result=ret)

@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful,
      result=PGResult())
def download_posts(step_info: so_ana_mu.StepRequest,
                   flow_info: so_ana_mu.FlowOptions,
                   page_download_result: so_ana_mu.PageDownloadsSuccessReport,
                   user_agent: str,
                   from_email: str):
    deps = get_deps(db_logger_name=f'so_ana_download_posts_[{page_download_result.batch_id}].db',
                    script_logger_name=f'so_ana_download_posts_[{page_download_result.batch_id}].script')

    prod_container = extr_post_deps.Prod_container()
    prod_container.config.from_dict({'logger': deps.script_logger,
                                     'stack_exchange_ws': flow_info.stack_exchange_type,
                                     'user_agent': user_agent,
                                     'from_email': from_email,
                                     'requ_delay': flow_info.download_opts.download_rate_delay,
                                     'recovery_timeout': flow_info.download_opts.error_retry_delay
                                     })
    downloader = prod_container.page_downloader()
    logger = deps.script_logger

    result_class_name = so_ana_worker_schemas.DownloadPostResult.__name__
    download_success_report = so_ana_mu.PostDownloadsSuccessReport( step=step_info.step,
                                                                    label=step_info.label,
                                                                  )

    for row in page_download_result.extr_post_iterator(deps.conn):
        post_id = None
        try:
            post_id = row['post_id']
            ord_key = row['ord_key']
            ml_tag = row['ml_tag']
            download_res = extract_posts.download_post(downloader=downloader,
                                                       logger=logger,
                                                       step=step_info.step,
                                                       step_label=step_info.label,
                                                       post_id=post_id,
                                                       ord_key=ord_key,
                                                       ml_tag=ml_tag,
                                                       modus=prefect.context.modus)
            deps.save_to_db(data=download_res.raw_post_content,
                            key_lst = ['step', 'step_label', 'ord_key'],
                            to_pg=False,
                            to_es=True)

            res_log_entry_on_post = so_ana_mu.PostResult(step=step_info.step,
                                                         step_label=step_info.label,
                                                         ord_key=download_res.raw_post_content.ord_key,
                                                         flow_run_id=prefect.context.flow_run_id,
                                                         flow_run_name=prefect.context.flow_run_name,
                                                         result_class_name=result_class_name,
                                                         exit_code=download_res.dwnl_post_result.exit_code,
                                                         exit_msg=download_res.dwnl_post_result.exit_message,
                                                         modus=prefect.context.modus,
                                                         post_id=post_id,
                                                         ml_tag=ml_tag
                                                         )

            deps.save_to_db(data=res_log_entry_on_post,
                            key_lst=['step', 'step_label', 'ord_key', 'result_class_name'],
                            to_pg=True,
                            to_es=False)
            download_success_report.nr_success +=1
        except Exception as exc:
            download_success_report.nr_failure += 1
            res_log_entry_on_post = so_ana_mu.PostResult(step=step_info.step,
                                                         step_label=step_info.label,
                                                         ord_key=download_res.raw_post_content.ord_key,
                                                         flow_run_id=prefect.context.flow_run_id,
                                                         flow_run_name=prefect.context.flow_run_name,
                                                         result_class_name=result_class_name,
                                                         exit_code=1,
                                                         exit_msg=f'{exc}',
                                                         modus=prefect.context.modus,
                                                         post_id=post_id,
                                                         ml_tag=ml_tag
                                                         )

            deps.save_to_db(data=res_log_entry_on_post,
                            key_lst=['step', 'step_label', 'ord_key', 'result_class_name'],
                            to_pg=True,
                            to_es=False)
    if download_success_report.nr_failure > flow_info.download_opts.max_dwnl_errors_per_batch:
        download_success_report.exit_code = 1
        download_success_report.msg = f'Error threshold for download of pages reached.'
    else:
        download_success_report.exit_code = 0
        download_success_report.msg = ''
    deps.conn.close()
    return download_success_report

@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful,
      result=PGResult())
def skip_download_posts(step_info: so_ana_mu.StepRequest,
                        flow_info: so_ana_mu.FlowOptions,
                        page_download_result: so_ana_mu.PageDownloadsSuccessReport,
                        user_agent: str,
                        from_email: str
                        ):
    return so_ana_mu.SkipPostDownloadsSuccessReport(step=step_info.step,
                                                    label=step_info.label,
                                                    nr_failure=0,
                                                    nr_success=0,
                                                    exit_code=0,
                                                    msg=''
                                                  )

@task(nout=2, max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful, result=PGResult())
def get_postprocessing_batch_info(step_2_res: so_ana_mu.StepFinishedReport,
                                  flow_info: so_ana_mu.FlowOptions):
    batch_count = flow_info.preproc_batch_count
    batches = [so_ana_mu.BatchResult(   step=step_2_res.step,
                                        label=step_2_res.label,
                                        divisor=batch_count,
                                        batch_id=i,
                                        result_class_name=so_ana_worker_schemas.DownloadPostResult.__name__,
                                        data_class_name=so_ana_worker_schemas.PostRawData.__name__
                                    )
                for i in range(batch_count)
            ]
    return batches

@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful, result=PGResult())
def extract_post_meta(step_info: so_ana_mu.StepRequest,
                      batch_result: so_ana_mu.BatchResult):
    deps = get_deps(db_logger_name=f'so_ana_process_posts_[{batch_result.batch_id}].db',
                    script_logger_name=f'so_ana_process_posts_[{batch_result.batch_id}].script')

    result_class_name = so_ana_worker_schemas.ExtractResult.__name__
    data_class_name = so_ana_worker_schemas.QuestionInfo.__name__
    nr_success=0
    nr_failure=0
    for row in batch_result.result_iterator(deps.conn):
        post_id = -1
        ord_key = -1
        ml_tag = -1
        try:
            post_id = row['post_id']
            ord_key = row['ord_key']
            ml_tag = row['ml_tag']
            deps.script_logger.info(f'Start extracting information from post ord_key={ord_key} (post_id={post_id})')
            prev_key = dict_to_es_key({ 'step': batch_result.step,
                                        'step_label': batch_result.label,
                                        'ord_key': ord_key
                                    })

            raw_data = deps.d2es.get(so_ana_worker_schemas.PostRawData, prev_key).content_raw
            transformed_data = so_ana_process_posts.parse_raw_file(raw_data=raw_data,
                                                                   for_step=step_info.step,
                                                                   for_step_label=step_info.label,
                                                                   post_id=post_id,
                                                                   ord_key=ord_key,
                                                                   ml_tag=ml_tag,
                                                                   modus=prefect.context.modus
                                                                   )

            key = dict_to_es_key({  'step': step_info.step,
                                    'step_label': step_info.label,
                                    'ord_key': ord_key
                                })
            deps.d2es(id=key, data=transformed_data.extract_data)
            res_entry = so_ana_mu.PostResult(   step=step_info.step,
                                                step_label=step_info.label,
                                                ord_key=ord_key,
                                                flow_run_id=prefect.context.flow_run_id,
                                                flow_run_name=prefect.context.flow_run_name,
                                                result_class_name=result_class_name,
                                                exit_code=transformed_data.extract_result.exit_code,
                                                exit_msg=transformed_data.extract_result.exit_message,
                                                modus=prefect.context.modus,
                                                post_id=post_id,
                                                ml_tag=ml_tag
                                            )

            deps.save_to_db(data=res_entry,
                            key_lst=['step', 'step_label', 'ord_key', 'result_class_name'],
                            to_pg=True,
                            to_es=False)
            nr_success += 1
        except Exception as exc:
            deps.script_logger.error(f'{exc}')
            res_entry = so_ana_mu.PostResult(step=step_info.step,
                                             step_label=step_info.label,
                                             ord_key=ord_key,
                                             flow_run_id=prefect.context.flow_run_id,
                                             flow_run_name=prefect.context.flow_run_name,
                                             result_class_name=result_class_name,
                                             exit_code=2,
                                             exit_msg=f'Unhandled exception: {exc}',
                                             modus=prefect.context.modus,
                                             post_id=post_id,
                                             ml_tag=ml_tag
                                             )

            deps.save_to_db(data=res_entry,
                            key_lst=['step', 'step_label', 'ord_key', 'result_class_name'],
                            to_pg=True,
                            to_es=False)

            nr_failure +=1

        deps.script_logger.info(f'Finished extracting information from post ord_key={ord_key} (post_id={post_id})')
    deps.conn.close()
    return so_ana_mu.BatchResult(step=step_info.step,
                                 label=step_info.label,
                                 divisor=batch_result.divisor,
                                 batch_id=batch_result.batch_id,
                                 result_class_name=result_class_name,
                                 data_class_name=data_class_name,
                                 nr_success = nr_success,
                                 nr_failure = nr_failure
                                 )

@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful, result=PGResult())
def skip_extract_post_meta(step_info: so_ana_mu.StepRequest,
                           batch_result: so_ana_mu.BatchResult):
    result_class_name = so_ana_worker_schemas.ExtractResult.__name__
    data_class_name = so_ana_worker_schemas.QuestionInfo.__name__
    return so_ana_mu.BatchResult(   step=step_info.step,
                                    label=step_info.label,
                                    divisor=batch_result.divisor,
                                    batch_id=batch_result.batch_id,
                                    result_class_name=result_class_name,
                                    data_class_name=data_class_name
                                 )

@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful, result=PGResult(extended=True))
def finish_doc_transformation_task(step_info: so_ana_mu.StepRequest,
                                   summary_lst: List[so_ana_mu.BatchResult]):
    ret = so_ana_mu.TransformStepSummaryReport.from_batch_result_list(step_info, summary_lst)
    return finish_step(step_info, exit_code=ret.exit_code, exit_message=ret.msg, result=ret)

@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful, result=PGResult())
def tokenize_documents(step_info: so_ana_mu.StepRequest,
                       flow_info: so_ana_mu.FlowOptions,
                       batch_result: so_ana_mu.BatchResult):
    deps = get_deps(db_logger_name=f'so_ana_tokenize_posts_[{batch_result.batch_id}].db',
                    script_logger_name=f'so_ana_tokenize_posts_[{batch_result.batch_id}].script')

    result_class_name = so_ana_worker_schemas.TokenizationResult.__name__
    data_class_name = so_ana_worker_schemas.TokenizationData.__name__
    nr_success=0
    nr_failure=0
    for row in batch_result.result_iterator(deps.conn):
        post_id=-1
        ord_key=-1
        ml_tag=-1
        try:
            post_id = row['post_id']
            ord_key = row['ord_key']
            ml_tag = row['ml_tag']
            deps.script_logger.info(f'Start tokenizing post ord_key={ord_key} (post_id={post_id})')
            prev_key = dict_to_es_key({ 'step': batch_result.step,
                                        'step_label': batch_result.label,
                                        'ord_key': ord_key
                                        }
                                      )

            question_info = deps.d2es.get(so_ana_worker_schemas.QuestionInfo, prev_key)
            deps.script_logger.info(f'payloady: document={question_info} (post_id={post_id})')

            tokenized_data = so_ana_process_posts.tokenize(document=question_info,
                                                           for_step=step_info.step,
                                                           for_step_label=step_info.label,
                                                           post_id=post_id,
                                                           ord_key=ord_key,
                                                           base_content=flow_info.pre_proc_opts.base_content,
                                                           to_lower_case=flow_info.pre_proc_opts.to_lower_case,
                                                           use_lemmatizer=flow_info.pre_proc_opts.use_lemmatizer,
                                                           filter_gensim_stopwords=flow_info.pre_proc_opts.filter_gensim_stopwords,
                                                           own_stopword_lst=flow_info.pre_proc_opts.own_stopword_lst,
                                                           ml_tag=ml_tag,
                                                           modus=prefect.context.modus
                                                           )
            key = dict_to_es_key({'step': step_info.step,
                                  'step_label': step_info.label,
                                  'ord_key': ord_key
                                  }
                                 )

            deps.d2es(id=key, data=tokenized_data.tok_data)
            res_entry = so_ana_mu.PostResult(   step=step_info.step,
                                                step_label=step_info.label,
                                                ord_key=ord_key,
                                                flow_run_id=prefect.context.flow_run_id,
                                                flow_run_name=prefect.context.flow_run_name,
                                                result_class_name=result_class_name,
                                                exit_code=tokenized_data.tok_result.exit_code,
                                                exit_msg=tokenized_data.tok_result.exit_message,
                                                modus=prefect.context.modus,
                                                post_id=post_id,
                                                ml_tag=ml_tag
                                            )

            deps.save_to_db(data=res_entry,
                            key_lst=['step', 'step_label', 'ord_key', 'result_class_name'],
                            to_pg=True,
                            to_es=False)
            nr_success += 1
        except Exception as exc:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            deps.script_logger.error(f'Exception: {exc}, traceback: {traceback.extract_tb(exc_traceback)}')
            res_entry = so_ana_mu.PostResult(step=step_info.step,
                                             step_label=step_info.label,
                                             ord_key=ord_key,
                                             flow_run_id=prefect.context.flow_run_id,
                                             flow_run_name=prefect.context.flow_run_name,
                                             result_class_name=result_class_name,
                                             exit_code=2,
                                             exit_msg=f'Unhandled exception: {exc}, tb: {traceback.extract_tb(exc_traceback)}',
                                             modus=prefect.context.modus,
                                             post_id=post_id,
                                             ml_tag=ml_tag
                                             )

            deps.save_to_db(data=res_entry,
                            key_lst=['step', 'step_label', 'ord_key', 'result_class_name'],
                            to_pg=True,
                            to_es=False)

            nr_failure += 1

        deps.script_logger.info(f'Finished tokenizing post ord_key={ord_key} (post_id={post_id}) exit-code: {res_entry.exit_code}')
    if nr_failure>0:
        raise RuntimeError(f'Could not tokenize {nr_failure} posts out of {nr_failure+nr_success} posts.')
    deps.conn.close()
    return so_ana_mu.BatchResult(step=step_info.step,
                                 label=step_info.label,
                                 divisor=batch_result.divisor,
                                 batch_id=batch_result.batch_id,
                                 result_class_name=result_class_name,
                                 nr_success = nr_success,
                                 nr_failure = nr_failure,
                                 data_class_name=data_class_name
                                 )


@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful, result=PGResult())
def skip_tokenize_documents(step_info: so_ana_mu.StepRequest,
                            flow_info: so_ana_mu.FlowOptions,
                            batch_result: so_ana_mu.BatchResult):
    result_class_name = so_ana_worker_schemas.TokenizationResult.__name__
    data_class_name = so_ana_worker_schemas.TokenizationData.__name__
    return so_ana_mu.BatchResult(step=step_info.step,
                                 label=step_info.label,
                                 divisor=batch_result.divisor,
                                 batch_id=batch_result.batch_id,
                                 result_class_name=result_class_name,
                                 data_class_name=data_class_name
                                 )

@task(nout=2, max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful, result=PGResult())
def generate_dictionary(step_info: so_ana_mu.StepRequest,
                        flow_info: so_ana_mu.FlowOptions,
                        finish_rep: so_ana_mu.StepFinishedReport):

    deps = get_deps(db_logger_name=f'so_ana_create_dictionary.db',
                    script_logger_name=f'so_ana_create_dictionary.script')

    batch_count = flow_info.preproc_batch_count

    doc_iterator = get_doc_iterator(connection=deps.conn,
                                    d2es_obj=deps.d2es,
                                    step_label=finish_rep.result.label,
                                    format='unprocessed_tokens',
                                    ml_tags=[0])

    deps.script_logger.info(f'start creating dictionary...')
    file_key, phr_lbl_lst = so_ana_process_posts.generate_dictionary(
                                                        storage_path=flow_info.vect_opts.get_storage_path(prefect.context.flow_run_id),
                                                        step=step_info.step,
                                                        step_label=step_info.label,
                                                        step_label_4=finish_rep.result.label,
                                                        deps=deps,
                                                        doc_iterator=doc_iterator,
                                                        ext_doc_generator_factory=so_ana_process_posts.get_extended_generator,
                                                        nr_grams=flow_info.vect_opts.nr_grams,
                                                        filter_no_below=flow_info.vect_opts.filter_no_below,
                                                        filter_no_above=flow_info.vect_opts.filter_no_above
    )
    deps.script_logger.info(f'finished creating dictionary, file_key={file_key}')

    batch_res_art_dict = {'dict_key': file_key, 'phrases_keys': phr_lbl_lst}

    erg_artefact = so_ana_mu.Artefact.save_data(session=deps.session,
                                                serializer=serializer,
                                                step=step_info.step,
                                                step_label=step_info.label,
                                                key='dictionary',
                                                value={'storage_path': flow_info.vect_opts.get_storage_path(prefect.context.flow_run_id),
                                                       'keys_dict': batch_res_art_dict
                                                      }
                                                )

    ret = [so_ana_mu.BatchResultDoc(step=finish_rep.result.step,
                                    label=finish_rep.result.label,
                                    divisor=batch_count,
                                    result_class_name = finish_rep.result.result_class_name_set[0],
                                    data_class_name = finish_rep.result.data_class_name_set[0],
                                    batch_id = i,
                                    file_keys = erg_artefact.artefact_value['keys_dict'],
                                    base_path = erg_artefact.artefact_value['storage_path']
                                    )
           for i in range(batch_count)
          ]

    return erg_artefact, ret

@task(nout=2, max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful, result=PGResult())
def skip_generate_dictionary(   step_info: so_ana_mu.StepRequest,
                                flow_info: so_ana_mu.FlowOptions,
                                finish_rep: so_ana_mu.StepFinishedReport):
    batch_count = flow_info.preproc_batch_count
    for item in step_info.artefact_list:
        if item.artefact_key == 'dictionary':
            art = item
            break
    else:
        raise RuntimeError(f'No appropriate artefact found for key "dictionary".')
    ret = [so_ana_mu.BatchResultDoc(step=finish_rep.result.step,
                                    label=finish_rep.result.label,
                                    divisor=batch_count,
                                    result_class_name = finish_rep.result.result_class_name_set[0],
                                    data_class_name = finish_rep.result.data_class_name_set[0],
                                    batch_id = i,
                                    file_keys=art.artefact_value['keys_dict'],
                                    base_path=art.artefact_value['storage_path']
                                    )
           for i in range(batch_count)
          ]

    return art, ret

@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful, result=PGResult())
def documents_2_bow(step_info: so_ana_mu.StepRequest,
                    flow_info: so_ana_mu.FlowOptions,
                    batch_result_doc: so_ana_mu.BatchResultDoc):
    deps = get_deps(db_logger_name=f'so_ana_doc_2_bow_[{batch_result_doc.batch_id}].db',
                    script_logger_name=f'so_ana_doc_2_bow_[{batch_result_doc.batch_id}].script')

    file_keys_dict = batch_result_doc.file_keys

    result_class_name = so_ana_worker_schemas.BoWResult.__name__
    data_class_name = so_ana_worker_schemas.BoWData.__name__
    nr_success=0
    nr_failure=0

    phrases_obj_lst = so_ana_process_posts.load_phrase(batch_result_doc.base_path,
                                                       file_keys_dict['phrases_keys'])

    def post_proc(row):
        nonlocal deps
        nonlocal batch_result_doc
        nonlocal phrases_obj_lst

        ord_key = row['ord_key']
        prev_key = dict_to_es_key({'step': batch_result_doc.step,
                                   'step_label': batch_result_doc.label,
                                   'ord_key': ord_key
                                   }
                                  )
        tokenized_doc = deps.d2es.get(so_ana_worker_schemas.TokenizationData, prev_key)

        tok_data = so_ana_process_posts.ext_tokens_with_phrases(tokenized_doc.tokenized_content, *phrases_obj_lst)
        return row, tok_data

    ext_doc_generator = IteratorFromGenerator(generator=batch_result_doc.result_iterator,
                                              postprocess_callback=post_proc,
                                              conn=deps.conn)

    for row, tok_data in ext_doc_generator:
        post_id=-1
        ord_key=-1
        ml_tag=-1
        try:
            post_id = row['post_id']
            ord_key = row['ord_key']
            ml_tag = row['ml_tag']
            deps.script_logger.info(f'Start tokenizing post ord_key={ord_key} (post_id={post_id})')

            bow_data = so_ana_process_posts.doc_to_bow(for_step=step_info.step,
                                                       for_step_label=step_info.label,
                                                       post_id=post_id,
                                                       ord_key=ord_key,
                                                       storage_path=batch_result_doc.base_path,
                                                       file_key=file_keys_dict['dict_key'],
                                                       document=tok_data,
                                                       ml_tag=ml_tag,
                                                       modus=prefect.context.modus
                                                       )

            key = dict_to_es_key({'step': step_info.step,
                                  'step_label': step_info.label,
                                  'ord_key': ord_key
                                  }
                                 )
            deps.d2es(id=key, data=bow_data.bow_data)
            res_entry = so_ana_mu.PostResult(step=step_info.step,
                                             step_label=step_info.label,
                                             ord_key=ord_key,
                                             flow_run_id=prefect.context.flow_run_id,
                                             flow_run_name=prefect.context.flow_run_name,
                                             result_class_name=result_class_name,
                                             exit_code=bow_data.bow_result.exit_code,
                                             exit_msg=bow_data.bow_result.exit_message,
                                             modus=prefect.context.modus,
                                             post_id=post_id,
                                             ml_tag=ml_tag
                                             )

            deps.save_to_db(data=res_entry,
                            key_lst=['step', 'step_label', 'ord_key', 'result_class_name'],
                            to_pg=True,
                            to_es=False)
            nr_success += 1
        except Exception as exc:
            deps.script_logger.error(f'{exc}')
            res_entry = so_ana_mu.PostResult(step=step_info.step,
                                             step_label=step_info.label,
                                             ord_key=ord_key,
                                             flow_run_id=prefect.context.flow_run_id,
                                             flow_run_name=prefect.context.flow_run_name,
                                             result_class_name=result_class_name,
                                             exit_code=2,
                                             exit_msg=f'Unhandled exception: {exc}',
                                             modus=prefect.context.modus,
                                             post_id=post_id,
                                             ml_tag=ml_tag
                                             )

            deps.save_to_db(data=res_entry,
                            key_lst=['step', 'step_label', 'ord_key', 'result_class_name'],
                            to_pg=True,
                            to_es=False)

            nr_failure += 1

        deps.script_logger.info(f'Finished tokenizing post ord_key={ord_key} (post_id={post_id}) exit-code: {res_entry.exit_code}')
    if nr_failure>0:
        raise RuntimeError(f'Could not transfer {nr_failure} posts out of {nr_failure+nr_success} posts into bag-of-words representation.')
    deps.conn.close()
    return so_ana_mu.BatchResult(step=step_info.step,
                                 label=step_info.label,
                                 divisor=batch_result_doc.divisor,
                                 batch_id=batch_result_doc.batch_id,
                                 result_class_name=result_class_name,
                                 nr_success = nr_success,
                                 nr_failure = nr_failure,
                                 data_class_name=data_class_name
                                 )

@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful, result=PGResult())
def skip_documents_2_bow(step_info: so_ana_mu.StepRequest,
                         flow_info: so_ana_mu.FlowOptions,
                         batch_result_doc: so_ana_mu.BatchResultDoc):
    result_class_name = so_ana_worker_schemas.BoWResult.__name__
    data_class_name = so_ana_worker_schemas.BoWData.__name__
    return so_ana_mu.BatchResult(step=step_info.step,
                                 label=step_info.label,
                                 divisor=batch_result_doc.divisor,
                                 batch_id=batch_result_doc.batch_id,
                                 result_class_name=result_class_name,
                                 nr_success = 0,
                                 nr_failure = 0,
                                 data_class_name=data_class_name
                                 )

@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful, result=PGResult())
def train_ML_model( step_info: so_ana_mu.StepRequest,
                    flow_info: so_ana_mu.FlowOptions,
                    batch_result_doc: so_ana_mu.BatchResultDoc,
                    step_5_info: so_ana_mu.StepRequest)->so_ana_mu.ArtefactShort:

    deps = get_deps(db_logger_name=f'so_ana_create_dictionary.db')
    d2es = deps.d2es

    def post_proc(row):
        nonlocal d2es
        step = row['step']
        label = row['step_label']
        ord_key = row['ord_key']
        key = dict_to_es_key({'step': step,
                              'step_label': label,
                              'ord_key': ord_key
                              }
                             )
        res = d2es.get(so_ana_worker_schemas.BoWData, key).BoW
        return res

    doc_iterable = get_doc_iterator(connection=deps.conn,
                                    d2es_obj=deps.d2es,
                                    step_label=step_5_info.label,
                                    format='keys',
                                    ml_tags=[0])

    lda_key = LDA.create_LDA_model(step=step_info.step,
                                   step_label=step_info.label,
                                   base_path = flow_info.vect_opts.get_storage_path(prefect.context.flow_run_id),
                                   base_path_lda = flow_info.ml_opts.get_storage_path(prefect.context.flow_run_id),
                                   corpus=doc_iterable,
                                   dictionary_key=batch_result_doc.file_keys['dict_key'],
                                   num_topics=flow_info.ml_opts.num_topics,
                                   passes=flow_info.ml_opts.nr_passes
                                   )

    erg_artefact = so_ana_mu.Artefact.save_data(session=deps.session,
                                                serializer=serializer,
                                                step=step_info.step,
                                                step_label=step_info.label,
                                                key='LDA_model_data',
                                                value={'base_path': flow_info.ml_opts.get_storage_path(prefect.context.flow_run_id),
                                                       'lda_key': lda_key}
                                 )
    deps.conn.close()
    return erg_artefact

@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful, result=PGResult())
def skip_train_ML_model(step_info: so_ana_mu.StepRequest,
                        flow_info: so_ana_mu.FlowOptions,
                        batch_result_doc: so_ana_mu.BatchResultDoc,
                        step_5_info: so_ana_mu.StepRequest)->so_ana_mu.ArtefactShort:
    for item in step_info.artefact_list:
        if item.artefact_key == 'LDA_model_data':
            return item
            break
    else:
        raise RuntimeError(f'No appropriate artefact found for key "LDA_model_data".')

@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful, result=PGResult())
def finish_ML_learning_step(step_info: so_ana_mu.StepRequest,
                            LDA_artefact: so_ana_mu.ArtefactShort):
    return finish_step(step_info, exit_code=0, exit_message='', result=LDA_artefact)


@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful, result=PGResult())
def generate_corpus_wordcloud(  step_info: so_ana_mu.StepRequest,
                                step_5_info: so_ana_mu.StepRequest,
                                flow_info: so_ana_mu.FlowOptions,
                                ):
    res = {}
    if not flow_info.rep_opts.get_wc_base_path(prefect.context.flow_run_id) is None:
        deps = get_deps()
        wc_report_obj = so_ana_reporting.WCReports(deps_obj=deps,
                                                   step=step_5_info.step,
                                                   step_label=step_5_info.label)
        base_path = flow_info.rep_opts.get_wc_base_path(prefect.context.flow_run_id)
        timest = datetime.now().strftime('%Y_%m_%d__%H_%M_%S')
        file_name = f'WordCloud_{timest}_{step_info.step}_{step_info.label}.png'
        wc_report_obj.wc_for_corpus(file_name=os.path.join(base_path, file_name))
        res = {'base_path': base_path, 'file_name': file_name}
    erg_artefact = so_ana_mu.Artefact.save_data( session=deps.session,
                                                 serializer=serializer,
                                                 step=step_info.step,
                                                 step_label=step_info.label,
                                                 key='wordcloud',
                                                 value=res
                                                 )
    return erg_artefact

@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful, result=PGResult())
def generate_LDAvis(step_info: so_ana_mu.StepRequest,
                    step_5_info: so_ana_mu.StepRequest,
                    flow_info: so_ana_mu.FlowOptions,
                    dict_artefact: so_ana_mu.ArtefactShort,
                    lda_model_artefact: so_ana_mu.ArtefactShort
                    ):
    res = {}
    if not flow_info.rep_opts.get_LDAvis_base_path(prefect.context.flow_run_id) is None:
        deps = get_deps()
        base_path = flow_info.rep_opts.get_LDAvis_base_path(prefect.context.flow_run_id)
        timest = datetime.now().strftime('%Y_%m_%d__%H_%M_%S')
        file_name_html = f'LDAvis_{timest}_{step_info.step}_{step_info.label}.html'
        file_name_json = f'LDAvis_{timest}_{step_info.step}_{step_info.label}.json'
        so_ana_reporting.generate_lda_vis(dict_artefact_obj=_asdict(dict_artefact),
                                          lda_model_artefact_obj=_asdict(lda_model_artefact),
                                          deps_obj=deps,
                                          step_label=step_5_info.label,
                                          target_file_html=os.path.join(base_path, file_name_html),
                                          target_file_json=os.path.join(base_path, file_name_json))
        res = {'base_path': base_path,
               'file_name_html': file_name_html,
               'file_name_json': file_name_json}
    erg_artefact = so_ana_mu.Artefact.save_data(session=deps.session,
                                                serializer=serializer,
                                                step=step_info.step,
                                                step_label=step_info.label,
                                                key='LDAvis',
                                                value=res
                                                )
    return erg_artefact

@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful, result=PGResult())
def finish_reporting_steps(step_info: so_ana_mu.StepRequest,
                           rep_art_lst: List[so_ana_mu.Artefact]):
    return finish_step(step_info, exit_code=0, exit_message='', result=rep_art_lst)


@task(max_retries=3, retry_delay=timedelta(seconds=5), trigger=all_successful, result=PGResult())
def extract_topics(step_info, step_5_info, lda_model_artefact):
    deps = get_deps(db_logger_name=f'extract_doc_topics.db',
                    script_logger_name=f'extract_doc_topics.script')
    session = deps.session

    overall_topic_weights = defaultdict(lambda: 0.0)
    cnt_tot = 0
    deps.script_logger.info(f'start assigning topic distributions - batch 1')
    for i, topic_info in enumerate(so_ana_reporting.topic_iterator(deps=deps,
                                                                   for_step_label=step_5_info.label,
                                                                   lda_model_artefact=asdict(lda_model_artefact))
                                   ):
        cntx_lst = ['modus', 'flow_run_id', 'task_name', 'task_slug', 'task_run_id', 'map_index',
                    'task_loop_count', 'task_run_count', 'thread', 'process']
        data = so_ana_mu.TopicDistribution(step=step_info.step,
                                           step_label=step_info.label,
                                           **asdict(topic_info),
                                           timestamp=datetime.now(),
                                           **{attr: getattr(prefect.context,attr, None) for attr in cntx_lst}
                                           )

        session.add(data)
        overall_topic_weights[topic_info.topic_id] += topic_info.topic_weight
        cnt_tot += 1
        if cnt_tot % 100 == 0:
            session.commit()
            deps.script_logger.info(f'finish assigning topic distributions - batch {((cnt_tot // 100))}')
            deps.script_logger.info(f'start assigning topic distributions - batch {((cnt_tot // 100) + 1)}')
    session.commit()
    deps.script_logger.info(f'finished assigning topic distributions - totals: {cnt_tot}')
    erg_artefact = so_ana_mu.Artefact.save_data(session=deps.session,
                                                serializer=serializer,
                                                step=step_info.step,
                                                step_label=step_info.label,
                                                key='doc_topic_weights',
                                                value={'cnt_total': cnt_tot, 'total_weight_sum': overall_topic_weights}
                                                )

    return erg_artefact



def get_flow():
    mng_prod_container = management_deps.get_prod_container()
    dask_scheduler_address = mng_prod_container.dask_scheduler_address()

    #env = RemoteEnvironment(
    #    executor="prefect.engine.executors.DaskExecutor",
    #    executor_kwargs={"address": dask_scheduler_address},
    #    labels=["dask"]
   #)

    with Flow("so-analysis",
              executor=DaskExecutor(address=dask_scheduler_address),
              result=PGResult()
              ) as flow:
        config_yaml = Parameter('config_yaml')
        user_agent = Parameter('user_agent')
        from_email = Parameter('from_email')
        flow_info = get_param(config_yaml)
        step2info = prepare_job_run(flow_info,
                                    user_agent,
                                    from_email)

        step_1_info = start_step(step2info, '#1', task_args=dict(name='start step #1'))

        cond_download_pages = exc_condition(step_info=step_1_info, task_args=dict(name="check if extraction of page "
                                                                                       "number necessary"))

        with case(cond_download_pages, True):
            batches_1 = get_page_number(step_info=step_1_info,
                                        flow_info=flow_info,
                                        user_agent=user_agent,
                                        from_email=from_email)
        with case(cond_download_pages, False):
            batches_2 = skip_extract_page_number(step_info=step_1_info,
                                                 flow_info=flow_info)
        batches = merge(batches_1,batches_2)

        dwnl_pages=apply_map(OptionalFlow(download_pages, skip_download_pages, cond_name='check if download of pages '
                                                                                         'necessary'),
                             step_info=unmapped(step_1_info),
                             flow_info=unmapped(flow_info),
                             batch=batches,
                             user_agent=unmapped(user_agent),
                             from_email=unmapped(from_email)
                             )
        step_1_res = finish_dwnl_step(step_1_info, dwnl_pages, task_args=dict(name='finish download of pages'))
        step_2_info = start_step(step2info, '#2', task_args=dict(name='start step #2'))

        dwnl_posts = apply_map( OptionalFlow(download_posts, skip_download_posts, cond_name='check if download of '
                                                                                            'posts necessary'),
                                step_info=unmapped(step_2_info),
                                flow_info=unmapped(flow_info),
                                page_download_result=dwnl_pages,
                                user_agent=unmapped(user_agent),
                                from_email=unmapped(from_email)
                              )

        step_2_res = finish_dwnl_step(step_2_info, dwnl_posts, task_args=dict(name='finish download of posts'))
        preproc_batches = get_postprocessing_batch_info(step_2_res = step_2_res,
                                                        flow_info=flow_info)

        step_3_info = start_step(step2info, '#3', upstream_tasks=[preproc_batches], task_args=dict(name='start step #3'))
        extracted_posts = apply_map(OptionalFlow(extract_post_meta, skip_extract_post_meta, cond_name='check if '
                                                                                                      'extraction of '
                                                                                                      'post meta '
                                                                                                      'information '
                                                                                                      'necessary'),
                                    step_info=unmapped(step_3_info),
                                    batch_result=preproc_batches,
                               )

        step_3_res = finish_doc_transformation_task(step_3_info, extracted_posts,
                                                    task_args=dict(name='finish parsing posts'))

        step_4_info = start_step(step2info, '#4', upstream_tasks=[preproc_batches], task_args=dict(name='start step #4'))
        tokenized_posts = apply_map(OptionalFlow(tokenize_documents, skip_tokenize_documents, cond_name='check if '
                                                                                                        'tokenization necessary'),
                                    step_info=unmapped(step_4_info),
                                    flow_info=unmapped(flow_info),
                                    batch_result=extracted_posts
                                    )
        step_4_res = finish_doc_transformation_task(step_4_info, tokenized_posts,
                                                    task_args=dict(name='finish tokenizing posts'))
        step_5_info = start_step(step2info, '#5', upstream_tasks=[step_4_res], task_args=dict(name='start step #5'))
        cond_create_dict = exc_condition(step_info=step_5_info, task_args=dict(name='check if creation of gensim dictionary necessary'))

        with case(cond_create_dict, True):
            dict_art_1, dictionary_batches_1 = generate_dictionary( step_info=step_5_info,
                                                                    flow_info=flow_info,
                                                                    finish_rep=step_4_res)
        with case(cond_create_dict, False):
            dict_art_2, dictionary_batches_2 = skip_generate_dictionary(step_info=step_5_info,
                                                                        flow_info=flow_info,
                                                                        finish_rep=step_4_res)
        dict_res_tuple = merge( [dict_art_1, dictionary_batches_1],
                                [dict_art_2, dictionary_batches_2])

        dict_art = dict_res_tuple[0]
        dictionary_batches = dict_res_tuple[1]

        bow_docs = apply_map(   OptionalFlow(documents_2_bow, skip_documents_2_bow, cond_name='check if transformation '
                                                                                              'to back-of-words '
                                                                                              'representation necessary'),
                                step_info=unmapped(step_5_info),
                                flow_info=unmapped(flow_info),
                                batch_result_doc=dictionary_batches
                  )

        step_5_res = finish_doc_transformation_task(step_5_info, bow_docs, task_args=dict(name='finish creation of BoW '
                                                                                               'representation'))
        step_6_info = start_step(step2info, '#6', upstream_tasks=[step_5_res], task_args=dict(name='start step #6'))

        cond_train_ML = exc_condition(step_info=step_6_info, task_args=dict(name='check if ML training of LDA model '
                                                                                 'necessary'))

        with case(cond_train_ML, True):
            ml_model_art_1= train_ML_model( step_info=step_6_info,
                                            flow_info=flow_info,
                                            batch_result_doc=dictionary_batches[0],
                                            step_5_info=step_5_info)
        with case(cond_train_ML, False):
            ml_model_art_2 = skip_train_ML_model(   step_info=step_6_info,
                                                    flow_info=flow_info,
                                                    batch_result_doc=dictionary_batches[0],
                                                    step_5_info=step_5_info)
        ml_model_art = merge(ml_model_art_1, ml_model_art_2)

        step_6_res = finish_ML_learning_step(step_6_info, ml_model_art)
        step_7_info =  start_step(step2info, '#7', upstream_tasks=[step_5_res], task_args=dict(name='start step #7'))

        wc_res = generate_corpus_wordcloud(step_info=step_7_info,
                                           step_5_info=step_5_info,
                                           flow_info=flow_info)

        LDAvis_res = generate_LDAvis(step_info=step_7_info,
                                     step_5_info=step_5_info,
                                     flow_info=flow_info,
                                     dict_artefact = dict_art,
                                     lda_model_artefact=ml_model_art)

        topic_weight_res = extract_topics(step_info=step_7_info,
                                          step_5_info=step_5_info,
                                          lda_model_artefact=ml_model_art)

        step_7_res = finish_reporting_steps(step_info=step_7_info,
                                            rep_art_lst=[wc_res, LDAvis_res, topic_weight_res])

        step_8_info = start_step(step2info, '#8', upstream_tasks=[step_7_res], task_args=dict(name='start step #8'))

        final_result = finish_flow_run(step_8_info, [step_1_res, step_2_res, step_3_res, step_4_res,
                                                     step_5_res, step_6_res, step_7_res])


    #client = get_client(address=dask_scheduler_address)
    #client.run(init_logging)
    return flow

if __name__ == '__main__':
    flow = get_flow()
    flow.visualize()