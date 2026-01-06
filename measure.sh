#!/bin/bash
# 5-minute fan measurement script

echo "=== Meranie otáčok ventilátorov (OptimalCooling, 5 minút) ==="
echo "Čas | Fans | MaxTemp"
echo "----------------------------------------"

for i in {1..10}; do
    curl -k -s -u Administrator:7P7G6HP8 "https://10.31.0.10/redfish/v1/Chassis/1/Thermal/" | python3 -c "
import sys, json
from datetime import datetime
data = json.load(sys.stdin)
fans = [f.get('Reading') for f in data.get('Fans', [])]
temps = [t.get('ReadingCelsius') for t in data.get('Temperatures', []) if t.get('ReadingCelsius')]
max_temp = max(temps) if temps else 0
avg_fan = sum(fans)/len(fans) if fans else 0
print(f'{datetime.now().strftime(\"%H:%M:%S\")} | {avg_fan:.0f}% | {max_temp}°C')
"
    if [ $i -lt 10 ]; then
        sleep 30
    fi
done

echo "----------------------------------------"
echo "=== Meranie dokončené ==="
