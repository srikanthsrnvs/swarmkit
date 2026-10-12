# Agents working in this repository

This is swarmkit, the ops kit that runs N sandboxed agents on one box on top of the
[agent-network](https://github.com/srikanthsrnvs/agent-network) protocol (see README.md). **If you are the
swarm agent `codex`** (your task says so), your instructions are in [cloud/codex/PROMPT.md](cloud/codex/PROMPT.md):
read it in full and follow it. Your only way to the Threadripper is `cloud/codex/bin/sc`, your network is
`cloud/codex/bin/net`, your memory is `cloud/codex/bin/memo` (all need `cloud/codex/setup.sh` to have run in
this environment). Do the work on the box, not here; this machine has no GPU.
