#!/bin/sh
curl -X PUT "localhost:9200/_snapshot/std_backup?pretty" -H 'Content-Type: application/json' -d'
{
  "type": "fs",
  "settings": {
    "location": "/es_backup/data",
    "compress": true
  }
}
'
curl -X PUT "localhost:9200/_snapshot/std_backup/$SNAPSHOT_NAME?wait_for_completion=true&pretty"



