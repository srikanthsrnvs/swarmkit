# Codex (or any cloud harness) as a swarm agent

Codex runs in OpenAI's cloud and cannot see the box. Its network is the relay (`cloud/README.md`): `cloud/codex/bin/net`
is `anet` in HTTPS mode. Optionally its *shell* is a sandbox on the box reached through the exec gateway
(`gateway/README.md`): `cloud/codex/bin/sc` is one HTTPS POST per command. Neither needs ssh or cloudflared on the Codex
side — plain HTTPS is all its egress proxy allows.

Environment (Codex "cloud environment" settings; the same variables for any other harness):

| | |
|---|---|
| setup script | `cd /workspace/swarmkit && bash cloud/codex/setup.sh` |
| variable `AGENTNET_URL` | the relay, e.g. `https://relay.deepshard.org` |
| secret `AGENTNET_TOKEN` | the identity's token (from the operator: `swarm-join join <name> --harness relay`) |
| variable `SWARM_GATEWAY_HOST` | *(optional, shell)* the gateway's hostname, no `https://` |
| secret `SWARM_GATEWAY_TOKEN` | *(optional, shell)* the sandbox token (`swarm-join join <name> --harness gateway`) |
| internet access | on (the relay and gateway hostnames at least) |

`setup.sh` installs Node and clones agent-network at the pinned tag so `net` works, and checks the gateway when configured.
Task text: `cloud/codex/BEGIN.md`; standing instructions: a prompt rendered with `prompts/render-prompts.sh` for this
agent, committed to the environment's repo as `cloud/codex/PROMPT.md` (an example of a rendered one from a real run:
`examples/glm-swarm-2026-10/cloud/codex-PROMPT.md`). `AGENTS.md` at the repo root points Codex to it.

Wrappers: `net <inbox [--wait S] | send <target> <text…> | send <target> --file F | join | leave | members | rooms | whoami>`;
`sc '<cmd>'` (cwd `/swarm/me/work`, user `agent`, `SC_TIMEOUT` ≤ 3600; long jobs in tmux inside the sandbox and polled;
`sc --upload <local> <remote>` ships a text file); `memo <wake|note|nap|recall|zoom …>`. A message body with quotes or
newlines goes through a file: `sc --upload reply.md /swarm/me/work/reply.md && net send <room> --file /swarm/me/work/reply.md`
(or, without a sandbox, `net send <room> -` with the body on stdin).
