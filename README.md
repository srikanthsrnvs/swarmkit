# swarmkit

Set up agents for a swarm using any harness: cloud agents on a relay, local agents on a PC, Docker sandboxes on a
shared machine, or agents spread across multiple machines. agent-network supplies identities, rooms and transport.
pi and the OpenAI Agents SDK run agents; swarmkit supplies portable prompts, membership, sandboxes and operator tools.
Both repositories are public. Distribution is Git with an immutable protocol revision in `agent-network.ref`.

## Choose the execution environment

| Agent | Setup | Needs Docker? | Network |
|---|---|---|---|
| Cloud/MCP | relay identity + exported join kit | No | HTTPS relay or MCP |
| Local harness | `swarm-join join alice --harness local` | No | its own daemon, or a relay token |
| Sandbox pi | `swarm-join join alice --harness pi` | Yes | pi owns its XMTP client |
| Sandbox SDK | `swarm-join join alice --harness sdk` | Yes | SDK uses the sandbox's daemon |
| Remote agent | register its public address, export a kit | No on the operator | daemon or relay on its machine |
| Cloud agent with remote shell | sandbox + optional gateway | Yes on the sandbox host | daemon through gateway, or separate relay identity |

The four communication tools remain send, join, leave and members. Workflow, claims, roles and evidence are free text.
A new agent can communicate without having shell access to any other machine.

## Prerequisites and source preparation

Common: Bash, Python 3.10+, Node 22+, Git, jq. Sandboxes also need Docker and Bash 4+; pi/observer tools need tmux.
GPU sandboxes use NVIDIA CDI when configured, otherwise the toolkit's `--gpus all` fallback. CPU-only images are supported.
The SDK runner is tested with openai-agents 0.23.x; its dependency is constrained to that supported series.

```bash
git clone https://github.com/srikanthsrnvs/swarmkit && cd swarmkit
bin/stage-agent-network.sh --build
```

Staging refuses to replace code used by a running host daemon/relay. A matching source/build is reused.
To develop against a protocol checkout: `bin/stage-agent-network.sh <commit> --from /path/to/agent-network --build`.
`AGENT_NETWORK=/path/to/a/built/agent-network` selects host tools without replacing the staged tree.

## One machine, sandboxed agents

Write `mission.md` first: outcome, constraints, acceptance tests and completion policy. Keep API credentials in a
separate private env file (0600); do not put them in prompts or the repo. Use your relay's keeper address if cloud agents
will join. Without `--keeper-address`, swarm-init creates a keeper and prints the command to run it.

```bash
bin/swarmctl build                       # add --cpu for a machine without CUDA
bin/swarm-init demo --room demo-lab --keeper-address 0xYOUR_KEEPER_ADDRESS \
  --mission-file mission.md --env-file provider.env
export SWARM_DIR=$HOME/swarms/demo
bin/swarm-join join alice --harness pi  --lane "Build the first candidate" --model deepseek/deepseek-flash
bin/swarm-join join bob   --harness sdk --lane "Reproduce independently" --model deepseek-flash
# Review agents, models, resource caps and budget before launch: launch starts paid turns.
bin/swarmctl launch all
bin/swarm-observer start --port 8788
bin/swarm-say "Begin the mission; claim work and post evidence."
```

Choose caps for your workload and physical host; caps are ceilings, not memory reservations. Models/providers are
configured per agent (`--model`, provider env files; SDK provider flags in per-agent or swarm `sdk.conf`).
Port blocks are allocated per host across swarms, skipping listening TCP ports; `--port-base` requests an explicit block.
GPU locks are shared across swarms on that host (`SWARM_HOST_STATE`, default `~/.local/state/swarmkit`). Different operator
users must set the same `SWARM_GPU_LOCK_DIR` to coordinate a shared host. Locks on different PCs are independent.
A stale lock is never automatically stolen. Measure the job and ask its owner/operator to release it.

Images carry a source fingerprint. Create/launch refuse an old image; rebuild and recreate the affected containers.
Persistent work, memory and identities survive recreation. `SWARM_ALLOW_STALE_IMAGE=1` is an explicit legacy override.
Changing the mission refreshes shared/mission.md and generated prompts before launch. Explicit custom prompts are preserved.

## Cloud-only and mixed swarms

An operator can use ordinary CLI tools without Docker. On the relay host (or through its operator), provision namespaced
identities with the pinned protocol. Short names remain local to the swarm, so several swarms can each have alice and owner.

```bash
bin/swarm-init demo --room demo-lab --keeper-address 0xYOUR_KEEPER_ADDRESS --mission-file mission.md
export SWARM_DIR=$HOME/swarms/demo
bin/swarm-join join alice --harness relay --lane "Research and verify sources"
bin/swarm-export alice --out join-alice --execution cloud
```

The identity on the relay is `demo.alice`; its scoped contacts map `alice`, `owner`, `keeper` and peers to this swarm's
addresses. The shared relay address book and other swarms are untouched. Give the agent the public kit and its token
through a secret store, separately. It imports contacts, joins the room and polls. See [cloud/README.md](cloud/README.md).
A pure cloud operator can itself use a relay identity named `demo.owner`: initialize with its public `--owner-address`,
import names.json with its token, and use `anet send/inbox` rather than swarm-say (which drives a local owner identity).

## Multiple PCs

All PCs use the same room, keeper and operator address. Each agent holds its own key/database, or uses its own relay token.
Create a local identity on PC B, then register its public address on the operator PC:

```bash
bin/swarm-join register cara --address 0xCARA_ADDRESS
bin/swarm-export cara --out join-cara --execution local
# On PC B, copy the public kit and initialize its local swarm metadata:
bin/swarm-init demo --from /path/to/join-cara
# To join as the existing cara identity on PC B:
export AGENT_HOME=/path/to/cara-home AGENT_NAME=cara
AGENT_NETWORK=/path/to/built/agent-network /path/to/join-cara/join.sh
# For additional sandboxes on PC B, create fresh agent names and register their addresses on the operator PC.
```

Use `swarm-sync --names /path/to/public-roster.json` to merge new peers into a PC's roster. Conflicting mappings are refused.
`swarm-sync` updates local homes and relay identities recorded in relay-agents.json. On a relay on another host,
use each identity's `anet contacts --file names.json --no-inbox` (or provision it with `anet relay add-identity ... --names ...`).
Portable join kits contain only contacts, metadata, a rendered prompt and shared-state snapshots. They contain no keys or tokens.
A kit does not create a distributed filesystem: configure shared storage, or appoint a ledger keeper and exchange updates in
room messages. Use `--execution remote --workspace ... --shared ...` when exporting an agent that works through SSH/gateway.

## Operating and stopping

- `swarmctl status/screen`: inspect actual harness processes, memory/CPU usage and GPUs.
- `swarm-status-writer`: host snapshot every 30 s; run in your swarm's own tmux server.
- `swarm-watch`: durable periodic status log; optional `--inbox` consumes the operator inbox, so use exactly one reader.
- `swarmctl park <name>` stops model turns; `unpark` resumes the harness. SDK daemons continue buffering; pi catches up on restart.
- `swarm-stop`: stop this swarm's owned harnesses, daemons, containers and observer sessions; retain data/tokens.

SDK runners log receives, tool calls, errors and per-turn token usage in net.jsonl, with known env secrets redacted.
Use `--max-messages`, `--idle-exit`, `--heartbeat-minutes 0` and/or `--max-total-tokens` to set your parking policy.
The token ceiling retains completed-run totals across restarts and can overshoot by one SDK run; provider failures may not return usage. A token ceiling is not a dollar ceiling;
monitor the provider's bill and stop agents at your agreed spend limit. Session input keeps a recent window of complete turns;
SQLite history is retained, and durable notes/shared ledgers preserve decisions. A private pending queue preserves unprocessed inbox batches across parking/restarts. Host runners omit bash unless explicitly enabled.

The observer has its own identity. It cannot see peer DMs or operate the owner's inbox. Its SSE logger deduplicates replay.
Keep operator requests in DMs to owner, and findings in the room. A newly joined observer has no earlier room history.
Archive by copying logs, sessions, public prompts, notes and shared evidence; keep private credentials separate.

## Validation

```bash
python3 -m venv .venv && .venv/bin/pip install -e . pytest
TEST_AGENT_NETWORK=/path/to/built/agent-network .venv/bin/python -m pytest tests/
```

Tests exercise real setup scripts without Docker and actual SDK execution with a local fake model. They never call a paid provider.
Protocol integration tests in agent-network exercise the real XMTP dev network with throwaway identities.
Historical prompts and outcomes in examples/ describe one GLM experiment; they are not requirements for a new swarm.
