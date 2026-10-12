#!/usr/bin/env bash
# Keeps ~/swarm/gateway.py (127.0.0.1:8790) running; restarts it if it dies. Window infra:gateway.
# The tmux server predates srikanth's docker group, so start this window with: sg docker -c ~/swarm/run-gateway.sh
L=~/swarm/gateway.log
while true; do
  echo "=== gateway start $(date -u +%FT%TZ)" >> "$L"
  python3 -u ~/swarm/gateway.py >> "$L" 2>&1
  echo "=== gateway exited rc=$? $(date -u +%FT%TZ)" >> "$L"
  sleep 3
done
