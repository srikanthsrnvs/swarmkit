#!/usr/bin/env bash
# Add an agent to a swarm: identity (anet init), memory, names.json everywhere, limits, prompt, sandbox.
#   bin/add-agent.sh <name> [--harness pi|sdk] [--model provider/model] [--mem 48g] [--cpus 16]
#                    [--lane "text" | --lane-file f | --prompt f] [--env-file f] [--no-container]
# Names are lowercase letters/digits. The new name is visible to every running agent within seconds (names.json is
# re-read on change); the new agent still joins the room itself at launch (its prompt says so).
#   pi   (default) a pi coding agent in the sandbox: `pi -e /opt/agent-network/adapters/pi` with the rendered prompt
#   sdk  the swarmkit OpenAI Agents SDK runner in the sandbox (python -m swarmkit.run) over the sandbox's anet daemon;
#        --model is the provider's model id (default deepseek-flash); the runner renders template + lane itself
# SWARM_DIR selects the swarm (default ~/swarms/default; create it with bin/swarm-init).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); KIT=$(dirname "$HERE")
SWARM=${SWARM_DIR:-$HOME/swarms/default}; export SWARM_DIR=$SWARM
TAG=${AGENT_NETWORK_TAG:-$(cat "$SWARM/agent-network.tag" 2>/dev/null || cat "$KIT/agent-network.ref" 2>/dev/null || cat "$KIT/image/agent-network/.tag" 2>/dev/null || echo v0.3.0)}
IMAGE=${IMAGE:-$(cat "$SWARM/image" 2>/dev/null || echo "swarmkit-agent:$TAG")}
name=${1:?name}; shift
[[ "$name" =~ ^[a-z][a-z0-9]{1,15}$ ]] || { echo "bad name: $name (lowercase letters/digits, 2-16 chars)" >&2; exit 1; }
  case "$name" in owner|keeper|observer|shared|prompts|logs|secrets) echo "reserved agent name: $name" >&2; exit 1;; esac
[ -f "$SWARM/names.json" ] || { echo "no swarm at $SWARM (bin/swarm-init <name> --room <room> first)" >&2; exit 1; }
harness=pi; mem=48g; cpus=16; lane=""; prompt=""; model=""; envfile=""; container=1
while [ $# -gt 0 ]; do case "$1" in
  --harness) harness=$2; shift 2;; --model) model=$2; shift 2;; --mem) mem=$2; shift 2;; --cpus) cpus=$2; shift 2;;
  --lane) lane=$2; shift 2;; --lane-file) lane=$(cat "$2"); shift 2;; --prompt) prompt=$2; shift 2;;
  --env-file) envfile=$2; shift 2;; --no-container) container=0; shift;; *) echo "unknown flag $1" >&2; exit 1;; esac; done
[[ "$cpus" =~ ^[1-9][0-9]*$ ]] || { echo "--cpus must be a positive integer (used for build parallelism)" >&2; exit 1; }
[ "$harness" != local ] || container=0
case "$harness" in pi|sdk|local) ;; *) echo "--harness pi|sdk|local" >&2; exit 1;; esac
jq -e --arg n "$name" 'has($n)' "$SWARM/names.json" >/dev/null && { echo "$name already exists in $SWARM/names.json" >&2; exit 1; }
[ -f "$SWARM/$name/home/key" ] && { echo "$name already has an identity at $SWARM/$name/home/key" >&2; exit 1; }
mkdir -p "$SWARM/$name"/{home,memory,work,pi/agent/extensions,.ccache} "$SWARM/prompts"

# identity: `anet init` from the staged+built agent-network on this host when it exists, else from the sandbox image
anet_init() {
  local host_anet="${AGENT_NETWORK:-$KIT/image/agent-network}/packages/cli/bin/anet.mjs"
  if [ -f "$host_anet" ] && [ -f "$(dirname "$host_anet")/../../core/dist/keystore.js" ] && command -v node >/dev/null; then
    AGENT_HOME="$SWARM/$name/home" node "$host_anet" init "$name"
  elif docker image inspect "$IMAGE" >/dev/null 2>&1; then
    docker run --rm -u "$(id -u)" -v "$SWARM/$name/home:/swarm/me/home" -e AGENT_HOME=/swarm/me/home -e HOME=/tmp "$IMAGE" anet init "$name"
  else
    echo "need either a built host copy (bin/stage-agent-network.sh --build) or the image $IMAGE (swarmctl build)" >&2; return 1
  fi
}
out=$(anet_init) || { echo "identity creation failed" >&2; exit 1; }
addr=$(printf '%s\n' "$out" | tail -1 | jq -r .address)
[[ "$addr" =~ ^0x[0-9a-fA-F]{40}$ ]] || { echo "key generation failed: $out" >&2; exit 1; }
chmod 600 "$SWARM/$name/home/key"
if [ -x "$HOME/.optmem/memo" ]; then MEMORY_DIR="$SWARM/$name/memory" "$HOME/.optmem/memo" init >/dev/null 2>&1 || true; fi
tmp=$(mktemp); jq --arg n "$name" --arg a "$addr" '. + {($n): $a}' "$SWARM/names.json" > "$tmp" && mv "$tmp" "$SWARM/names.json" && chmod 644 "$SWARM/names.json"
"$HERE/swarm-sync"   # a same-box relay learns the name too
grep -qx "$name" "$SWARM/agents.txt" 2>/dev/null || echo "$name" >> "$SWARM/agents.txt"
grep -q "^$name " "$SWARM/limits.conf" 2>/dev/null || echo "$name $mem $cpus" >> "$SWARM/limits.conf"
echo "$harness" > "$SWARM/$name/harness"
[ -z "$model" ] || echo "$model" > "$SWARM/$name/model"
[ -z "$envfile" ] || install -m 600 "$envfile" "$SWARM/$name/env"
room=$(cat "$SWARM/room" 2>/dev/null || echo swarm)
[ -n "$lane" ] || lane="GENERALIST. Read the shared board (/swarm/shared/BOARD.md), find the most valuable unclaimed or stalled task, claim it in the room and do it; reproduce others' key measurements; review the shared runbook."
printf '%s\n' "$lane" > "$SWARM/prompts/$name.lane"
if [ -n "$prompt" ]; then
  [ "$(realpath "$prompt")" = "$(realpath -m "$SWARM/prompts/$name.md")" ] || cp "$prompt" "$SWARM/prompts/$name.md"
  touch "$SWARM/prompts/$name.custom"
else
  template="$SWARM/prompts/prompt.template.md"; [ -f "$template" ] || template="$KIT/prompts/prompt.template.md"
  execution=sandbox; [ "$harness" != local ] || execution=local
  "$KIT/prompts/render-prompts.sh" --execution "$execution" --template "$template" --name "$name" --lane-file "$SWARM/prompts/$name.lane" --room "$room" \
    --mission-file "$SWARM/mission.md" --out "$SWARM/prompts/$name.md"
fi
[ -f "$SWARM/$name/pi/agent/models.json" ] || cp "$SWARM/pi-seed/models.json" "$SWARM/$name/pi/agent/models.json" 2>/dev/null || true
[ -f "$SWARM/$name/pi/agent/settings.json" ] || cp "$SWARM/pi-seed/settings.json" "$SWARM/$name/pi/agent/settings.json" 2>/dev/null || true
if [ $container = 1 ]; then "$HERE/swarmctl" create "$name"; fi
echo "added $name = $addr (harness $harness, mem $mem, cpus $cpus); prompt $SWARM/prompts/$name.md, lane $SWARM/prompts/$name.lane"
echo "launch it:   SWARM_DIR=$SWARM $HERE/swarmctl launch $name     (then: swarmctl screen $name)"
echo "by hand:     AGENT_HOME=$SWARM/$name/home AGENT_NAME=$name KEEPER_ADDRESS=\$(cat $SWARM/keeper/address) anet join $room"
