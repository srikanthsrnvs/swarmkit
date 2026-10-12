#!/usr/bin/env bash
# Stage an immutable protocol ref without replacing a running host toolchain.
# stage-agent-network.sh [ref] [--from local-clone] [--build]
set -euo pipefail
KIT=$(cd "$(dirname "$0")/.." && pwd); DEST="$KIT/image/agent-network"
URL=${AGENT_NETWORK_URL:-https://github.com/srikanthsrnvs/agent-network}
tag=""; from=""; build=0
while [ $# -gt 0 ]; do case "$1" in --from) from=$2; shift 2;; --build) build=1; shift;; --*) exit 2;; *) tag=$1; shift;; esac; done
tag=${tag:-${AGENT_NETWORK_TAG:-$(cat "$KIT/agent-network.ref" 2>/dev/null || echo v0.3.0)}}
if [ -n "$from" ]; then revision=$(git -C "$from" rev-parse "$tag^{commit}"); else revision=$tag; fi
current=$(cat "$DEST/.commit" 2>/dev/null || true)
stamp="$revision:$(node --version 2>/dev/null || echo no-node)"
if [ "$current" = "$revision" ] && { [ $build = 0 ] || { [ -f "$DEST/packages/relay/dist/relay.js" ] && [ "$(cat "$DEST/.host-build" 2>/dev/null || true)" = "$stamp" ]; }; }; then
  echo "protocol source/build already current ($revision)"; exit 0
fi
# Match argv entries, not a broad pkill/pgrep pattern. A running daemon/relay owns this tree.
python3 - "$DEST" <<'GUARD'
import shlex, subprocess, sys
from pathlib import Path
prefix=Path(sys.argv[1]).resolve()
for line in subprocess.check_output(['ps','-eo','pid=,args='],text=True).splitlines():
    pid,_,command=line.strip().partition(' ')
    try: args=shlex.split(command)
    except ValueError: continue
    if not args or 'node' not in args[0].rsplit('/',1)[-1]: continue
    try: cwd=Path('/proc/'+pid+'/cwd').resolve(strict=True)
    except OSError:
        try:
            data=subprocess.check_output(['lsof','-a','-p',pid,'-d','cwd','-Fn'],text=True,stderr=subprocess.DEVNULL)
            cwd=Path(next(x[1:] for x in data.splitlines() if x.startswith('n')))
        except (OSError,subprocess.SubprocessError,StopIteration): cwd=None
    for arg in args[1:]:
        if not arg.endswith(('.js','.ts','.mjs')): continue
        path=Path(arg)
        if not path.is_absolute():
            if cwd is None: continue
            path=cwd/path
        if path.resolve().is_relative_to(prefix):
            raise SystemExit('staged protocol tree is in use; stop its owned daemon before rebuilding')

GUARD
if [ "$current" != "$revision" ]; then
  temp=$(mktemp -d "$KIT/image/.stage.XXXXXX"); trap 'rm -rf "$temp"' EXIT
  mkdir "$temp/source"
  if [ -n "$from" ]; then git -C "$from" archive "$revision" | tar -x -C "$temp/source"
  else
    git init -q "$temp/clone"; git -C "$temp/clone" remote add origin "$URL"
    git -C "$temp/clone" fetch -q --depth 1 origin "$tag"
    revision=$(git -C "$temp/clone" rev-parse FETCH_HEAD)
    git -C "$temp/clone" archive FETCH_HEAD | tar -x -C "$temp/source"
  fi
  echo "$tag" > "$temp/source/.tag"; echo "$revision" > "$temp/source/.commit"
  rm -rf "$DEST"; mv "$temp/source" "$DEST"
fi
if [ $build = 1 ]; then
  (cd "$DEST" && npm ci --no-audit --no-fund && npm run build)
  echo "$revision:$(node --version)" > "$DEST/.host-build"
fi
echo "staged protocol $revision"
