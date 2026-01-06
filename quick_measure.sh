#!/bin/bash
echo "Čas | Fans | ThermalConfig"
for i in {1..4}; do
    curl -k -s -u Administrator:7P7G6HP8 "https://10.31.0.10/redfish/v1/Chassis/1/Thermal/" | python3 -c "
import sys, json
from datetime import datetime
data = json.load(sys.stdin)
oem = data.get('Oem', {}).get('Hpe', {})
fans = data.get('Fans', [{}])[0].get('Reading', 0)
print(f'{datetime.now().strftime(\"%H:%M:%S\")} | {fans}% | {oem.get(\"ThermalConfiguration\")}')
"
    if [ $i -lt 4 ]; then
        sleep 30
    fi
done
