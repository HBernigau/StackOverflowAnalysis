#!/bin/sh
# startup actions for script "src/receive_hellow.py"
# wait until some-rabbit service has started 
nc -z so_ana_postgres 5432
CON_STAT=$?
while [ $CON_STAT != 0 ]
do
	sleep 2
	nc -z so_ana_postgres 5432
	CON_STAT=$?
	echo "Connection status to so_ana_postgres 5432: $CON_STAT"
done
nc -z so_ana_elastic_search 9200
CON_STAT=$?
while [ $CON_STAT != 0 ]
do
	sleep 2
	nc -z so_ana_elastic_search 9200
	CON_STAT=$?
	echo "Connection status to so_ana_elastic_search 9200: $CON_STAT"
done

cd /python/alembic
alembic -c alembic_docker.ini upgrade head