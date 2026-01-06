#!/bin/bash
# Nastaví ThermalConfiguration na EnhancedCooling
# Používa sa ako ExecStartPre v systemd

CONFIG_FILE="/etc/fan-controller/config.yaml"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Načítanie údajov z config.yaml (skús /etc, potom lokálny)
if [ ! -f "$CONFIG_FILE" ] && [ -f "$SCRIPT_DIR/config.yaml" ]; then
    CONFIG_FILE="$SCRIPT_DIR/config.yaml"
fi

if [ -f "$CONFIG_FILE" ]; then
    HOST=$(grep -A3 "^ilo:" "$CONFIG_FILE" | grep "host:" | awk '{print $2}' | tr -d '"')
    USER=$(grep -A3 "^ilo:" "$CONFIG_FILE" | grep "username:" | awk '{print $2}' | tr -d '"')
    PASS=$(grep -A3 "^ilo:" "$CONFIG_FILE" | grep "password:" | awk '{print $2}' | tr -d '"')
else
    echo "Config file not found: $CONFIG_FILE"
    exit 1
fi

# Nastavenie EnhancedCooling
curl -k -s -X PATCH \
    -u "${USER}:${PASS}" \
    -H "content-type: application/json" \
    "https://${HOST}/redfish/v1/Chassis/1/Thermal/" \
    -d '{"Oem":{"Hpe":{"ThermalConfiguration":"EnhancedCooling"}}}'

# Počkaj na aplikovanie
sleep 5
