#!/usr/bin/env bash
# Speak as the owner identity through the observer. Usage: owner-say.sh "<text>" [room|@name]
set -euo pipefail
OBSERVER=${OBSERVER:-http://threadripper.local:8787}
AUTH=$(cat "${OBSERVER_BASIC_FILE:-$HOME/.config/agent-network/observer.basic}" 2>/dev/null || true)
text=${1:?text}; target=${2:-swarm}
# long text: file + one-line pointer (a 44k-char paste once went verbatim into 12 contexts)
if [ ${#text} -gt 4000 ] && [[ "$target" != @* ]]; then
  stamp=$(date -u +%Y%m%dT%H%M%SZ); f="/swarm/shared/owner/$stamp.md"
  printf '%s\n' "$text" | ssh threadripper "mkdir -p ~/swarm/shared/owner && cat > ~/swarm/shared/owner/$stamp.md"
  first=$(printf '%s' "$text" | head -c 300 | tr '\n' ' ')
  text="@everyone — owner posted a long document ($(( ${#text} / 1000 ))k chars): read $f. Starts: $first …"
fi
if [[ "$target" == @* ]]; then body=$(jq -cn --arg t "$text" --arg to "${target#@}" '{text:$t,to:$to}')
else body=$(jq -cn --arg t "$text" --arg r "$target" '{text:$t,room:$r}'); fi
TOKEN=$(cat "${OBSERVER_TOKEN_FILE:-$HOME/.config/agent-network/observer.token}" 2>/dev/null || true)
curl -s ${AUTH:+-u "$AUTH"} -X POST "$OBSERVER/send" -H 'content-type: application/json' -H "x-owner-token: $TOKEN" -d "$body"; echo
