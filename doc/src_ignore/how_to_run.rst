How to run stack overflow analysis
==================================


Alembic
-------

alembic.ini
line 38: sqlalchemy.url = postgresql://admin:admin@localhost:5437/SO_ANA

alembic_docker.ini
line 38: sqlalchemy.url = postgresql://admin:admin@so_ana_postgres:5432/SO_ANA

data folder
-----------

Docker directories?
-------------------

DB configuration
----------------
db_deps.py
.env file

HOST_PG_PORT=5437
RMQ_USER=admin
RMQ_PW=admin
PG_DB=SO_ANA
PG_USER=admin
PG_PW=admin
PGADMIN_DEFAULT_EMAIL=Holger.Bernigau@gmx.de
PGADMIN_PW=admin
HOST_PGADMIN_PORT=5000
HOST_ES_PORT=9200
HOST_KIBANA_PORT=5601
ENV_HOME=/home/jovyan

extr_post_deps.py
-----------------

Z. 200 default values...



stubs folder raus

venv raus
---------

1.) Code runterladen
2.) 


add intro to each file
----------------------

flow_congigs.py
---------------

user_agent, from_email, [...]

management_deps
---------------
Dask

pip-tools
---------
https://github.com/jazzband/pip-tools

new environment
---------------

pyenv exec pip install pip-tools

pyenv
-----
pyenv local <version, 3.8.6>

pyenv exec python -m venv venv

.\venv\Lib\site-packages\prefect\cli\docker-compose.yml



volumes:
  prefect_postgresdata_so_analysis: