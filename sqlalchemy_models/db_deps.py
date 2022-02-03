"""
contains dependencies for data base access

Author: `HBernigau <https://github.com/HBernigau>`_
Date: 01.2022
"""

from dependency_injector import containers, providers
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from elasticsearch import Elasticsearch
from dataclasses import dataclass, is_dataclass, asdict
from elasticsearch.serializer import JSONSerializer
import marshmallow_dataclass as mmdc
from typing import List
from datetime import datetime, date
import so_ana_util.common_types as common_types
import sqlalchemy_models.models as sqamod
import inspect
from dotted_dict import DottedDict
import time
import logging
import typing
import os
import threading

from so_ana_util.common_types import get_prod_logger
import so_ana_util.common_types as so_ana_common_types



class CreateEngine:

    _engine_dict = {}

    def __call__(self,
                 db_conn_str,
                 application_name,
                 pool_size =5,
                 max_overflow = 0
                 ):
        if not (application_name in CreateEngine._engine_dict.keys()):
            appl_name = f'{application_name} (pid={os.getpid()}, thread={threading.get_ident()})'
            CreateEngine._engine_dict[application_name]=create_engine(  db_conn_str,
                                                                        pool_size=pool_size,
                                                                        max_overflow=max_overflow,
                                                                        connect_args={'application_name': appl_name}
                                                                )
        return CreateEngine._engine_dict[application_name]

cust_create_engine = CreateEngine()


def dict_to_es_key(key_dict):
    sort_keys = sorted(key_dict.keys())
    return ';'.join([f'{key}:{key_dict[key]}' for key in sort_keys])


class DCEncoder(JSONSerializer):

    def loads(self, s):
        return super().loads(s)

    def dumps(self, s):
        if is_dataclass(s):
            schema = mmdc.class_schema(type(s))()
            ret = schema.dumps(s)
            return schema.dumps(s)
        else:
            res = super().dumps(s)
            return res

def provide_dc_type(pot_DC):
    if is_dataclass(pot_DC):
        return pot_DC, 'nested'
    elif isinstance(pot_DC, typing._GenericAlias):
        arg0 = getattr(pot_DC, '__args__', [None])[0]
        if is_dataclass(arg0):
            return arg0, 'nested'
        elif arg0 is datetime:
            return arg0, 'date'
        elif arg0 is date:
            return arg0, 'date'
        else:
            return None, None
    else:
        return None


class DC2ES:

    def __init__(self, es):
        self.index_cache = set()
        self.type_transl = [ (common_types.UUID, 'text'),
                    (str, 'text'),
                    (int, 'integer'),
                    (float,'double'),
                    (bool, 'boolean'),
                    (datetime, 'date'),
                    (date, 'date'),
                    (List[str], 'text'),
                    (List[int], 'integer'),
                    (List[float], 'double'),
                    (List[bool], 'boolean'),
                    (List[date], 'date'),
                    (List[datetime], 'date')
                    ]
        self.fb_val = 'text'
        self.es=es

    @property
    def _std_settings(self):
        settings = {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0
            },
            "mappings": {
                "dynamic": "strict",
                "properties": {}
            }
        }
        return settings

    def properties(self, dc):
        prop_dict = {}
        for field_name, field_obj in dc.__dataclass_fields__.items():
            for src_type, tar_type in self.type_transl:
                if field_obj.type is src_type:
                    prop_dict[field_name] = {'type': tar_type}
                    if tar_type=='text':
                        prop_dict[field_name]['analyzer']='whitespace'
                    break
            else:
                inner_type, field_type = provide_dc_type(field_obj.type)
                prop_dict[field_name] = {'type': field_type or self.fb_val}
                if field_type=='nested':
                    prop_dict[field_name]['properties']=self.properties(inner_type)
        return prop_dict

    def get_std_settings(self, dc):
        props=self.properties(dc)
        settings = self._std_settings
        settings['mappings']['properties']=props
        return settings

    def create_index(self, index_name: str, dc):
        settings = self.get_std_settings(dc)
        res = self.es.indices.create(index=index_name, ignore=400, body=settings)
        if res.get('acknowledged', False) is True:
            self.index_cache.add(index_name)
        else:
            pass

    def _index_name(self, dc):
        if inspect.isclass(dc):
            part = dc.__name__.lower()
        else:
            part = type(dc).__name__.lower()
        return 'idx_' + part

    def create_indx_ifnex(self, dc):
        idx_name=self._index_name(dc)
        if not idx_name in self.index_cache:
            if not self.es.indices.exists(idx_name):
                self.create_index(idx_name, dc)

    def __call__(self, id, data):
        """stores data class in elastic search cluster"""
        if not is_dataclass(data):
            raise NotImplementedError(f'Method requires a data class as input.')
        else:
            self.create_indx_ifnex(data)
        res = self.es.index(index=self._index_name(data), id=id, body=asdict(data))
        return res

    def _error_on_not_dataclass(self,DC):
        if not (is_dataclass(DC) and inspect.isclass(DC)):
            raise NotImplementedError(f'Method requires a data class as input.')

    def get(self, DC, key):
        """receives elements by key ands stores in data class"""
        self._error_on_not_dataclass(DC)
        idx_name = self._index_name(DC)
        res_plain = DottedDict(self.es.get(idx_name, id=key)['_source'])
        res = so_ana_common_types.fill_dc_from_obj(DC,res_plain)
        return res

    def delete(self, DC, key):
        self._error_on_not_dataclass(DC)
        idx_name = self._index_name(DC)
        res = self.es.delete(index=idx_name, doc_type='_doc', id=key)
        return res

    def delete_by_query(self, DC, query_dict):
        """
        Deletes documents that matches a given query
        :param DC:
        :param query_dict: compare https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl.html
        and https://elasticsearch-dsl.readthedocs.io/en/latest/
        :return:
        """
        if DC is None:
            idx_name = '_all'
        elif isinstance(DC, list):
            for item in DC:
                self._error_on_not_dataclass(item)
            idx_name = ','.join([self._index_name(item) for item in DC])
        elif isinstance(DC, str):
            idx_name = DC
        else:
            self._error_on_not_dataclass(DC)
            idx_name = self._index_name(DC)
        res = self.es.delete_by_query(index=idx_name, body=query_dict)
        return res

    def search(self, DC, query_dict):
        """
        Deletes documents that matches a given query
        :param DC:
        :param query_dict: compare https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl.html
        and https://elasticsearch-dsl.readthedocs.io/en/latest/
        :return:
        """
        tr_dict = {}
        do_parse = False
        if isinstance(DC, list):
            for item in DC:
                self._error_on_not_dataclass(item)
                tr_dict[self._index_name(item)]=item
            idx_name = ','.join([self._index_name(item) for item in DC])
            do_parse = True
        elif isinstance(DC, str):
            idx_name = DC
        else:
            self._error_on_not_dataclass(DC)
            idx_name = self._index_name(DC)
            tr_dict[idx_name] = DC
            do_parse = True
        res_raw = self.es.search(index=idx_name, body=query_dict)
        res = [DottedDict(item) for item in res_raw['hits']['hits']]
        if do_parse:
            res = [so_ana_common_types.fill_dc_from_obj(tr_dict[item['_index']], item['_source']) for item in res]
        return res_raw, res

class CreateSessionFactory:

    def __init__(self, bind):
        CreateSessionFactory.bind = bind
        session_factory = sessionmaker(bind=bind, future=True)
        CreateSessionFactory.Session = scoped_session(session_factory)

    def __call__(self):
        return CreateSessionFactory.Session()

def get_es(address, serializer):
    es = Elasticsearch(address, serializer=serializer, timeout=30, max_retries=10, retry_on_timeout=True)
    return es

@dataclass(frozen=True)
class DBAccResult:
    exit_code: int
    msg: str

def save2es(d2es, key_dict, data, logger):
    key = dict_to_es_key(key_dict)
    ex_res = d2es(key, data)
    if not ex_res['result'] == 'created':
        res_value = ex_res['result']
        logger.error(f'could not write data for key "{key}" to elastic search data base, result is "{res_value}".')
    else:
        logger.info(f'data for {key} written to es.')



class SaveTDB:

    def __init__(self, d2es, get_session, logger, enable_sql_alchemy_logging=False):
        self.d2es = d2es
        self.get_session = get_session
        self.session=get_session()
        self.logger=logger
        if enable_sql_alchemy_logging:
            logging.basicConfig(format='[%(asctime)s] %(levelname)s - %(name)s | %(message)s')
            logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    def _session_add(self, value):
        for i in range(2):
            try:
                self.session.add(value)
                return DBAccResult(0,'')
            except Exception as exc:
                self.logger.error(f'error in trial {i+1}/3 : {exc} - trying again in 1s...')
                self.session = self.get_session()
                msg = str(exc)
                time.sleep(1.0)
        else:
            RuntimeError(msg)

    def _session_get(self, DC, key_dict):
        for i in range(2):
            try:
                return DBAccResult(0,''), self.session.get(DC, key_dict)
            except Exception as exc:
                self.logger.error(f'error in trial {i+1}/3 : {exc} - trying again in 1s...')
                msg = str(exc)
                time.sleep(1.0)
        else:
            raise RuntimeError(msg)

    def __call__(self, data, key_lst, to_pg = False, to_es = False):
        key_dict = {key: getattr(data, key) for key in key_lst}
        if to_pg:
            if key_dict is not None:
                old_val = None
                res, old_val = self._session_get(type(data), key_dict)
                if old_val is None:
                    res = self._session_add(data)
                else:
                    for item in asdict(old_val).keys():
                        setattr(old_val, item, getattr(data, item))
            else:
                res = self._session_add(data)

            self.session.commit()
            if res.exit_code > 0:
                self.logger.error(f'Could not add  data with keys "{key_dict}" to pg session, msg: "{res.msg}"')
            else:
                self.logger.info(f'data for {key_dict} written to pg.')

        if to_es:
            key = dict_to_es_key(key_dict)
            ex_res = self.d2es(key, data)
            if not ex_res['result'] == 'created':
                res_value = ex_res['result']
                msg = f'could not write data for key "{key}" to elastic search data base, result is "{res_value}".'
                self.logger.error(msg)
                raise RuntimeError(msg)
            else:
                self.logger.info(f'data for {key} written to es.')

def pg_url_from_parts(user_name, pw, server_name, port, db_name):
    s = r'/'
    return f'postgresql:{s+s}{user_name}:{pw}@{server_name}:{port}{s}{db_name}'

def es_url_from_parts(server_name, port):
    return f'{server_name}:{port}'

class DBDeps(containers.DeclarativeContainer):

    config = providers.Configuration()

    pg_conn_str = providers.Factory(pg_url_from_parts,
                                    user_name=config.user_name,
                                    pw=config.pw,
                                    server_name=config.server_name,
                                    port=config.port,
                                    db_name=config.db_name
                                    )

    es_conn_str =  providers.Factory(   es_url_from_parts,
                                        server_name=config.es_server_name,
                                        port=config.es_port,
                                    )

    engine = providers.Singleton(   cust_create_engine,
                                    application_name=config.app_conn_name,
                                    db_conn_str=pg_conn_str
                                    )

    logging_engine=providers.Singleton( cust_create_engine,
                                        application_name=config.log_conn_name,
                                        db_conn_str=pg_conn_str
                                        )

    get_session = providers.Singleton(  CreateSessionFactory,
                                        bind=engine)

    get_logging_session = providers.Singleton(  CreateSessionFactory,
                                                bind=logging_engine)

    es=providers.Factory(get_es,
                         address=es_conn_str,
                         serializer=DCEncoder())

    d2es=providers.Factory(DC2ES,
                           es=es)

    db_logger = providers.Factory(  get_prod_logger,
                                    name=config.db_logger_name,
                                    get_session=get_logging_session,
                                    modus=config.modus)

    script_logger = providers.Factory(  get_prod_logger,
                                        name=config.script_logger_name,
                                        get_session=get_logging_session,
                                        modus=config.modus)


    save_to_db = providers.Factory(SaveTDB,
                                   d2es=d2es,
                                   get_session=get_session,
                                   logger=db_logger,
                                   enable_sql_alchemy_logging=False
                         )

    tbl_specs=providers.Singleton(lambda: sqamod.tbl_specs)


class LazyProviderAccessObject:

    def __init__(self, provider):
        self.provider = provider

    def __getattr__(self, value):
        if not value in self.__dict__.keys():
            new_val = getattr(self.provider, value)()
            setattr(self, value, new_val)
            return new_val

db_deps = DBDeps()

def prod_db_deps_container(user_name: str='admin',
                           pw: str = 'admin',
                           server_name: str = 'localhost',
                           port: int = 5437,
                           db_name: str = 'SO_ANA',
                           es_server_name: str = 'localhost',
                           es_port: int = 9200,
                           app_conn_name: str = 'so_ana_app',
                           log_conn_name: str = 'so_ana_log',
                           db_logger_name: str = 'default.db',
                           script_logger_name: str = 'default.db',
                           modus: str = 'test'):
    lazy_access_ob = LazyProviderAccessObject(db_deps)
    lazy_access_ob.provider.config.from_dict({ 'user_name': user_name,
                                               'pw': pw,
                                               'server_name': server_name,
                                               'port': port,
                                               'db_name': db_name,
                                               'es_server_name': es_server_name,
                                               'es_port': es_port,
                                               'app_conn_name': app_conn_name,
                                               'log_conn_name': log_conn_name,
                                               'db_logger_name': db_logger_name,
                                               'script_logger_name': script_logger_name,
                                               'modus': modus
                                                }
                                             )
    lazy_access_ob.session = lazy_access_ob.get_session()
    lazy_access_ob.conn = lazy_access_ob.engine.connect()
    return lazy_access_ob

if __name__ == '__main__':
    sample_obj = prod_db_deps_container()
    print(sample_obj.pg_conn_str)
    #cont = DBDeps()
    #cont.config.from_dict({'user_name':'admin',
   #                       'pw': 'admin',
    #                       'server_name': 'localhost',
   #                        'port' : 5437,
  #                         'db_name' : 'SO_ANA',
   #                        'es_server_name':'localhost',
  #                         'es_port': 9200,
  #                         'app_conn_name': 'so_ana_app',
  #                         'log_conn_name': 'so_ana_log',
  #                         'db_logger_name':'default.db',
  #                         'script_logger_name':'default.db'})
#
    #pg_conn_str = cont.pg_conn_str()
    #print(pg_conn_str)