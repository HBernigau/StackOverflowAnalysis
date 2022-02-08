"""
Defines the tables to be used. Note: schemas are separated by bounded context. For each bounded context a
separate table registry is used.

Author: `HBernigau <https://github.com/HBernigau>`_
Date: 01.2022
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine, Date
from sqlalchemy.dialects.postgresql import JSON, ARRAY, UUID

import so_ana_sqlalchemy_models.model_base as mb

cntx_lst = ['so_ana_analysis',
            'so_ana_doc_worker',
            'so_ana_management',
            'so_ana_logging'
            ]

tbl_specs = {}

for schema in cntx_lst:
    tbl_specs[schema] = mb.TableRegistry(schema)

tbl_specs['so_ana_doc_worker']['page_meta_info'] = mb.TblSpec(args=[
                                                        Column('step', String(255), primary_key=True),
                                                        Column('step_label', String(255), primary_key=True),
                                                        Column('ord_key', Integer(), primary_key=True), # changed: 2021-01-16
                                                        Column('post_id', Integer()),
                                                        Column('post_meta_extracted_date', Date()),
                                                        Column('post_url', String(1023)),
                                                        Column('heading', String(1023)),
                                                        Column('excerpt', String(2047)),
                                                        Column('asked_date', Date()),
                                                        Column('votes', Integer()),
                                                        Column('answers', Integer()),
                                                        Column('answer_status', String(255)),
                                                        Column('views', Integer()),
                                                        Column('tags', ARRAY(String(255), dimensions=1)),
                                                        Column('user', String(255)),
                                                        Column('user_url',String(1023)),
                                                        Column('modus', String(7)),
                                                        Column('ml_tag', Integer())
                                                        ]
                                                    )


tbl_specs['so_ana_management']['task_results'] = mb.TblSpec(args=[
                                                        Column('flow_run_id', String(255), primary_key=True),
                                                        Column('date', DateTime()),
                                                        Column('task_slug', String(255), primary_key=True),
                                                        Column('map_index', Integer(), primary_key=True),
                                                        Column('task_loop_count', Integer(), primary_key=True),  # changed: 2021-01-16
                                                        Column('task_run_count', Integer(), primary_key=True),  # changed: 2021-01-16 (switched position)
                                                        Column('result_as_json', JSON()),
                                                        Column('flow_name', String(255)), # changed: 2021-01-16 (switched position)
                                                        Column('flow_run_name', String(255)), # changed: 2021-01-16 (switched position)
                                                        Column('task_name', String(255)), # changed: 2021-01-16 (switched position)
                                                        Column('task_full_name', String(255)),  # removed primary key
                                                        Column('task_id', String(255)), # changed: 2021-01-16 (switched position)
                                                        Column('timestamp', DateTime()),   # changed: 2021-01-16
                                                        Column('task_run_id', String(255)),
                                                        Column('pid', Integer()),  # changed: 2021-01-16 (lower case)
                                                        Column('thread', Integer()),  # changed: 2021-01-16
                                                        Column('modus', String(7))]
                                                    )

tbl_specs['so_ana_management']['job_overview'] = mb.TblSpec(args=[
                                                        Column('description', String(2047)),
                                                        Column('flow_name', String(2047)),
                                                        Column('flow_id', String(2047)),
                                                        Column('flow_run_id', String(2047), primary_key=True),
                                                        Column('flow_run_name', String(2047)),
                                                        Column('stack_exchange_type', String(255)),
                                                        Column('topic', String(255)),
                                                        Column('download_opts', JSON()),
                                                        Column('pre_proc_opts', JSON()), # changed: 2021-01-16
                                                        Column('vect_opts', JSON()),
                                                        Column('ml_opts', JSON()),
                                                        Column('rep_opts', JSON()),
                                                        Column('use_step_step', String(255)),
                                                        Column('use_step_label', String(255)),
                                                        Column('started_at_timest', DateTime()),
                                                        Column('finished_at_timst', DateTime()),
                                                        Column('exit_code', Integer()),
                                                        Column('exit_msg', String()),
                                                        Column('modus', String(7)),
                                                        Column('result', JSON()),
                                                        Column('flow_opts', JSON()),
                                                        Column('step_2_info', JSON()),
                                                        Column('user_agent', String(255)),
                                                        Column('from_email', String(255))
                                                        ]
                                                    )

tbl_specs['so_ana_management']['steps_overview'] = mb.TblSpec(args=[
                                                        Column('flow_name', String(255)),
                                                        Column('flow_id', String(255)),
                                                        Column('flow_run_id', String(255)),
                                                        Column('flow_run_name', String(255)),
                                                        Column('step', String(255), primary_key=True),
                                                        Column('step_label', String(255), primary_key=True),
                                                        Column('placed_at_timest', DateTime()), # 2020-01-16: new!
                                                        Column('started_at_timest', DateTime()),
                                                        Column('finished_at_timest', DateTime()),
                                                        Column('result', JSON()),
                                                        Column('exit_code', Integer()),
                                                        Column('exit_msg', String()),
                                                        Column('prev_step_lbls', ARRAY(String(255), dimensions=1)),
                                                        Column('modus', String(7))]
                                                    )

tbl_specs['so_ana_management']['page_results'] = mb.TblSpec(args=[
                                                        Column('step', String(255), primary_key=True),
                                                        Column('step_label', String(255), primary_key=True),
                                                        Column('ord_key', Integer(), primary_key=True),
                                                        Column('flow_run_id', String(255)),
                                                        Column('flow_run_name', String(255)),
                                                        Column('result_class_name', String(255), primary_key=True),
                                                        Column('exit_code', Integer()),
                                                        Column('exit_msg', String(4095)),
                                                        Column('modus', String(7)),
                                                        Column('page_nr', Integer())]
                                                    )

tbl_specs['so_ana_management']['post_results'] = mb.TblSpec(args=[
                                                        Column('step', String(255), primary_key=True),
                                                        Column('step_label', String(255), primary_key=True),
                                                        Column('ord_key', Integer(), primary_key=True),
                                                        Column('flow_run_id', String(255)),
                                                        Column('flow_run_name', String(255)),
                                                        Column('result_class_name', String(255), primary_key=True),
                                                        Column('exit_code', Integer()),
                                                        Column('exit_msg', String(4095)),
                                                        Column('modus', String(7)),
                                                        Column('post_id', Integer()),
                                                        Column('ml_tag', Integer())
                                                        ]
                                                    )

tbl_specs['so_ana_logging']['prefect_logs'] = mb.TblSpec(args=[
                                                        Column('name', String(255)),
                                                        Column('flow_run_id', String(255)),
                                                        Column('task_name', String(255)),
                                                        Column('task_slug', String(255)),
                                                        Column('task_run_id', String(255)),
                                                        Column('map_index', Integer()),         # 2020-01-16: new!
                                                        Column('task_loop_count', Integer()),  # 2020-01-16: new!
                                                        Column('task_run_count', Integer()),  # 2020-01-16: new!
                                                        Column('thread', Integer()),
                                                        Column('threadName', String(255)),
                                                        Column('process', Integer()),
                                                        Column('processName',String(255)),
                                                        Column('exc_text', String(4095)),
                                                        Column('levelname', String(15)),
                                                        Column('msg', String(4095)),
                                                        Column('timestamp', DateTime()),  # 2020-01-16: new!
                                                        Column('msg_uuid', UUID(as_uuid=True), primary_key=True),
                                                        Column('modus', String(7))]
                                                    )

tbl_specs['so_ana_management']['artefacts'] = mb.TblSpec(args=[
                                                        Column('step', String(255), primary_key=True),
                                                        Column('step_label', String(255), primary_key=True),
                                                        Column('artefact_key', String(255), primary_key=True),
                                                        Column('artefact_value', JSON()),
                                                        Column('modus', String(7)),
                                                        Column('flow_run_id', String(255)),
                                                        Column('timestamp', DateTime()),
                                                        Column('task_name', String(255)),
                                                        Column('task_slug', String(255)),
                                                        Column('task_run_id', String(255)),
                                                        Column('map_index', Integer()),
                                                        Column('task_loop_count', Integer()),
                                                        Column('task_run_count', Integer()),
                                                        Column('thread', Integer()),
                                                        Column('process', Integer())
                                                        ]
)

tbl_specs['so_ana_analysis']['topic_distribution'] = mb.TblSpec(args=[
                                                        Column('step', String(255), primary_key=True),
                                                        Column('step_label', String(255), primary_key=True),
                                                        Column('ord_key', Integer(), primary_key=True),
                                                        Column('post_id', Integer()),
                                                        Column('for_step', String(255)),
                                                        Column('for_step_label', String(255)),
                                                        Column('topic_id', Integer(), primary_key=True),
                                                        Column('topic_weight', Float()),
                                                        Column('modus', String(7)),
                                                        Column('flow_run_id', String(255)),
                                                        Column('timestamp', DateTime()),
                                                        Column('task_name', String(255)),
                                                        Column('task_slug', String(255)),
                                                        Column('task_run_id', String(255)),
                                                        Column('map_index', Integer()),
                                                        Column('task_loop_count', Integer()),
                                                        Column('task_run_count', Integer()),
                                                        Column('thread', Integer()),
                                                        Column('process', Integer())
                                                        ]
)



















