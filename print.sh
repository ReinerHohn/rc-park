#!/bin/bash
# Schnell auf Prusa MK4S drucken: ./print.sh datei.gcode
FILE="$1"
NAME=$(basename "$FILE")
curl -s --digest -u "maker:eNU6xZJ95V9tJxQ" \
  -X PUT -H "Content-Type: application/octet-stream" -H "Overwrite: ?1" \
  --data-binary @"$FILE" \
  "http://192.168.178.55/api/v1/files/usb/$NAME" | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK:', d['name'])"
SHORT=$(curl -s --digest -u "maker:eNU6xZJ95V9tJxQ" \
  "http://192.168.178.55/api/v1/files/usb" | python3 -c "
import sys,json
d=json.load(sys.stdin)
name='$NAME'.lower().replace('.gcode','')
for f in d.get('children',[]):
    if name[:4].lower() in f['name'].lower():
        print(f['name']); break
")
curl -s -w "Start: HTTP %{http_code}\n" --digest -u "maker:eNU6xZJ95V9tJxQ" \
  -X POST "http://192.168.178.55/api/v1/files/usb/$SHORT"
