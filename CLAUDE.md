# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HP DL360 Gen10 Fan Speed Controller - Python daemon that controls server fan speeds via HPE iLO 5 Redfish API.

**Problem:** With `OptimalCooling` (default), fans gradually increase from ~30% to 100% over time, regardless of temperature.

**Solution:** Set `ThermalConfiguration: EnhancedCooling` which keeps fans stable and allows `FanPercentMinimum` control.

## Commands

```bash
# Test single iteration
python3 /opt/fan-controller/fan_controller.py --once -v

# Set ThermalConfiguration manually
python3 /opt/fan-controller/fan_controller.py --set-thermal-config EnhancedCooling

# Service management
sudo systemctl start|stop|restart|status fan-controller
sudo journalctl -u fan-controller -f

# Measure fans for 5 minutes (testing)
/home/rsys/development/fansSpeedController/measure.sh
```

## Architecture

```
/opt/fan-controller/
├── fan_controller.py        # Main daemon
└── set-thermal-config.sh    # ExecStartPre script (sets EnhancedCooling)

/etc/fan-controller/
└── config.yaml              # iLO credentials + thermal thresholds (chmod 600)

/etc/systemd/system/
└── fan-controller.service   # Systemd unit
```

**Service flow:**
1. `ExecStartPre` runs `set-thermal-config.sh` → sets `ThermalConfiguration: EnhancedCooling`
2. Main daemon starts and loops every 10s
3. Reads temperatures via Redfish API
4. Calculates target fan speed (linear interpolation)
5. Sets `FanPercentMinimum` via Redfish OEM endpoint

## Key HPE Redfish OEM Parameters

| Parameter | Endpoint | Effect |
|-----------|----------|--------|
| `ThermalConfiguration` | `/redfish/v1/Chassis/1/Thermal/` | Must be `EnhancedCooling` for manual control |
| `FanPercentMinimum` | `/redfish/v1/Chassis/1/Thermal/` | Sets minimum fan speed (0-100%) |

**Note:** `FanPercentAdjust` is NOT available on all iLO 5 versions (returns HTTP 400).

**Important:** Changes via Redfish are immediate (no reboot), but reset to BIOS defaults after server reboot.

## Configuration

`/etc/fan-controller/config.yaml`:
```yaml
ilo:
  host: "ILO_IP"
  username: "Administrator"
  password: "PASSWORD"

temp_low: 40      # °C → fan_min
temp_high: 80     # °C → fan_max
fan_min: 15       # %
fan_max: 100      # %
interval: 10      # seconds

sensors:          # Temperature sensors to monitor
  - "BMC"         # BMC chip - often hottest (60-66°C)
  - "CPU"         # CPU package temperatures
  - "Inlet"       # Ambient inlet temperature
```

## Redfish API Examples

```bash
# Set ThermalConfiguration
curl -k -X PATCH -u USER:PASS -H "content-type: application/json" \
  "https://ILO/redfish/v1/Chassis/1/Thermal/" \
  -d '{"Oem":{"Hpe":{"ThermalConfiguration":"EnhancedCooling"}}}'

# Set FanPercentMinimum
curl -k -X PATCH -u USER:PASS -H "content-type: application/json" \
  "https://ILO/redfish/v1/Chassis/1/Thermal/" \
  -d '{"Oem":{"Hpe":{"FanPercentMinimum":20}}}'

# Read status
curl -k -s -u USER:PASS "https://ILO/redfish/v1/Chassis/1/Thermal/" | python3 -m json.tool
```

## Test Results

| ThermalConfiguration | Behavior |
|---------------------|----------|
| OptimalCooling | Fans drift: 30% → 100% over time (unstable) |
| **EnhancedCooling** | Fans stable: ~36-57% depending on BMC temp |

Typical temperatures: BMC 60-66°C, CPU 40-47°C, Inlet 23-24°C

## Important Notes

- IPMI raw commands do NOT work on HPE iLO 5 Gen10
- `FanPercentAdjust` may not be available (HTTP 400) - use `FanPercentMinimum`
- `OptimalCooling` causes gradual fan speed increase regardless of temperature
- `EnhancedCooling` is required for stable fan control
- PSU redundancy loss (missing PSU) can trigger higher fan speeds (iLO safety)
- After iLO config changes, brief "ResetInProgress" errors are normal
- AMS (Agentless Management Service) should be installed but doesn't prevent fan drift alone
