#!/usr/bin/env bash
# Render prompt.template.md into rendered/<name>.md using lanes.json (rendered/ is not committed; per-run prompts are archived).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p rendered
for name in $(jq -r 'keys[]' lanes.json); do
  lane=$(jq -r --arg n "$name" '.[$n]' lanes.json)
  awk -v name="$name" -v lane="$lane" '{ gsub(/\{\{NAME\}\}/, name); gsub(/\{\{LANE\}\}/, lane); print }' prompt.template.md > "rendered/$name.md"
done
python3 derive-agent-prompt.py claude && python3 derive-agent-prompt.py codex
ls rendered | tr "\n" " "; echo
