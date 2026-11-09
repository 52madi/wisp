#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
umask 077
if [ ! -x .venv/bin/python ]; then
  echo 'Bitte zuerst bash INSTALLIEREN.command ausführen.'
  exit 1
fi
exec .venv/bin/python wisp.py "$@"
