#!/usr/bin/env bash
# Bootstrap a portable network connection; no model is launched and no inbox is consumed.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); KIT=$(cd "$HERE/../.." && pwd)
REF=${AGENT_NETWORK_TAG:-$(cat "$KIT/agent-network.ref")}
AN=${AGENT_NETWORK:-$KIT/.cache/agent-network-$REF}
if [ -n "${AGENTNET_URL:-}" ]; then
  : "${AGENTNET_TOKEN:?supply AGENTNET_TOKEN through the environment secret store}"
  command -v node >/dev/null || { echo "Node 22+ is required" >&2; exit 1; }
  if [ ! -f "$AN/packages/cli/bin/anet.mjs" ]; then
    mkdir -p "$(dirname "$AN")"; git init -q "$AN"
    git -C "$AN" remote add origin https://github.com/srikanthsrnvs/agent-network
    git -C "$AN" fetch -q --depth 1 origin "$REF"; git -C "$AN" checkout -q --detach FETCH_HEAD
    (cd "$AN" && npm ci --no-audit --no-fund >/dev/null && npm run build >/dev/null)
  fi
  export AGENT_NETWORK="$AN"
  if [ -n "${SWARM_JOIN_KIT:-}" ]; then
    "$HERE/bin/net" contacts --file "$SWARM_JOIN_KIT/names.json" --no-inbox >/dev/null
  fi
  "$HERE/bin/net" whoami --no-inbox
elif [ -z "${SWARM_GATEWAY_HOST:-}" ]; then
  echo "set AGENTNET_URL/token (relay), or SWARM_GATEWAY_HOST/token (sandbox gateway)" >&2; exit 1
fi
if [ -n "${SWARM_GATEWAY_HOST:-}" ]; then
  "$HERE/bin/sc" 'printf "sandbox reachable: "; hostname'
fi
if [ -n "${SWARM_JOIN_KIT:-}" ]; then
  [ -f "$SWARM_JOIN_KIT/PROMPT.md" ] || { echo "join kit has no PROMPT.md" >&2; exit 1; }
  echo "standing prompt: $SWARM_JOIN_KIT/PROMPT.md"
fi
