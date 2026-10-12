#!/usr/bin/env bash
# Setup script for a cloud environment (Codex or similar) running one swarm agent.
# Needs: AGENTNET_URL (variable) and AGENTNET_TOKEN (secret) for the relay — see cloud/README.md.
# Optional: SWARM_GATEWAY_HOST (variable) + SWARM_GATEWAY_TOKEN (secret) for a shell in a sandbox on the box (gateway/README.md).
# Installs agent-network at the pinned tag next to this repo so cloud/codex/bin/net (= anet in HTTPS mode) works.
set -euo pipefail
: "${AGENTNET_URL:?set the AGENTNET_URL variable}" "${AGENTNET_TOKEN:?set the AGENTNET_TOKEN secret}"
HERE=$(cd "$(dirname "$0")" && pwd); KIT=$(cd "$HERE/../.." && pwd)
TAG=${AGENT_NETWORK_TAG:-$(cat "$KIT/image/agent-network/.tag" 2>/dev/null || echo v0.2.0)}
AN=${AGENT_NETWORK:-$KIT/../agent-network}
command -v node >/dev/null || { echo "node 22+ is required for anet" >&2; exit 1; }
if [ ! -f "$AN/packages/cli/bin/anet.mjs" ]; then
  git clone -q --depth 1 --branch "$TAG" https://github.com/srikanthsrnvs/agent-network "$AN"
  (cd "$AN" && npm ci --no-audit --no-fund >/dev/null && npm run build >/dev/null)
fi
chmod +x "$HERE/bin/"*
echo "network: $("$HERE/bin/net" whoami)"
if [ -n "${SWARM_GATEWAY_HOST:-}" ]; then
  command -v python3 >/dev/null || { echo "python3 is required by cloud/codex/bin/sc" >&2; exit 1; }
  "$HERE/bin/sc" 'echo "sandbox reachable: $(hostname) as $(whoami); GPUs: $(nvidia-smi -L 2>/dev/null | wc -l)"'
fi
