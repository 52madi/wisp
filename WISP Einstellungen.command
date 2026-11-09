#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
exec bash 'WISP starten.command' --settings
