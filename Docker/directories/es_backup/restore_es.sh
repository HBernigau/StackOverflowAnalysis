#!/bin/sh
# startup actions for script "src/receive_hellow.py"
# wait until some-rabbit service has started 
curl -X POST "localhost:9200/sample_index/_close?pretty"
# curl -X DELETE "localhost:9200/sample_index"
curl -X POST "localhost:9200/_snapshot/std_backup/$SNAPSHOT_NAME/_restore?pretty" -H 'Content-Type: application/json' -d'
{
  "indices": "sample_index"
}
'

