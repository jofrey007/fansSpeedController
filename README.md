# HP DL360 Gen10 Fan Speed Controller

Daemon pre riadenie ventilátorov na serveroch HP DL360 Gen10 cez **HPE iLO 5 Redfish API**.

## Problém

Ventilátory na HP DL360 Gen10 sa postupne zvyšujú až na 100% bez ohľadu na teplotu.

## Skutočná príčina

**Consumer-grade disky** (napr. WD Blue) spôsobujú, že iLO postupne zvyšuje otáčky ventilátorov na 100%. iLO nevie čítať teplotu z týchto diskov a reaguje zvýšením chladenia ako bezpečnostné opatrenie.

### Testované disky

| Disk | Výsledok |
|------|----------|
| ❌ **WD Blue 1TB** | Spôsobuje drift na 100% |
| ✅ HGST 500GB | Funguje (11-12%) |
| ✅ Kingston DC600M 1.92TB | Funguje |
| ✅ HPE branded disky | Fungujú |

### Riešenie

1. **Vymeniť problémový disk** za enterprise disk (HGST, Kingston DC, HPE) - **odporúčané**
2. Alebo použiť tento fan-controller daemon (nepomôže úplne, iLO stále override-uje)

## Ak potrebuješ fan-controller

Tento daemon komunikuje s iLO cez Redfish API:
1. Nastaví `ThermalConfiguration` na `EnhancedCooling` pri štarte
2. Číta teploty a nastavuje `FanPercentMinimum` podľa lineárnej interpolácie

**Poznámka:** Ak je príčinou problémový disk, daemon nepomôže - iLO override-uje nastavenia.

### Inštalácia

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

### Konfigurácia

Súbor: `/etc/fan-controller/config.yaml`

```yaml
ilo:
  host: "ILO_IP"
  username: "Administrator"
  password: "PASSWORD"

temp_low: 40       # °C - minimálne otáčky
temp_high: 80      # °C - maximálne otáčky
fan_min: 15        # %
fan_max: 100       # %
interval: 10       # sekúnd

sensors:
  - "BMC"          # BMC chip (často najvyššia teplota)
  - "CPU"
  - "Inlet"
```

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

## Dôležité poznámky

- IPMI raw príkazy **nefungujú** na HPE iLO 5 Gen10
- `FanPercentAdjust` nemusí byť dostupný (HTTP 400) - použite `FanPercentMinimum`
- `FanPercentMinimum` nastavuje len **minimum** - iLO môže zvýšiť vyššie
- Ak máš consumer disk (WD Blue, Seagate Barracuda, atď.), daemon nepomôže

## Licencia

MIT
