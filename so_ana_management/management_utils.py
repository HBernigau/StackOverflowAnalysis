"""
contains several utilities for flow management including data types

Author: `HBernigau <https://github.com/HBernigau>`_
Date: 01.2022
"""

import  logging.config
from dataclasses import dataclass, field
import uuid
import marshmallow.validate
import so_ana_util.so_ana_json as so_ana_json
from typing import List, Dict, Any
from datetime import datetime
import os
import threading
from elasticsearch import helpers
import json

import so_ana_util

UDF = '#undefined#'
REQU_TYPE_LST=['calculate_new', 'use_old']
STEPS_DICT= { '#1': 'extract_posts', '#2': 'download_posts', '#3': 'extract_post_info', '#4': 'preprocess_posts',
              '#5': 'vectorize_posts', '#6': 'integrate_2_ML_model', '#7': 'report_results', '#8': 'finish_run'}
DATA_TYPE_LST = ['pg', 'es']
ML_TAGS = {0: 'train', 1: 'test', 2: 'validation'}


#define Exceptions...


#define registry for data classes
class DCRegistry:

    def __init__(self):
        self._members = {}

    def register(self, DC):
        self._members[DC.__name__] = DC

    def __call__(self, DC):
        self.register(DC)
        return DC


with_register = DCRegistry()

def get_full_storage_path(flow_id, base_value):
    return os.path.join(so_ana_util.PROJ_OUTP_PATH, flow_id, base_value)


@dataclass
class OptionsBase:
    opts_label: str = field(default_factory=lambda:str(uuid.uuid4()))
    opts_description: str = field(default_factory=lambda:'')

@with_register
@dataclass(frozen=False)
class TokenizationOptions(OptionsBase):
    base_content: str = field(default='all')
    to_lower_case: bool = field(default=True)
    use_lemmatizer: str = field(default='wordnet')
    filter_gensim_stopwords: bool = field(default=True)
    own_stopword_lst: List[str] = field(default_factory=list)

@with_register
@dataclass(frozen=False)
class VectorizationOptions(OptionsBase):
    storage_location: str = field(default=None)
    filter_no_below: int = field(default=1)
    filter_no_above: float = field(default=1.0)
    nr_grams: int = field(default=1)

    def get_storage_path(self, flow_id):
        return get_full_storage_path(flow_id, base_value=self.storage_location)


@with_register
@dataclass(frozen=False)
class MLOptions(OptionsBase):
    storage_location: str = field(default=None)
    test_fraction: int = field(default=0.15)
    val_fraction: int = field(default=0.15)
    num_topics: int = field(default=10),
    nr_passes: int = field(default=1)

    def get_storage_path(self, flow_id):
        return get_full_storage_path(flow_id, base_value=self.storage_location)

@with_register
@dataclass(frozen=False)
class ReportingOptions(OptionsBase):
    wc_base_location: str = field(default='')
    LDAvis_base_location: str = field(default='')

    def get_wc_base_path(self, flow_id):
        return get_full_storage_path(flow_id, base_value=self.wc_base_location)

    def get_LDAvis_base_path(self, flow_id):
        return get_full_storage_path(flow_id, base_value=self.LDAvis_base_location)

@with_register
@dataclass(frozen=False)
class DownloadOptions(OptionsBase):
    download_rate_delay: float = 2.0
    error_retry_delay: float = 400.0
    batch_count: int = field(default_factory=lambda: 1)
    max_dwnl_errors_per_batch: int = field(default=20)

@with_register
@dataclass(frozen=False)
class StepDescr:
    step: str = field(metadata=dict(validate=marshmallow.validate.OneOf([key for key in STEPS_DICT.keys() if not key == '#8'])
                                   )
                      )
    label: str = field(default_factory=lambda: str(uuid.uuid4()))

@with_register
@dataclass(frozen=False)
class StepSuccessReportBase(StepDescr):
    exit_code: int = field(default=0) # 0:successfull
    msg: str = field(default='')

@with_register
@dataclass(frozen=False)
class PageCountReport(StepSuccessReportBase):
    page_number_total: int = field(default=0)
    divisor: int = field(default=1)
    batch_id: int = field(default=0)

@with_register
@dataclass(frozen=False)
class SkipPageCountReport(PageCountReport):
    pass

@with_register
@dataclass(frozen=False)
class PageDownloadsSuccessReport(StepSuccessReportBase):
    nr_success: int = field(default=0)
    nr_failure: int = field(default=0)
    divisor: int = field(default=0)
    batch_id: int = field(default=0)

    @property
    def nr_total(self):
        return self.nr_success + self.nr_failure

    def extr_post_iterator(self, conn):
        qu = 'select post_id, ord_key, ml_tag from so_ana_doc_worker.page_meta_info ' \
             'where step=%(step)s ' \
             'and step_label=%(step_label)s ' \
             'and MOD(ord_key,%(divisor)s)=%(batch_id)s'

        res_cursor = conn.execute(qu, {'step': self.step,
                                       'step_label': self.label,
                                       'divisor': self.divisor,
                                       'batch_id': self.batch_id
                                       })

        for res_row in res_cursor:
            yield res_row

@with_register
@dataclass(frozen=False)
class SkipPageDownloadsSuccessReport(PageDownloadsSuccessReport):
	pass

@with_register
@dataclass(frozen=False)
class PostDownloadsSuccessReport(StepSuccessReportBase):
    nr_success: int = field(default=0)
    nr_failure: int = field(default=0)

    @property
    def nr_total(self):
        return self.nr_success + self.nr_failure

@with_register
@dataclass(frozen=False)
class SkipPostDownloadsSuccessReport(PostDownloadsSuccessReport):
	pass
	
@with_register
@dataclass(frozen=False)
class StepFinishedReport(StepSuccessReportBase):
    result: Any = field(default=None)

@dataclass(frozen=False)
class BatchResultBase(StepDescr):
    divisor: int = field(default=10)
    result_class_name: str = field(default=None)
    data_class_name: str = field(default=None)
    batch_id: int = field(default=0)

    def set_result_class_name(self, cls):
        self.result_class_name = cls.__name__

    def result_iterator(self, conn):
        qu = f'select post_id, ord_key, ml_tag from so_ana_management.post_results ' \
             'where step=%(step)s ' \
             'and step_label=%(step_label)s ' \
             'and result_class_name=%(result_class_name)s ' \
             'and MOD(ord_key,%(divisor)s)=%(batch_id)s ' \
             'and exit_code = 0'

        res_cursor = conn.execute(qu, {'step': self.step,
                                       'step_label': self.label,
                                       'result_class_name': self.result_class_name,
                                       'divisor': self.divisor,
                                       'batch_id': self.batch_id
                                       })

        for res_row in res_cursor:
            yield res_row

@with_register
@dataclass
class BatchResult(BatchResultBase):
    nr_success: int = field(default=0)
    nr_failure: int = field(default=0)

@with_register
@dataclass
class BatchResultDoc(BatchResultBase):
    file_keys: Dict[str, str] = field(default=None)
    base_path: str = field(default=None)

    @property
    def full_path_to_files(self):
        return {key: os.path.join(self.base_path, value) for key, value in self.file_keys.items()}


@with_register
@dataclass
class TransformStepSummaryReport(StepDescr):
    nr_success: int = field(default=0)
    nr_failure: int = field(default=0)
    exit_code: int = field(default=0)
    msg: str = field(default='')
    result_class_name_set: List[str] = field(default_factory=list)
    data_class_name_set: List[str] = field(default_factory=list)

    @property
    def total(self):
        return self.nr_failure + self.nr_success

    @classmethod
    def from_batch_result_list(cls, step_info, batchres_lst):
        nr_success = sum([item.nr_success for item in batchres_lst])
        nr_failure = sum([item.nr_failure for item in batchres_lst])
        exit_code = 0 if nr_failure == 0 else 1
        msg = '' if exit_code == 0 else f'{nr_failure} of {nr_failure+nr_success} tasks failed.'
        result_class_name_set=list(set([item.result_class_name for item in batchres_lst]))
        data_class_name_set=list(set([item.data_class_name for item in batchres_lst]))
        return cls(step=step_info.step,
                   label=step_info.label,
                   nr_success=nr_success,
                   nr_failure=nr_failure,
                   exit_code=exit_code,
                   msg=msg,
                   result_class_name_set=result_class_name_set,
                   data_class_name_set=data_class_name_set
                )

    def es_idx_iterator(self, es, ret_field_src_list = None, training_data_only=False):
        query = {'query': {'bool': {'filter': [ {'term': {'step': self.step}},
                                                {'term': {'step_label': self.label}}
                                                ]
                                    }
                            }
                }
        if training_data_only:
            query['query']['bool']['filter'].append({'term': {'ml_tag': 0}})
        if ret_field_src_list is not None:
            query['_source'] = ret_field_src_list

        resp = helpers.scan(
            client=es,
            index=','.join(['idx_' + item.lower() for item in self.data_class_name_set]),
            query=query,
            scroll='120m',
            size=1,
            clear_scroll=True
        )

        for i, es_data in enumerate(resp):
            yield i, es_data

    def pg_result_iterator(self, conn, training_data_only=False):
        qu = f'select step, step_label, post_id, ord_key, ml_tag from so_ana_management.post_results ' \
             'where step=%(step)s ' \
             'and step_label=%(step_label)s ' \
             'and result_class_name=%(result_class_name)s ' \
             'and exit_code = 0'
        param_lst = []
        if training_data_only:
            qu += ' and ml_tag = 0'
        for res_class_name in self.result_class_name_set:
            param_lst.append({  'step': self.step,
                                'step_label': self.label,
                                'result_class_name': res_class_name
                             }
                            )
        res_cursor = conn.execute(qu, param_lst)

        for res_row in res_cursor:
            yield res_row

@with_register
@dataclass
class ArtefactShort:
    step: str
    step_label: str
    artefact_key: str
    artefact_value: str


@with_register
@dataclass
class Artefact(ArtefactShort):
    modus: str
    flow_run_id: str
    timestamp: datetime
    task_name: str
    task_slug: str
    task_run_id: str
    map_index: int
    task_loop_count: int
    task_run_count: int
    thread: int = field(default_factory=threading.get_ident)
    process: int = field(default_factory=os.getpid)

    @classmethod
    def _part_default_values(cls):
        import prefect
        return dict(    modus= getattr(prefect.context, 'modus', 'test'),
                        flow_run_id=prefect.context.flow_run_id,
                        timestamp=datetime.now(),
                        task_name=prefect.context.task_name,
                        task_slug=prefect.context.task_slug,
                        task_run_id=prefect.context.task_run_id,
                        map_index=prefect.context.map_index,
                        task_loop_count=getattr(prefect.context, 'task_loop_count', None),
                        task_run_count=prefect.context.task_run_count)

    @classmethod
    def save_data(cls,
                  session,
                  serializer,
                  step: str,
                  step_label: str,
                  key: str,
                  value: Any):

        modified_value= json.loads(serializer.serialize(value))

        sav_data = cls( step=step,
                        step_label=step_label,
                        artefact_key=key,
                        artefact_value = modified_value,
                        **cls._part_default_values()
                       )
        session.add(sav_data)
        session.commit()

        return ArtefactShort(step=sav_data.step,
                             step_label = sav_data.step_label,
                             artefact_key = sav_data.artefact_key,
                             artefact_value = sav_data.artefact_value
                             )

    @classmethod
    def get_data(   cls,
                    session,
                    serializer,
                    step: str,
                    step_label: str,
                    key: str):
        obj = session.get(cls, {'step': step,
                                'step_label': step_label,
                                'artefact_key': key})

        return ArtefactShort(step=obj.step,
                             step_label = obj.step_label,
                             artefact_key = obj.artefact_key,
                             artefact_value = obj.artefact_value
                             )

    @classmethod
    def all_artefacts_by_step(cls,
                              session,
                              serializer,
                              step,
                              step_label):
        res = session.query(cls).filter_by(step=step, step_label=step_label).all()
        res = [ArtefactShort(step=item.step,
                             step_label = item.step_label,
                             artefact_key = item.artefact_key,
                             artefact_value = item.artefact_value
                             )
               for item in res]
        return res

@with_register
@dataclass(frozen=False)
class StepRequest(StepDescr):
    request_type: str = field(default=REQU_TYPE_LST[0], metadata=dict(    validate=marshmallow.validate.OneOf(REQU_TYPE_LST)
                                   )
                      )
    artefact_list: List[ArtefactShort] = field(default_factory=list)

    def set_artefacts_from_db(self, session, serializer):
        art_lst = Artefact.all_artefacts_by_step(   session=session,
                                                    serializer=serializer,
                                                    step= self.step,
                                                    step_label = self.label
                                              )
        self.artefact_list = art_lst



@with_register
@dataclass(frozen=False)
class FlowOptions:
    description: str
    stack_exchange_type: str
    topic: str
    download_opts: DownloadOptions = field(default_factory=lambda: DownloadOptions())
    pre_proc_opts: TokenizationOptions = field(default_factory=lambda: TokenizationOptions())
    vect_opts: VectorizationOptions = field(default_factory=lambda: VectorizationOptions())
    ml_opts: MLOptions = field(default_factory=lambda: MLOptions())
    rep_opts: ReportingOptions = field(default_factory=lambda: ReportingOptions())
    preproc_batch_count: int = field(default=10)
    use_step: StepDescr = field(default=None)

@with_register
@dataclass
class LocationKey:
    flow_run_id: str
    date: datetime
    task_slug: str
    map_index: int
    task_loop_count: int
    task_run_count: int

@with_register
@dataclass
class ExtendedKey(LocationKey):
    result_as_json: Any

@with_register
@dataclass
class FullResult(ExtendedKey):
    flow_name: str
    flow_run_name: str
    task_name: str
    task_full_name: str
    task_id: str
    task_run_id: str
    pid: int = field(default_factory=os.getpid)
    thread: int = field(default_factory=threading.get_ident)
    timestamp: datetime = field(default_factory=datetime.now)
    modus: str = field(default_factory=lambda: 'test')


@dataclass
class JobOverview:
    description: str
    flow_name: str
    flow_id: str
    flow_run_id: str
    flow_run_name: str
    stack_exchange_type: str
    topic: str
    download_opts: Any
    pre_proc_opts: Any
    vect_opts: Any
    ml_opts: Any
    rep_opts: Any
    use_step_step: str
    use_step_label: str
    started_at_timest: datetime
    finished_at_timst: datetime
    exit_code: int
    exit_msg: str
    modus: str
    result: List[Any]
    flow_opts: FlowOptions
    step_2_info: Dict[str, StepRequest]
    user_agent: str
    from_email: str


@dataclass
class JobStepOverview:
    flow_name: str
    flow_id: str
    flow_run_id: str
    flow_run_name: str
    step: str
    step_label: str
    placed_at_timest: datetime
    started_at_timest: datetime
    finished_at_timest: datetime
    result: Any
    exit_code: int
    exit_msg: str
    prev_step_lbls: List[str]
    modus: str = field(default='test')

@dataclass
class ResultBase:
    step: str
    step_label: str
    ord_key: int
    flow_run_id: str
    flow_run_name: str
    result_class_name: str
    exit_code: int
    exit_msg: str
    modus: str

@dataclass
class PageResult(ResultBase):
    page_nr: int

@dataclass
class PostResult(ResultBase):
    post_id: int
    ml_tag: int

@dataclass
class TopicDistribution:
    step: str
    step_label: str
    ord_key: int
    post_id: int
    for_step: str
    for_step_label: str
    topic_id: int
    topic_weight: float
    modus: str
    flow_run_id: str
    timestamp: datetime
    task_name: str
    task_slug: str
    task_run_id: str
    map_index: int
    task_loop_count: int
    task_run_count: int
    thread: int
    process: int

def get_proj_serializer():
    registry = so_ana_json.TypedJsonSerializer()
    for item in with_register._members.values():
        registry.register_schema(item)
    return registry

if __name__ == '__main__':
    config_dict = {'version': 1,
                   'formatters': {'std': {'format': '%(name)s: %(asctime)s - %(levelname)s - %(message)s'}

                                },
                   'handlers': {'console':
                                    {'class': 'logging.StreamHandler',
                                     'formatter': 'std'
                                     }
                                },
                   'root': {'level' : 'DEBUG',
                            'propagate': False,
                            'handlers': ['console']
                            }

                   }

    logging.config.dictConfig(config_dict)
    serializer = get_proj_serializer()
    print(serializer._registry)

    @dataclass
    class SampleClass:
        int_field: int
        str_field: str

    print(SampleClass.__dict__)

    for key, value in SampleClass.__dataclass_fields__.items():
        print(key, value, value.name)