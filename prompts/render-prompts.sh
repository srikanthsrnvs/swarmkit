#!/usr/bin/env bash
# Render prompt.template.md ({{NAME}}, {{LANE}}, {{ROOM}}, {{MISSION}}, {{SWARM}}) for one agent or for every agent in a lanes file.
#   render-prompts.sh --name alice (--lane "text" | --lane-file f) --out rendered/alice.md [--template T] [--room R] [--mission-file M] [--swarm S]
#   render-prompts.sh --lanes lanes.json --out-dir rendered/ [--template T] [--room R] [--mission-file M] [--swarm S]
# Defaults: template = prompts/prompt.template.md next to this script; room = $SWARM_DIR/room or "swarm"; mission =
# $SWARM_DIR/mission.md or a placeholder; swarm = basename of $SWARM_DIR or "default". bin/add-agent.sh calls the first form.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SWARM=${SWARM_DIR:-$HOME/swarms/default}
template="$HERE/prompt.template.md"; name=""; lane=""; lanefile=""; out=""; lanes=""; outdir=""
room=$(cat "$SWARM/room" 2>/dev/null || echo swarm); mission="$SWARM/mission.md"; swarm=$(basename "$SWARM")
while [ $# -gt 0 ]; do case "$1" in
  --template) template=$2; shift 2;; --name) name=$2; shift 2;; --lane) lane=$2; shift 2;; --lane-file) lanefile=$2; shift 2;;
  --out) out=$2; shift 2;; --lanes) lanes=$2; shift 2;; --out-dir) outdir=$2; shift 2;; --room) room=$2; shift 2;;
  --mission-file) mission=$2; shift 2;; --swarm) swarm=$2; shift 2;; *) echo "unknown flag $1" >&2; exit 2;; esac; done
[ -f "$template" ] || { echo "no template at $template" >&2; exit 1; }
render() { # name lane out
  python3 - "$template" "$1" "$2" "$room" "$mission" "$swarm" "$3" <<'PY'
import sys, pathlib
template, name, lane, room, mission_file, swarm, out = sys.argv[1:8]
mission = pathlib.Path(mission_file).read_text().strip() if pathlib.Path(mission_file).is_file() else "<no mission yet: the owner will post it in the room; meanwhile read /swarm/shared/README.md and BOARD.md>"
s = pathlib.Path(template).read_text()
for k, v in {"NAME": name, "LANE": lane.strip(), "ROOM": room, "MISSION": mission, "SWARM": swarm}.items():
    s = s.replace("{{" + k + "}}", v)
pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True); pathlib.Path(out).write_text(s)
print(f"rendered {out} ({len(s.split())} words)")
PY
}
if [ -n "$lanes" ]; then
  [ -n "$outdir" ] || outdir="$HERE/rendered"
  for n in $(jq -r 'keys[]' "$lanes"); do render "$n" "$(jq -r --arg n "$n" '.[$n]' "$lanes")" "$outdir/$n.md"; done
else
  [ -n "$name" ] && [ -n "$out" ] || { sed -n '2,6p' "$0" >&2; exit 2; }
  [ -n "$lanefile" ] && lane=$(cat "$lanefile")
  [ -n "$lane" ] || { echo "--lane or --lane-file is required" >&2; exit 2; }
  render "$name" "$lane" "$out"
fi
