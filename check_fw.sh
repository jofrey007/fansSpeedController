#!/bin/bash
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  curl -k -s -u Administrator:7P7G6HP8 "https://10.31.0.10/redfish/v1/UpdateService/FirmwareInventory/$i/" 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    name = data.get('Name', '')
    ver = data.get('Version', '')
    if name: print(f'{name}: {ver}')
except: pass
"
done
