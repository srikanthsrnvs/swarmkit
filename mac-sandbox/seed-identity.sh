#!/usr/bin/env bash
# Copy a host agent's identity (key, names, XMTP db) into the `agent-mac` container. Refuses while a pi agent is
# running on the host or inside the container: two clients on one XMTP db corrupt it.
#   AGENT_HOME=~/.agent-network mac-sandbox/seed-identity.sh
set -euo pipefail

NAME=agent-mac
SRC="${AGENT_HOME:-$HOME/.agent-network}"
DST=/home/agent/.agent-network

if pgrep -f "adapters/pi" >/dev/null; then
  echo "refusing: a pi agent with the network adapter is running on this host (pgrep -f adapters/pi):" >&2
  pgrep -fl "adapters/pi" >&2
  exit 1
fi
[ "$(docker container inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null)" = "true" ] || { echo "container $NAME is not running; run mac-sandbox/run.sh first" >&2; exit 1; }
if docker exec -u agent "$NAME" pgrep -f "adapters/pi" >/dev/null 2>&1; then
  echo "refusing: pi is running inside $NAME (tmux session mac). Stop it first." >&2
  exit 1
fi
[ -f "$SRC/key" ] || { echo "no key at $SRC/key" >&2; exit 1; }

# pi is not the only owner: a resident anet daemon also holds the identity database.
if command -v lsof >/dev/null; then
  for file in "$SRC"/xmtp-*.db3 "$SRC"/xmtp-*.db3-wal "$SRC"/xmtp-*.db3-shm; do
    [ -e "$file" ] || continue
    if lsof -t -- "$file" >/dev/null 2>&1; then echo "refusing: a network client holds the source identity database" >&2; exit 1; fi
  done
fi
if docker exec -u agent "$NAME" pgrep -f '[r]elay/dist/daemon.js' >/dev/null 2>&1; then
  echo "refusing: a network daemon is running inside $NAME; stop it before seeding" >&2; exit 1
fi

docker exec -u agent "$NAME" mkdir -p "$DST"
copied=()
for f in key names.json xmtp-dev.db3 xmtp-dev.db3-wal xmtp-dev.db3-shm xmtp-dev.db3.sqlcipher_salt xmtp-dev.cursor; do
  if [ -e "$SRC/$f" ]; then
    docker cp "$SRC/$f" "$NAME:$DST/$f"
    copied+=("$f")
  fi
done
# docker cp keeps the host uid; hand the files to the agent user and lock the key down.
docker exec -u root "$NAME" sh -c "chown -R agent:agent $DST && chmod 700 $DST && chmod 600 $DST/key && chmod 644 $DST/names.json 2>/dev/null; chmod u+w $DST/xmtp-dev.db3.sqlcipher_salt 2>/dev/null || true"
echo "identity -> $NAME:$DST (${copied[*]})"

