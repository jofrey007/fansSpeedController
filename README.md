# HP DL360 Gen10 Fan Speed Controller

Daemon pre riadenie ventilátorov na serveroch HP DL360 Gen10 cez **HPE iLO 5 Redfish API**.

## Problém

HP amsd služba na Rocky Linux 10 nefunguje správne - po štarte OS sa otáčky ventilátorov postupne zvyšujú až na 100%.

## Riešenie

Python daemon komunikujúci s iLO cez Redfish API:
1. Nastaví `ThermalConfiguration` na `EnhancedCooling` pri štarte
2. Číta teploty a nastavuje `FanPercentMinimum` podľa lineárnej interpolácie
3. Monitoruje stav systému

**Výsledok:** Ventilátory **100% → 23%** (pri bežnej záťaži)

## Inštalácia

```bash
# Prerekvizity
pip3 install pyyaml

# Inštalácia služby
sudo ./install.sh

# Upravte konfiguráciu (iLO prístup)
sudo nano /etc/fan-controller/config.yaml

# Spustite službu
sudo systemctl start fan-controller
```

## Použitie

```bash
# Testovanie (jedna iterácia)
python3 fan_controller.py --once -v

# Okamžité nastavenie ThermalConfiguration
python3 fan_controller.py --set-thermal-config EnhancedCooling

# Správa systemd služby
sudo systemctl start fan-controller
sudo systemctl status fan-controller
sudo journalctl -u fan-controller -f
```

## Konfigurácia

Súbor: `/etc/fan-controller/config.yaml`

```yaml
# iLO pripojenie
ilo:
  host: "10.31.0.10"
  username: "Administrator"
  password: "your-password"

# Teplotné prahy pre lineárnu interpoláciu
temp_low: 40       # °C - minimálne otáčky
temp_high: 80      # °C - maximálne otáčky

# Rozsah ventilátorov
fan_min: 15        # %
fan_max: 100       # %

interval: 10       # sekúnd
```

## ThermalConfiguration profily

| Profil | Popis |
|--------|-------|
| **EnhancedCooling** | Odporúčaný - umožňuje manuálne riadenie |
| OptimalCooling | Štandardné nastavenie |
| IncreasedCooling | Vyššie otáčky |
| MaximumCooling | Maximálne chladenie |

## Ako to funguje

1. Pri štarte nastaví `ThermalConfiguration: EnhancedCooling` cez Redfish
2. Každých N sekúnd číta teploty a vypočíta cieľovú rýchlosť
3. Nastaví `FanPercentMinimum` podľa teploty
4. iLO riadi ventilátory na základe tohto minima

## Redfish API príkazy

```bash
# Nastavenie ThermalConfiguration
curl -k -X PATCH -u USER:PASS -H "content-type: application/json" \
  "https://ILO-IP/redfish/v1/Chassis/1/Thermal/" \
  -d '{"Oem":{"Hpe":{"ThermalConfiguration":"EnhancedCooling"}}}'

# Nastavenie FanPercentMinimum
curl -k -X PATCH -u USER:PASS -H "content-type: application/json" \
  "https://ILO-IP/redfish/v1/Chassis/1/Thermal/" \
  -d '{"Oem":{"Hpe":{"FanPercentMinimum":20}}}'

# Čítanie stavu
curl -k -s -u USER:PASS "https://ILO-IP/redfish/v1/Chassis/1/Thermal/"
```

## Licencia

MIT
