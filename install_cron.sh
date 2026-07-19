#!/bin/bash
# Dodaje do crontab wpis @reboot uruchamiający weather.py po starcie Raspberry Pi.
# Uruchom raz na Pi: bash install_cron.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_CMD="@reboot sleep 10 && /usr/bin/python3 $SCRIPT_DIR/weather.py >> $SCRIPT_DIR/weather.log 2>&1"

# usuwamy ewentualny stary wpis dla weather.py, żeby skrypt można było uruchomić wielokrotnie
( crontab -l 2>/dev/null | grep -Fv "weather.py" ; echo "$CRON_CMD" ) | crontab -

echo "Dodano do crontab:"
echo "$CRON_CMD"
echo
echo "Upewnij się, że demon pigpiod startuje automatycznie:"
echo "  sudo systemctl enable pigpiod"
