#!/bin/bash
# Odinštalačný skript pre HP DL360 Gen10 Fan Controller
# =====================================================

set -e

echo "=== HP DL360 Gen10 Fan Controller - Odinštalácia ==="
echo ""

# Kontrola root oprávnení
if [[ $EUID -ne 0 ]]; then
    echo "CHYBA: Tento skript vyžaduje root oprávnenia."
    exit 1
fi

# Zastavenie a zakázanie služby
echo "[1/3] Zastavujem službu..."
if systemctl is-active --quiet fan-controller 2>/dev/null; then
    systemctl stop fan-controller
fi
systemctl disable fan-controller 2>/dev/null || true

# Obnovenie automatického riadenia ventilátorov
echo "[2/3] Obnovujem automatické riadenie ventilátorov..."
ipmitool raw 0x30 0x70 0x66 0x00 0x00 2>/dev/null || true

# Odstránenie súborov
echo "[3/3] Odstraňujem súbory..."
rm -f /etc/systemd/system/fan-controller.service
rm -rf /opt/fan-controller
# Konfiguráciu ponechávam pre prípad opätovnej inštalácie
# rm -rf /etc/fan-controller

systemctl daemon-reload

echo ""
echo "=== Odinštalácia dokončená ==="
echo "Konfigurácia ponechaná v: /etc/fan-controller/"
echo "Pre úplné odstránenie: rm -rf /etc/fan-controller"
echo ""
