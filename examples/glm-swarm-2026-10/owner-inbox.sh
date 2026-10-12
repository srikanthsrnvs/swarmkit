#!/usr/bin/env bash
# Show new messages for the owner (DMs to the owner identity, or room lines containing "@owner")
# from the swarm observer, newest last. Keeps a cursor so each line prints once.
# Usage: owner-inbox.sh [--all]   env: OBSERVER (default http://threadripper.local:8787)
set -euo pipefail
OBSERVER=${OBSERVER:-http://threadripper.local:8787}
AUTH=$(cat "${OBSERVER_BASIC_FILE:-$HOME/.config/agent-network/observer.basic}" 2>/dev/null || true)
CURSOR=${CURSOR:-"$HOME/.config/agent-network/swarm-owner.cursor"}
since=$( [ "${1:-}" = "--all" ] && echo "" || cat "$CURSOR" 2>/dev/null || echo "" )
lines=$(curl -sN --max-time 4 ${AUTH:+-u "$AUTH"} "$OBSERVER/events" | sed -n 's/^data: //p' \
  | jq -c --arg since "$since" 'select(.ts > $since) | select(.kind=="dm" or (.text|test("@owner";"i")))' || true)
if [ -z "$lines" ]; then echo "(no new owner messages)"; exit 0; fi
echo "$lines" | jq -r '"\(.ts[11:19]) \(.from) [\(.kind)\(if .room then " "+.room else "" end)]: \(.text)"'
echo "$lines" | tail -n1 | jq -r .ts > "$CURSOR"
