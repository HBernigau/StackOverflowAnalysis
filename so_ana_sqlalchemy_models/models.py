"""
contains sql alchemy models

Author: `HBernigau <https://github.com/HBernigau>`_
Date: 01.2022
"""

from sqlalchemy.orm import registry, relationship
from sqlalchemy import MetaData

import so_ana_doc_worker.schemas as doc_worker_schemas
import so_ana_management.management_utils as mng_util
import so_ana_util.common_types as so_ana_common_types
from so_ana_sqlalchemy_models.table_defs import tbl_specs


# mapping the tables
metadata = MetaData()
mapper_registry = registry(metadata=metadata)


tbl_specs['so_ana_management'].bind(mapper_registry=mapper_registry,
                                    data_class=mng_util.Artefact,
                                    tbl_name='artefacts')

tbl_specs['so_ana_doc_worker'].bind(mapper_registry=mapper_registry,
                                    data_class=doc_worker_schemas.PostMetaData,
                                    tbl_name='page_meta_info')
tbl_specs['so_ana_management'].bind(mapper_registry=mapper_registry,
                                    data_class=mng_util.FullResult,
                                    tbl_name='task_results')
tbl_specs['so_ana_management'].bind(mapper_registry=mapper_registry,
                                    data_class=mng_util.JobOverview,
                                    tbl_name='job_overview')
tbl_specs['so_ana_management'].bind(mapper_registry=mapper_registry,
                                    data_class=mng_util.JobStepOverview,
                                    tbl_name='steps_overview')

tbl_specs['so_ana_management'].bind(mapper_registry=mapper_registry,
                                    data_class=mng_util.PageResult,
                                    tbl_name='page_results')

tbl_specs['so_ana_management'].bind(mapper_registry=mapper_registry,
                                    data_class=mng_util.PostResult,
                                    tbl_name='post_results')

tbl_specs['so_ana_logging'].bind(mapper_registry=mapper_registry,
                                 data_class=so_ana_common_types.LogEntry,
                                 tbl_name='prefect_logs')

tbl_specs['so_ana_analysis'].bind(mapper_registry=mapper_registry,
                                  data_class=mng_util.TopicDistribution,
                                  tbl_name='topic_distribution')



if __name__ == '__main__':
    # deps_container = prod_db_container()
    # session = deps_container.session
    for bnd_cntx_id, cntx_tbl_spec in tbl_specs.items():
        print(f'Tables for "{bnd_cntx_id}"')
        for tbl in cntx_tbl_spec.build_tables:
            print(tbl)
        print()