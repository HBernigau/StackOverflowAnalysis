"""
Defines table registry to be used in "table_defs"

Author: `HBernigau <https://github.com/HBernigau>`_
Date: 01.20222
"""


from sqlalchemy import Table
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any

@dataclass
class TblSpec:
    """
    Wrapper for table specification data
    """
    args: List[Any] = field(default_factory=lambda: [])
    kwargs: Dict[str, any] = field(default_factory=lambda: {})

class MappingArgs(TblSpec):
    """
    Mapping arguments
    """
    pass

class TableRegistry:
    """
    Table registry (later on one registry per bounded context will be used)
    """

    def __init__(self, schema_name = None):
        self.schema_name = schema_name # schema name
        self.tbl_spec_data = {} #table specification data
        self.mapping_param_data = {}    # additional mapping parameters -> .bind
        self.build_tables = {}  # tables actually built -> .bind
        self.tbl2dataclass = {} # mapping table to mapped data class -> .bind
        self.last_registry = None # last registry used -> .bind

    def __setitem__(self, tbl_name: str, tbl_spec: TblSpec):
        """
        Sets table specification
        :param tbl_name: name of the table
        :param tbl_spec: Table specification to be used for imperative style mapping in sql alchemy
        (compare: https://docs.sqlalchemy.org/en/14/orm/mapping_styles.html#orm-imperative-mapping)

        :return: None
        """
        self.tbl_spec_data[tbl_name] = tbl_spec

    def __getitem__(self, tbl_name):
        """
        Table specification by table name
        :param tbl_name: name of the table to be mapped
        :return: table specification
        """
        return self.tbl_spec_data[tbl_name]

    def bind(self, mapper_registry, data_class, tbl_name, *args, **kwargs):
        """
        Binds a data class to an sql alchemy table
        :param mapper_registry: sql alchemy registry (from sqlalchemy.orm import registry)
        :param data_class: data class to be mapped, attributes need to coincide with table column names
        :param tbl_name: table name the data class is mapped to
        :param args: additional args for mapper_registry.map_imperatively
        :param kwargs:  additional kwargs for mapper_registry.map_imperatively
        :return: None
        """
        self.tbl2dataclass[tbl_name] = data_class
        self.mapping_param_data[tbl_name] = MappingArgs(args=args, kwargs=kwargs)

        if tbl_name not in self.build_tables.keys():
            tbl_args = self[tbl_name].args
            tbl_kwargs = self[tbl_name].kwargs
            tbl_kwargs['schema'] = self.schema_name
            tbl = Table(tbl_name, mapper_registry.metadata, *tbl_args, **tbl_kwargs)
            self.build_tables[tbl_name] = tbl

            mapper_registry.map_imperatively(data_class, tbl, *args, **kwargs)

        self.last_registry = mapper_registry