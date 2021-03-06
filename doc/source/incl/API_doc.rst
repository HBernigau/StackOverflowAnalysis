API documentation
=================

Introduction
------------

The project consists of five top level modules, namely

- so_ana_analysis: containing the Jupyter notebooks for analysis
- so_ana_doc_worker: any code chunks related to processing documents
- so_ana_management: all tools for managing the overall flow
- so_ana_util: several utilities
- sqlalchemy_models containing the relational database models and related functionality

Moreover node that data base migrations are managed using
`alembic <https://alembic.sqlalchemy.org/en/latest/>`_ .

The migration code is placed in folder *alembic*

command line application so_ana.py
----------------------------------

.. automodule:: so_ana
   :members:
   :undoc-members:

package so_ana_doc_worker
-------------------------

contains submodules with code related to processing documents.

module so_ana_doc_worker.extr_post_deps
***************************************

.. automodule:: so_ana_doc_worker.extr_post_deps
   :members:
   :undoc-members:

module so_ana_doc_worker.extract_posts
**************************************

.. automodule:: so_ana_doc_worker.extract_posts
   :members:
   :undoc-members:

module so_ana_doc_worker.LDA
****************************

.. automodule:: so_ana_doc_worker.LDA
   :members:
   :undoc-members:

module so_ana_doc_worker.schemas
********************************

.. automodule:: so_ana_doc_worker.schemas
   :members:
   :undoc-members:

sub-module so_ana_doc_worker.so_ana_process_posts
*************************************************

.. automodule:: so_ana_doc_worker.so_ana_process_posts
   :members:
   :undoc-members:

module so_ana_doc_worker.so_ana_reporting
*****************************************

.. automodule:: so_ana_doc_worker.so_ana_reporting
   :members:
   :undoc-members:

package so_ana_management
-------------------------

Contains any code related to workflow management.

module so_ana_management.flow
*****************************

.. automodule:: so_ana_management.flow
   :members:
   :undoc-members:

sub-module so_ana_management.flow_services
******************************************

.. automodule:: so_ana_management.flow_services
   :members:
   :undoc-members:

module so_ana_management.management_deps
****************************************

.. automodule:: so_ana_management.management_deps
   :members:
   :undoc-members:

module so_ana_management.management_utils
*****************************************

.. automodule:: so_ana_management.management_utils
   :members:
   :undoc-members:

package so_ana_util
-------------------

Contains several utilities which are not directly related to any specific context.
On package level the modul provides some important directories:

- PROJ_ROOT_PATH is the root path for the project
- PROJ_DATA_PATH is the path to data
- PROJ_CONFIG_PATH is the path containing configurations
- PROJ_OUTP_PATH is the root for output data

Furthermore the function *get_main_config* loads the configuration file for the current run.

module so_ana_util.common_types
*******************************

.. automodule:: so_ana_util.common_types
   :members:
   :undoc-members:

module so_ana_util.data_access
******************************

.. automodule:: so_ana_util.data_access
   :members:
   :undoc-members:

module so_ana_util.error_handling
*********************************

.. automodule:: so_ana_util.error_handling
   :members:
   :undoc-members:

module so_ana_util.so_ana_json
******************************

.. automodule:: so_ana_util.so_ana_json
   :members:
   :undoc-members:

package so_ana_sqlalchemy_models
--------------------------------

Contains code related to data base access.

module so_ana_sqlalchemy_models.db_deps
***************************************

.. automodule:: so_ana_sqlalchemy_models.db_deps
   :members:
   :undoc-members:

module so_ana_sqlalchemy_models.model_base
******************************************

.. automodule:: so_ana_sqlalchemy_models.model_base
   :members:
   :undoc-members:

module so_ana_sqlalchemy_models.models
**************************************

.. automodule:: so_ana_sqlalchemy_models.models
   :members:
   :undoc-members:

module so_ana_sqlalchemy_models.table_defs
******************************************

.. automodule:: so_ana_sqlalchemy_models.table_defs
   :members:
   :undoc-members: