#!/usr/bin/env bash
# gpuclaim.sh — atomic GPU locks (one per GPU index) via mkdir, shared by every sandbox through /swarm/shared.
#   gpuclaim.sh status
#   gpuclaim.sh <index> take <owner> ["what, how long"]   -> exit 0 if you now hold it, 1 if not
#   gpuclaim.sh <index> release <owner>                   -> only the owner may release
#   gpuclaim.sh <index> heartbeat <owner>                 -> refresh last-active (long-running jobs)
# A lock older than $GPU_LOCK_STALE_MIN (60) minutes is stale and may be taken over (the previous owner is reported).
# GPU count: nvidia-smi when present, else $GPU_COUNT, else the lock dirs that exist.
set -u
LOCKDIR="${GPU_LOCK_DIR:-$(cd "$(dirname "$(readlink -f "$0")")" && pwd)/locks}"  # next to this script: <swarm>/shared on the host, /swarm/shared in a sandbox
STALE_MIN=${GPU_LOCK_STALE_MIN:-60}
mkdir -p "$LOCKDIR"
gpu_count() { local n; n=$(nvidia-smi -L 2>/dev/null | grep -c '^GPU') || true; [ "${n:-0}" -gt 0 ] && { echo "$n"; return; }; [ -n "${GPU_COUNT:-}" ] && { echo "$GPU_COUNT"; return; }; ls -d "$LOCKDIR"/gpu* 2>/dev/null | wc -l; }
lock_path() { echo "$LOCKDIR/gpu$1"; }
owner_of()  { cat "$(lock_path "$1")/owner" 2>/dev/null || echo "?"; }
desc_of()   { cat "$(lock_path "$1")/desc"  2>/dev/null || echo ""; }
since_of()  { cat "$(lock_path "$1")/since" 2>/dev/null || echo "?"; }
last_active() { cat "$(lock_path "$1")/last_active" 2>/dev/null || cat "$(lock_path "$1")/since" 2>/dev/null || echo 0; }
age_min()   { local p; p="$(lock_path "$1")"; [ -d "$p" ] || { echo 0; return; }; echo $(( ( $(date +%s) - $(stat -c %Y "$p" 2>/dev/null || stat -f %m "$p") ) / 60 )); }
idle_min()  { echo $(( ( $(date +%s) - $(last_active "$1") ) / 60 )); }
status() {
  local n; n=$(gpu_count); [ "$n" -gt 0 ] || { echo "no GPUs on this box"; return; }
  for g in $(seq 0 $((n - 1))); do
    p="$(lock_path "$g")"
    if [ -d "$p" ]; then
      a=$(age_min "$g"); i=$(idle_min "$g"); flag=""; [ "$a" -ge "$STALE_MIN" ] && flag=" (STALE)"
      d=$(desc_of "$g"); [ -n "$d" ] && d=" — $d"
      echo "gpu$g: held by $(owner_of "$g") for ${a} min (idle ${i} min) since $(since_of "$g")$d$flag"
    else echo "gpu$g: free"; fi
  done
}
stamp() { echo "$2" > "$1/owner"; date -Is > "$1/since"; date +%s > "$1/last_active"; [ -n "$3" ] && echo "$3" > "$1/desc"; }
take() {
  local g="$1" who="$2" p; p="$(lock_path "$g")"; shift 2; local desc="$*"
  if mkdir "$p" 2>/dev/null; then stamp "$p" "$who" "$desc"; echo "gpu$g: taken by $who${desc:+ ($desc)}"; return 0; fi
  if [ "$(owner_of "$g")" = "$who" ]; then touch "$p"; date +%s > "$p/last_active"; [ -n "$desc" ] && echo "$desc" > "$p/desc"; echo "gpu$g: already yours ($who) — refreshed${desc:+ ($desc)}"; return 0; fi
  if [ "$(age_min "$g")" -ge "$STALE_MIN" ]; then
    old=$(owner_of "$g"); rm -rf "$p"
    if mkdir "$p" 2>/dev/null; then stamp "$p" "$who" "$desc"; echo "gpu$g: stale lock of $old taken over by $who${desc:+ ($desc)}"; return 0; fi
  fi
  echo "gpu$g: BUSY, held by $(owner_of "$g") for $(age_min "$g") min (idle $(idle_min "$g") min)$( [ -n "$(desc_of "$g")" ] && echo " — $(desc_of "$g")")"; return 1
}
release() { local g="$1" who="$2" p; p="$(lock_path "$g")"; [ -d "$p" ] || { echo "gpu$g: was not held"; return 0; }
  [ "$(owner_of "$g")" = "$who" ] || { echo "gpu$g: held by $(owner_of "$g"), not $who; refusing"; return 1; }; rm -rf "$p"; echo "gpu$g: released by $who"; }
heartbeat() { local g="$1" who="$2" p; p="$(lock_path "$g")"; [ -d "$p" ] || { echo "gpu$g: not held; cannot heartbeat"; return 1; }
  [ "$(owner_of "$g")" = "$who" ] || { echo "gpu$g: held by $(owner_of "$g"), not $who; refusing"; return 1; }; date +%s > "$p/last_active"; touch "$p"; echo "gpu$g: heartbeat refreshed for $who"; }
usage() { echo "usage: gpuclaim.sh status | <index> take|release|heartbeat <owner> [desc]" >&2; exit 2; }
case "${1:-status}" in
  status) status ;;
  ''|*[!0-9]*) usage ;;
  *) g="$1"; cmd="${2:-}"; who="${3:-}"; [ -n "$who" ] || usage
     case "$cmd" in take) shift 3; take "$g" "$who" "$@" ;; release) release "$g" "$who" ;; heartbeat) heartbeat "$g" "$who" ;; *) usage ;; esac ;;
esac
