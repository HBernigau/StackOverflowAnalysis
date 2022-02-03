How to run stack overflow analysis
==================================

Get the repository
------------------

As a first step clone the repository:

.. code-block:: bat

   cd <put-your-target-folder-here>
   git clone https://github.com/HBernigau/StackOverflowAnalysis.git

Build the virtual environment
-----------------------------

The application has been tested using *Python 3.8.6* on a
Windows computer with *Windows 10 Enterprise*.

If you want to use the same Python version, we recommend
using `pyenv <https://github.com/pyenv/pyenv>`_ which allows
management of multiple Python versions on the same machine.

For dependency management the current application uses
`pip-tools <https://github.com/jazzband/pip-tools>`_ ,
which can be considered as a best-practice for dependency
management in Python. In order to use it, install it using pip:

.. code-block:: bat

   python -m pip install pip-tools

.. note::
   when writing this guide, there was
   an issue regarding compatibility of pip and
   pip-utils, which can be fixed by using a pip version
   bellow 22.0 (see `issue 1558 on pip-tools on Github <https://github.com/jazzband/pip-tools/issues/1558>`_ ).

Now change to the applications root folder and
build the virtual environment by calling

.. code-block:: bat

   build_full.bat

If you want to re-generate the requirements file
from first order dependencies (i.e. using the latest
available library version) call

.. code-block:: bat

   compile_full.bat

before calling the build script.

Start Docker containers
-----------------------

The application uses a `PostgreSQL <https://www.postgresql.org/>`_ data base and an
`elastic search <https://www.elastic.co/de/elasticsearch/>`_
data base as backends which ar run in Docker containers.

Hence, the application requires installation of
`Docker Desktop <https://www.docker.com/products/docker-desktop>`_ .

In order to run the application some environment variables
must be set. This can best be done by copying the *.env*
file from *templates* folder into the root folder and set the
variable *PGADMIN_DEFAULT_EMAIL* to some email address that
is then used as login information for
`PGAdmin <https://www.pgadmin.org/>`_ , a management tool for
postgresql data bases.

.. note::
   you can also change other environment variables,
   like the password for postgreSQL or various ports.
   The latter might be necessary, if you should encounter
   any port conflicts for example.

If you want to change the data base connection information in the *.env* file,
please read the following note:

.. note::

   If you alter postgreSQL connection data, please note the following:

   One of the Docker containers connects to the
   postgreSQL data base and builds the latest version
   of the application's data base using `alembic <https://alembic.sqlalchemy.org/en/latest/>`_ .
   In order to make that work, please also adjust the database
   urls in *./alembic/alembic.ini*, line 38 and in
   *./alembic/alembic_docker.ini*, line 38 (as the names suggest,
   *alembic_docker.ini* is the connection data from within Docker).

   Secondly the pgAdmin container requires valid connection
   data as well. Therefore, please adjust the settings in
   *Docker/directories/pgadmin_config_data/servers.json*

   Last but not least the application itself requires valid
   connection strings as well, which can be adjusted in
   *./data/config/so_ana_config.yaml* under db_opts -> postgres.

   If you changed elastic search connection data,
   please adjust the application's connection data in
   *./data/config/so_ana_config.yaml* under db_opts -> elastic_search.

in order to start all Docker containers type the following in
cmd:

.. code-block:: bat

   launch_docker_containers.bat

Start Prefect
-------------

The application uses `Prefect <https://www.prefect.io/>`_
for workflow management, and the individual tasks are
run in a `dask-cluster <https://dask.org/>`_ .

In order to run the cluster do the following:

1. Start dask:

.. code-block:: bat

   launch_dask.bat

2. Start the prefect server:

.. code-block:: bat

   launch_prefect_server.bat

3. Start the prefect client:

   launch_prefect_client.bat

Now you can use the command line application, *so_ana.py*,
to interact with the server. In order to see all
available commands, call:

.. code-block:: bat

   python so_ana.py --help

.. note::

   When configured as described above, prefect does not persist run-time information,
   i.e. prefect server looses any information about previous runs.

   Even though prefect in principle allows providing a storage location for
   its postgreSQL backend, this is not very help-full under windows, as
   assigning windows drives conflicts with Linux user-permission in Windows.

   As a work-around you can use Docker managed drives. In order to do that,
   the file *./venv/Lib/site-packages/cli/docker-compose.yml* has to be
   modified. In order to see an example, please open the file
   *./templates/.docker-compose_prefect.yml*.
   The essential modifications are in:

   - Line 18: mapping the docker-managed drive "prefect_postgresdata_so_analysis" to */var/lib/postgresql/data*
   - Line 19: mapping the back-up folder to */pg_backup/* / this is relevant
     if you want to back-up the prefect data base / otherhwise you can skip these lines
   - Line 147-148: defining the docker-managed drive *prefect_postgresdata_so_analysis*

Run your first sample workflow
------------------------------

Generally, flow configurations are stored in *./data/config*.
The most straight-forward way to run the sample configuration
*adm_smpl.yaml*, is using the command line utility, *so_ana.py*:

.. code-block:: bat

   activate_venv.bat
   python so_ana.py run --test adm_smpl.yaml python so_ana.py run --test adm_smpl.yaml Holger.Bernigau@gmx.de "Software Engineering Research@University of St.Gallen"

This command executes the flow with configuration *adm_smpl.yaml* in test modus.
For all requests to stack-overflow, the user provides some credentials within
the request headers (from_email="Holger.Bernigau@gmx.de" / user_agent="Software Engineering Research@University of St.Gallen").
This is in line with `ethical best-practices for web-scrapping <https://towardsdatascience.com/ethics-in-web-scraping-b96b18136f01>`_ .

A more convenient way to execute the flow, is submitting it to prefect server.
This can be done by calling the following command:

.. code-block:: bat

   python so_ana.py register

before running the script, you should clear all previous data
(as the step names to be provided in the sample configuration are supposed to be unique).

.. code-block:: bat

   python so_ana.py clear-db-data --test

Then enter "localhost:8080" in your favorite Browser to open prefect server's UI.
Change into Flows and select "so-analysis"

.. image:: img/cover_prefect_UI.png

Select the "Run" button and enter the flow parameters:

.. image:: img/run_prefect_UI_001.png

In order to enable a test-run, open the *advanced run configurations*

.. image:: img/run_prefect_UI_002.png

and enter modus test:

.. image:: img/run_prefect_UI_003.png

After clicking the *run button*, a dashboard appears
showing the run-time information of the flow.
