#!/usr/bin/env bash
# Keeps gateway.py (127.0.0.1:8790) running for one swarm; restarts it if it dies. Run on the host (docker group) in tmux:
#   SWARM_DIR=~/swarms/<name> gateway/run-gateway.sh     (log: $SWARM_DIR/gateway.log)
# If your tmux server predates your docker group membership: sg docker -c '…/run-gateway.sh'.
SWARM=${SWARM_DIR:-$HOME/swarms/default}; export SWARM_DIR=$SWARM
L=$SWARM/gateway.log
while true; do
  echo "=== gateway start $(date -u +%FT%TZ)" >> "$L"
  python3 -u "$(dirname "$0")/gateway.py" >> "$L" 2>&1
  echo "=== gateway exited rc=$? $(date -u +%FT%TZ)" >> "$L"
  sleep 3
done
