#!/bin/sh
# startup actions for script "src/receive_hellow.py"
# wait until some-rabbit service has started 
pg_dump $POSTGRES_DB -U $POSTGRES_USER>data/backup