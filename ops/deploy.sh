#!/usr/bin/env bash
# Push the agent-network checkout + swarm files from the Mac to the Threadripper and (re)start the observer.
#   ops/deploy.sh            sync + build + prompts + observer restart
#   ops/deploy.sh --recreate also recreate all sandboxes (picks up swarmctl/Dockerfile changes; pi sessions die)
# WARNING: this OVERWRITES the box's ~/agent-network, which the running GLM swarm uses as a frozen copy. Do not run
# it while a swarm is live. Env: REPO (agent-network checkout, default ~/agent-network), MISSION_DIR (brief.md +
# seed-paper.md for /swarm/shared), BOX_KIT (swarmkit on the box, default ~/src/swarmkit).
set -euo pipefail
KIT=$(cd "$(dirname "$0")/.." && pwd); REPO=${REPO:-$HOME/agent-network}; BOX_KIT=${BOX_KIT:-'~/src/swarmkit'}; cd "$REPO"
rsync -a --delete --exclude node_modules --exclude dist --exclude '*.tsbuildinfo' --exclude .git --exclude runs --exclude docs/runs --exclude '*.db3*' --exclude .env --exclude sandbox/home ./ threadripper:~/agent-network/
[ -d "$KIT/prompts/rendered" ] && rsync -a "$KIT/prompts/rendered/" threadripper:~/swarm/prompts/
rsync -a "$KIT"/prompts/{prompt.template.md,lanes.json,render-prompts.sh,derive-agent-prompt.py} threadripper:~/swarm/prompt-kit/
[ -n "${MISSION_DIR:-}" ] && rsync -a "$MISSION_DIR"/brief.md "$MISSION_DIR"/seed-paper.md threadripper:~/swarm/shared/
ssh threadripper bash -s <<'REMOTE'
set -euo pipefail
cd ~/agent-network && npm run build >/dev/null && echo "box: built"
mkdir -p ~/swarm/pi-seed && [ -f ~/swarm/pi-seed/models.json ] || echo "{\"providers\": {}}" > ~/swarm/pi-seed/models.json
[ -f ~/swarm/observer.token ] || { openssl rand -hex 24 > ~/swarm/observer.token; chmod 600 ~/swarm/observer.token; echo "box: new observer token"; }
[ -f ~/swarm/observer.basic ] || { echo "srikanth:$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)" > ~/swarm/observer.basic; chmod 600 ~/swarm/observer.basic; echo "box: new observer basic-auth password"; }
cat > ~/swarm/run-observer.sh <<'S'
#!/usr/bin/env bash
cd ~/agent-network
export AGENT_HOME=$HOME/swarm/owner/home AGENT_NAME=owner ROOM=swarm KEEPER_ADDRESS=$(cat ~/swarm/keeper/address) KEEPER_ROOMS_FILE=$HOME/swarm/keeper/rooms.json PORT=8787 HOST=0.0.0.0 XMTP_ENV=dev AGENT_EXIT_ON_STREAM_ERROR=1
export OBSERVER_TOKEN=$(cat ~/swarm/observer.token)
export OBSERVER_BASIC_AUTH=$(cat ~/swarm/observer.basic)
while true; do node packages/observer/dist/main.js 2>&1 | tee -a ~/swarm/owner/observer.log; echo "observer exited; restarting in 5 s"; sleep 5; done
S
chmod +x ~/swarm/run-observer.sh
tmux kill-window -t infra:observer 2>/dev/null || true
for pid in $(pgrep -f 'observer/dist/[m]ain.js' || true); do kill "$pid" 2>/dev/null || true; done; sleep 1
tmux new-window -t infra -n observer '~/swarm/run-observer.sh'
sleep 6; ss -ltn | grep -q ':8787 ' && echo "box: observer listening" || { echo "observer NOT listening"; tail -5 ~/swarm/owner/observer.log; exit 1; }
rm -rf /tmp/smoke-home /tmp/smoke*.std* 2>/dev/null || true
REMOTE
mkdir -p ~/.config/agent-network && scp -q threadripper:~/swarm/observer.token ~/.config/agent-network/observer.token && chmod 600 ~/.config/agent-network/observer.token && echo "mac: token copied"
scp -q threadripper:~/swarm/observer.basic ~/.config/agent-network/observer.basic && chmod 600 ~/.config/agent-network/observer.basic
if [ "${1:-}" = --recreate ]; then ssh threadripper "$BOX_KIT/bin/swarmctl create --recreate all" | tail -3; fi
echo "deploy done"
