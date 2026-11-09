#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
umask 077
if ! command -v python3 >/dev/null; then
  echo 'Bitte Python 3.10 oder neuer von python.org installieren.'
  exit 1
fi
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10 oder neuer erforderlich"; import tkinter'
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
echo 'Installation fertig. Starte WISP mit: bash "WISP starten.command"'
