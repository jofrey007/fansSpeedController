#!/bin/bash
# Inštalačný skript pre HP DL360 Gen10 Fan Controller (Redfish)
# =============================================================

set -e

INSTALL_DIR="/opt/fan-controller"
CONFIG_DIR="/etc/fan-controller"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== HP DL360 Gen10 Fan Controller (Redfish) - Inštalácia ==="
echo ""

# Kontrola root oprávnení
if [[ $EUID -ne 0 ]]; then
    echo "CHYBA: Tento skript vyžaduje root oprávnenia."
    echo "Spustite: sudo $0"
    exit 1
fi

# Kontrola závislostí
echo "[1/5] Kontrola závislostí..."

if ! command -v python3 &> /dev/null; then
    echo "CHYBA: Python3 nie je nainštalovaný."
    exit 1
fi

# Kontrola Python modulu yaml
if ! python3 -c "import yaml" 2>/dev/null; then
    echo "  Inštalujem pyyaml..."
    pip3 install pyyaml || dnf install -y python3-pyyaml
fi

# Zastavenie existujúcej služby ak beží
echo "[2/5] Kontrola existujúcej služby..."
if systemctl is-active --quiet fan-controller 2>/dev/null; then
    echo "  Zastavujem existujúcu službu..."
    systemctl stop fan-controller
fi

# Vytvorenie adresárov
echo "[3/5] Vytváram adresáre..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"

# Kopírovanie súborov
echo "[4/5] Kopírujem súbory..."
cp "$SCRIPT_DIR/fan_controller.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/set-thermal-config.sh" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/fan_controller.py"
chmod +x "$INSTALL_DIR/set-thermal-config.sh"

# Konfigurácia
if [[ ! -f "$CONFIG_DIR/config.yaml" ]]; then
    cp "$SCRIPT_DIR/config.yaml" "$CONFIG_DIR/"
    chmod 600 "$CONFIG_DIR/config.yaml"  # Obsahuje heslo
    echo "  Konfiguračný súbor vytvorený: $CONFIG_DIR/config.yaml"
    echo "  DÔLEŽITÉ: Upravte prihlasovacie údaje k iLO!"
else
    echo "  Konfiguračný súbor už existuje, preskakujem."
fi

# Systemd služba
echo "[5/5] Inštalujem systemd službu..."
cp "$SCRIPT_DIR/fan-controller.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable fan-controller

echo ""
echo "=== Inštalácia dokončená ==="
echo ""
echo "Príkazy:"
echo "  Testovanie:         python3 $INSTALL_DIR/fan_controller.py --once -v"
echo "  Spustiť službu:     systemctl start fan-controller"
echo "  Zastaviť službu:    systemctl stop fan-controller"
echo "  Stav služby:        systemctl status fan-controller"
echo "  Zobraziť logy:      journalctl -u fan-controller -f"
echo ""
echo "Konfigurácia:         $CONFIG_DIR/config.yaml"
echo ""
