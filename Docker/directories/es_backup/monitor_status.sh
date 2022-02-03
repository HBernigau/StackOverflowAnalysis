#!/bin/sh
# startup actions for script "src/receive_hellow.py"
# wait until some-rabbit service has started 
curl -X GET "localhost:9200/_snapshot/std_backup/$SNAPSHOT_NAME?pretty"
curl -X GET "localhost:9200/_snapshot/std_backup/_current?pretty"

