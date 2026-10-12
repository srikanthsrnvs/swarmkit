#!/usr/bin/env bash
# Render one prompt or a lane set (stdlib only); see python -m swarmkit.prompt --help.
set -euo pipefail
KIT=$(cd "$(dirname "$0")/.." && pwd)
export PYTHONPATH="$KIT${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m swarmkit.prompt "$@"
