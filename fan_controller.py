#!/usr/bin/env python3
"""
HP DL360 Gen10 Fan Speed Controller - Redfish API verzia
Riadi otáčky ventilátorov cez HPE iLO 5 Redfish API.
"""

import json
import sys
import signal
import time
import argparse
import logging
import urllib.request
import urllib.error
import ssl
import base64
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

try:
    import yaml
except ImportError:
    print("CHYBA: Chýba modul 'pyyaml'. Nainštalujte: pip3 install pyyaml")
    sys.exit(1)

# Globálna premenná pre graceful shutdown
running = True


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Nastaví logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    return logging.getLogger('fan_controller')


def load_config(config_path: str) -> dict:
    """Načíta konfiguráciu z YAML súboru."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Konfiguračný súbor nenájdený: {config_path}")
    with open(path, 'r') as f:
        return yaml.safe_load(f)


class RedfishClient:
    """Klient pre komunikáciu s HPE iLO cez Redfish API."""

    def __init__(self, host: str, username: str, password: str, logger: logging.Logger):
        self.base_url = f"https://{host}"
        self.username = username
        self.password = password
        self.logger = logger
        self.auth_header = self._create_auth_header()

        # SSL context - ignoruje self-signed certifikáty
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

    def _create_auth_header(self) -> str:
        """Vytvorí Basic Auth header."""
        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def _request(self, method: str, path: str, data: dict = None) -> Tuple[Optional[dict], int]:
        """Vykoná HTTP request na Redfish API."""
        url = f"{self.base_url}{path}"
        self.logger.debug(f"{method} {url}")

        headers = {
            "Authorization": self.auth_header,
            "Content-Type": "application/json",
            "OData-Version": "4.0"
        }

        body = json.dumps(data).encode() if data else None

        try:
            request = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(request, context=self.ssl_context, timeout=30) as response:
                status = response.status
                content = response.read().decode()
                return json.loads(content) if content else None, status
        except urllib.error.HTTPError as e:
            self.logger.error(f"HTTP Error {e.code}: {e.reason}")
            try:
                error_body = e.read().decode()
                self.logger.debug(f"Error body: {error_body}")
            except:
                pass
            return None, e.code
        except urllib.error.URLError as e:
            self.logger.error(f"URL Error: {e.reason}")
            return None, 0
        except Exception as e:
            self.logger.error(f"Request error: {e}")
            return None, 0

    def get(self, path: str) -> Optional[dict]:
        """GET request."""
        result, _ = self._request("GET", path)
        return result

    def patch(self, path: str, data: dict) -> Tuple[Optional[dict], int]:
        """PATCH request."""
        return self._request("PATCH", path, data)

    def post(self, path: str, data: dict) -> Tuple[Optional[dict], int]:
        """POST request."""
        return self._request("POST", path, data)


class HPEFanController:
    """Hlavná trieda pre riadenie ventilátorov."""

    def __init__(self, config: dict, logger: logging.Logger, dry_run: bool = False):
        self.config = config
        self.logger = logger
        self.dry_run = dry_run
        self.last_speed = -1
        self.error_count = 0

        # Redfish klient
        ilo_config = config.get('ilo', {})
        self.client = RedfishClient(
            host=ilo_config.get('host', 'localhost'),
            username=ilo_config.get('username', 'Administrator'),
            password=ilo_config.get('password', ''),
            logger=logger
        )

    def get_temperatures(self) -> Dict[str, float]:
        """Získa teploty zo senzorov cez Redfish."""
        data = self.client.get("/redfish/v1/Chassis/1/Thermal/")
        if not data:
            return {}

        temperatures = {}
        sensor_filters = self.config.get('sensors', [])

        for temp in data.get('Temperatures', []):
            name = temp.get('Name', '')
            reading = temp.get('ReadingCelsius')

            if reading is None:
                continue

            # Filter podľa konfigurácie
            if sensor_filters:
                if not any(f.lower() in name.lower() for f in sensor_filters):
                    continue

            temperatures[name] = float(reading)

        return temperatures

    def get_fan_status(self) -> Dict[str, int]:
        """Získa aktuálny stav ventilátorov."""
        data = self.client.get("/redfish/v1/Chassis/1/Thermal/")
        if not data:
            return {}

        fans = {}
        for fan in data.get('Fans', []):
            name = fan.get('Name', '')
            reading = fan.get('Reading')
            if reading is not None:
                fans[name] = int(reading)

        return fans

    def get_power_status(self) -> Dict[str, Any]:
        """Získa stav napájacích zdrojov."""
        data = self.client.get("/redfish/v1/Chassis/1/Power/")
        if not data:
            return {}

        status = {'supplies': [], 'redundant': True}
        for psu in data.get('PowerSupplies', []):
            psu_status = {
                'name': psu.get('Name', ''),
                'health': psu.get('Status', {}).get('Health', 'Unknown'),
                'state': psu.get('Status', {}).get('State', 'Unknown'),
                'watts': psu.get('LastPowerOutputWatts', 0)
            }
            status['supplies'].append(psu_status)
            if psu_status['health'] != 'OK' or psu_status['state'] != 'Enabled':
                status['redundant'] = False

        return status

    def calculate_fan_speed(self, temp: float) -> int:
        """Vypočíta cieľovú rýchlosť ventilátora."""
        temp_low = self.config.get('temp_low', 40)
        temp_high = self.config.get('temp_high', 80)
        fan_min = self.config.get('fan_min', 20)
        fan_max = self.config.get('fan_max', 100)

        if temp <= temp_low:
            return fan_min
        if temp >= temp_high:
            return fan_max

        ratio = (temp - temp_low) / (temp_high - temp_low)
        return int(fan_min + ratio * (fan_max - fan_min))

    def set_thermal_config(self, profile: str) -> bool:
        """
        Nastaví BIOS ThermalConfig profil.
        Dostupné profily: OptimalCooling, IncreasedCooling, MaximumCooling, EnhancedCooling
        POZOR: Vyžaduje reštart servera!
        """
        if self.dry_run:
            self.logger.info(f"[DRY-RUN] Nastavujem ThermalConfig: {profile}")
            return True

        # Najprv nastavíme pending hodnotu
        data = {"Attributes": {"ThermalConfig": profile}}
        result, status = self.client.patch("/redfish/v1/Systems/1/Bios/Settings/", data)

        if status in [200, 204]:
            self.logger.info(f"ThermalConfig nastavený na: {profile} (vyžaduje reštart)")
            return True
        else:
            self.logger.error(f"Nepodarilo sa nastaviť ThermalConfig: {status}")
            return False

    def try_set_fan_speed_oem(self, speed_percent: int) -> bool:
        """
        Nastaví rýchlosť ventilátorov cez HPE OEM endpoint.
        Používa FanPercentAdjust parameter (stabilnejší ako FanPercentMinimum).
        """
        if self.dry_run:
            self.logger.info(f"[DRY-RUN] Nastavujem FanPercentAdjust: {speed_percent}%")
            return True

        oem_data = {
            "Oem": {
                "Hpe": {
                    "FanPercentAdjust": speed_percent
                }
            }
        }
        result, status = self.client.patch("/redfish/v1/Chassis/1/Thermal/", oem_data)
        if status in [200, 204]:
            self.logger.info(f"FanPercentAdjust nastavený na: {speed_percent}%")
            return True

        self.logger.warning(f"Nepodarilo sa nastaviť FanPercentAdjust (status: {status})")
        return False

    def set_thermal_configuration(self, config: str) -> bool:
        """
        Nastaví ThermalConfiguration cez Redfish OEM endpoint.
        Dostupné hodnoty: OptimalCooling, IncreasedCooling, MaximumCooling, EnhancedCooling
        FUNGUJE BEZ REŠTARTU!
        """
        if self.dry_run:
            self.logger.info(f"[DRY-RUN] Nastavujem ThermalConfiguration: {config}")
            return True

        oem_data = {
            "Oem": {
                "Hpe": {
                    "ThermalConfiguration": config
                }
            }
        }
        result, status = self.client.patch("/redfish/v1/Chassis/1/Thermal/", oem_data)
        if status in [200, 204]:
            self.logger.info(f"ThermalConfiguration nastavený na: {config}")
            return True

        self.logger.warning(f"Nepodarilo sa nastaviť ThermalConfiguration (status: {status})")
        return False

    def run_iteration(self) -> bool:
        """Vykoná jednu iteráciu kontrolného cyklu."""
        # Získanie teplôt
        temperatures = self.get_temperatures()
        if not temperatures:
            self.error_count += 1
            self.logger.warning("Nepodarilo sa získať teploty")
            if self.error_count >= self.config.get('max_errors', 3):
                self.logger.error("Príliš veľa chýb, používam núdzovú rýchlosť")
            return False

        self.error_count = 0

        # Získanie stavu ventilátorov
        fans = self.get_fan_status()

        # Maximálna teplota
        max_temp = max(temperatures.values()) if temperatures else 0

        # Výpočet cieľovej rýchlosti
        target_speed = self.calculate_fan_speed(max_temp)

        # Aktuálna priemerná rýchlosť
        current_speed = sum(fans.values()) / len(fans) if fans else 0

        # Logovanie
        self.logger.info(f"Teploty: {temperatures}")
        self.logger.info(f"Max teplota: {max_temp:.1f}°C")
        self.logger.info(f"Ventilátory: {fans}")
        self.logger.info(f"Aktuálna rýchlosť: {current_speed:.0f}% | Cieľová: {target_speed}%")

        # Nastavenie FanPercentMinimum ak sa zmenila cieľová rýchlosť
        hysteresis = self.config.get('hysteresis', 5)
        if abs(target_speed - self.last_speed) >= hysteresis or self.last_speed == -1:
            self.try_set_fan_speed_oem(target_speed)
            self.last_speed = target_speed

        # Info o stave napájania (len pri prvej iterácii)
        if self.error_count == 0 and self.last_speed == target_speed:
            power = self.get_power_status()
            if not power.get('redundant', True):
                self.logger.info("INFO: PSU redundancia nie je aktívna")

        return True


def signal_handler(signum, frame):
    """Handler pre SIGTERM a SIGINT."""
    global running
    running = False


def main():
    parser = argparse.ArgumentParser(
        description='HP DL360 Gen10 Fan Speed Controller (Redfish API)'
    )
    parser.add_argument(
        '-c', '--config',
        default='/etc/fan-controller/config.yaml',
        help='Cesta ku konfiguračnému súboru'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Podrobný výstup'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulácia bez skutočných zmien'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Jedna iterácia a koniec'
    )
    parser.add_argument(
        '--set-thermal-config',
        choices=['OptimalCooling', 'IncreasedCooling', 'MaximumCooling', 'EnhancedCooling'],
        help='Nastaví ThermalConfiguration cez Redfish (bez reštartu!)'
    )
    parser.add_argument(
        '--init-thermal',
        choices=['OptimalCooling', 'IncreasedCooling', 'MaximumCooling', 'EnhancedCooling'],
        default=None,
        help='Nastaví ThermalConfiguration pri štarte daemona'
    )
    args = parser.parse_args()

    logger = setup_logging(args.verbose)
    logger.info("HP DL360 Gen10 Fan Speed Controller (Redfish) štartuje...")

    # Načítanie konfigurácie
    try:
        config_path = args.config
        if not Path(config_path).exists():
            local_config = Path(__file__).parent / 'config.yaml'
            if local_config.exists():
                config_path = str(local_config)
                logger.info(f"Používam lokálnu konfiguráciu: {config_path}")

        config = load_config(config_path)
        logger.info(f"Konfigurácia načítaná z: {config_path}")
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    # Vytvorenie controllera
    controller = HPEFanController(config, logger, args.dry_run)

    # Špeciálna akcia: nastavenie ThermalConfiguration
    if args.set_thermal_config:
        logger.info(f"Nastavujem ThermalConfiguration na: {args.set_thermal_config}")
        controller.set_thermal_configuration(args.set_thermal_config)
        sys.exit(0)

    # Inicializácia ThermalConfiguration pri štarte
    if args.init_thermal:
        logger.info(f"Inicializujem ThermalConfiguration na: {args.init_thermal}")
        controller.set_thermal_configuration(args.init_thermal)

    # Registrácia signal handlerov
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    interval = config.get('interval', 10)

    # Hlavný cyklus
    try:
        while running:
            controller.run_iteration()

            if args.once:
                break

            time.sleep(interval)

    except Exception as e:
        logger.error(f"Neočakávaná chyba: {e}")
    finally:
        logger.info("Fan Controller ukončený.")


if __name__ == '__main__':
    main()
