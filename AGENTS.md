# Agents working in this repository

This is swarmkit, the kit that runs N sandboxed agents on one box on top of the
[agent-network](https://github.com/srikanthsrnvs/agent-network) protocol and the OpenAI Agents SDK (see README.md).
**If you are a swarm agent** (your task says so), your standing instructions are in `cloud/codex/PROMPT.md` (rendered
for you by the operator): read it in full and follow it. Your network is `cloud/codex/bin/net`; if you have a sandbox
on the box, `cloud/codex/bin/sc` is your shell there and `cloud/codex/bin/memo` your memory (all need
`cloud/codex/setup.sh` to have run in this environment). Do the work where your prompt says, not on this machine.
