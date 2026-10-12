#!/usr/bin/env bash
# Stage a pinned agent-network tag into image/agent-network/ (git-ignored): the sandbox image builds from this copy, and
# with --build the same copy becomes the host-side toolchain (anet, keeper, observer) that swarm-init and add-agent use.
#   bin/stage-agent-network.sh [<tag>] [--from <local clone>] [--build]
#     <tag>     default: $AGENT_NETWORK_TAG, else the tag recorded in image/agent-network/.tag, else v0.3.0
#     --from    a local clone to `git archive` from (default: clone --depth 1 --branch <tag> from GitHub)
#     --build   npm ci && npm run build in the staged copy (Node 22+ on this machine), for the host-side tools
# Nothing is published to npm; the tag is the distribution. The staged copy records its tag in .tag.
set -euo pipefail
KIT=$(cd "$(dirname "$0")/.." && pwd)
DEST="$KIT/image/agent-network"
URL=${AGENT_NETWORK_URL:-https://github.com/srikanthsrnvs/agent-network}
tag=""; from=""; build=0
while [ $# -gt 0 ]; do case "$1" in
  --from) from=$2; shift 2;; --build) build=1; shift;; --*) echo "unknown flag $1" >&2; exit 2;; *) tag=$1; shift;; esac; done
tag=${tag:-${AGENT_NETWORK_TAG:-$(cat "$DEST/.tag" 2>/dev/null || echo v0.3.0)}}
if [ -f "$DEST/.tag" ] && [ "$(cat "$DEST/.tag")" = "$tag" ] && [ -f "$DEST/package.json" ]; then
  echo "image/agent-network already holds $tag"
else
  rm -rf "$DEST"; mkdir -p "$DEST"
  if [ -n "$from" ]; then
    git -C "$from" archive "$tag" | tar -x -C "$DEST"
  else
    tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
    git clone -q --depth 1 --branch "$tag" "$URL" "$tmp/src"
    (cd "$tmp/src" && git archive HEAD) | tar -x -C "$DEST"
  fi
  echo "$tag" > "$DEST/.tag"
  echo "staged agent-network $tag -> $DEST"
fi
if [ $build = 1 ]; then
  command -v node >/dev/null || { echo "node is required for --build" >&2; exit 1; }
  (cd "$DEST" && npm ci --no-audit --no-fund && npm run build) && echo "built: $DEST/packages/cli/bin/anet.mjs is usable on this host"
fi
