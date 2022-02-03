"""
contains several global data classes (for log entries for example)

Author: `HBernigau <https://github.com/HBernigau>`_
Date: 01.2022
"""

import marshmallow_dataclass as mmdc
import marshmallow
from logging import StreamHandler
from typing import Any
from dataclasses import is_dataclass, dataclass, field
from datetime import datetime
import uuid
import warnings
import time
import logging
import os
import threading

UUID = mmdc.NewType("UUID", str, field=marshmallow.fields.UUID)

@dataclass
class LogEntry:
    name: str
    flow_run_id: str
    task_name: str
    task_slug: str
    task_run_id: str
    map_index: int
    task_loop_count: int
    task_run_count: int
    thread: str
    threadName: str
    process: int
    processName: str
    exc_text: str
    levelname: str
    msg: str
    timestamp: datetime = field(default_factory=datetime.now)
    msg_uuid: UUID = field(default_factory=uuid.uuid4)
    modus: str = field(default_factory=lambda:'test')

def fill_dc_from_obj(DC, obj: Any, add_dict: dict = None, excl_lst = None, get_default = None, None_2_default = True):
    """
    Creates data class from fields in obj
    :param DC: Any data class
    :param obj: obj that contains values for parameters of data class (dictionary or object)
    :param add_dict: additional parameter values (will overwrite values of obj. if present)
    :param  excl_lst: list with field names for fields of CD that should not be filled
    :return: instance of DC with values of obj and add_dict
    """
    def h1(obj, key, default = None):
        if isinstance(obj, dict):
            ret = obj.get(key, default)
        else:
            try:
                ret = getattr(obj, key, default)
            except:
                raise ValueError(f'"get_item" not implemented for type="{type(obj)}"')

        if None_2_default and ret is None:
            return default
        else:
            return ret

    if add_dict is None:
        add_dict = {}
    if excl_lst is None:
        excl_lst = []
    if get_default is None:
        get_default=lambda x: None

    if not is_dataclass(DC) and type(DC) is type:
        raise ValueError(f'"DC" must be a valid dataclass.')

    rel_val_dict = {key: h1(obj, key, get_default(key)) for key, value in DC.__dataclass_fields__.items() if not key in excl_lst}
    rel_val_dict.update(add_dict)
    return DC(**rel_val_dict)

def flatten_ls(ls, base=None):
    if base is None:
        base = []
    if not (isinstance(ls, list)):
        return base + [ls]
    else:
        for item in ls:
            base += flatten_ls(item)
        return base

def get_null_logger():
    fb_null_logger = logging.getLogger('downloader logger')
    fb_null_logger.setLevel(logging.DEBUG)
    fb_null_logger.addHandler(logging.NullHandler())
    return fb_null_logger

class TstHandler(StreamHandler):

    def __init__(self):
        self.reset_loglist()
        super().__init__()


    def reset_loglist(self):
        self._log_list = []

    @property
    def log_list(self):
        return self._log_list

    def emit(self, record):
        msg = self.format(record)
        self._log_list.append({'formated_log_msg': msg, **record.__dict__})


class CustomLogHandler(StreamHandler):
    """Stores prefect logs in the project's postgresql data base"""

    def __init__(self, get_session, modus, *args, **kwargs):
        self.get_session=get_session
        self.modus=modus
        super().__init__(*args, **kwargs)

    def emit(self, record):
        resp = fill_dc_from_obj(DC=LogEntry,
                                obj=record,
                                excl_lst = ['timestamp', 'msg_uuid'],
                                add_dict={'modus': self.modus})

        default_dict = {'thread': threading.get_ident(),
                        'threadName': threading.current_thread().name,
                        'process': os.getpid()
                        }

        for attr, attr_def_value in default_dict.items():
            if getattr(resp, attr, None) is None:
                setattr(resp, attr, attr_def_value)
        if not isinstance(resp.msg, str):
            resp.msg = str(resp.msg)[:4094]
        else:
            resp.msg=resp.msg[:4094]
        for i in range(2):
            try:
                session = self.get_session()
                session.add(resp)
                session.commit()
                # session.close() # can be omitted now...
                break
            except Exception as exc:
                warnings.warn(f'Error when logging: "{exc}" (trial {i+1}/3)')
                time.sleep(1.0)
        else:
            warnings.warn(f'Final result: Could not log record {record}')

def get_tst_logger(tst_handler):
    smpl_logger = logging.Logger('tst_logger', level = logging.INFO)
    for hndl in smpl_logger.handlers:
        if type(hndl) is type(tst_handler):
            break
    else:
        smpl_logger.addHandler(tst_handler)
    return smpl_logger

def get_prod_logger(name, get_session, cust_formatting = None, modus='test'):
    logger = logging.Logger(name, level = logging.INFO)
    if cust_formatting is None:
        cust_formatting = '[%(asctime)s] %(levelname)s - %(name)s | %(message)s'
    for req_hndl in [StreamHandler(), CustomLogHandler(get_session, modus=modus)]:
        #for hndl in logger.handlers:
        #    logger.removeHandler(hndl)
        for hndl in logger.handlers:
            if type(hndl) is type(req_hndl):
                break
        else:
            formatter = logging.Formatter(cust_formatting)
            req_hndl.setFormatter(formatter)
            logger.addHandler(req_hndl)
    return logger



