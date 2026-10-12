# swarmkit

Run N sandboxed agents on one box. [agent-network](https://github.com/srikanthsrnvs/agent-network) connects them (an
identity per agent, names, store-and-forward messages, rooms, a hosted relay for agents elsewhere — the CLI is `anet`);
the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) runs the ones written in Python (Agent/Runner,
function tools, agents-as-tools, Sessions, tracing); pi runs the coding agents. This kit is everything an operator needs
around those two to put a dozen agents with their own Docker sandboxes, caps, GPUs, memory and prompts on one machine
and keep them working for days. Distribution is `git clone`; nothing is published to npm or PyPI.

```
bin/        swarm-init · add-agent.sh · swarmctl · swarm-join · swarm-say · swarm-relay-names · swarm-status-writer · stage-agent-network.sh
image/      Dockerfile for one sandbox per agent (CUDA devel or plain Ubuntu + node + pi + agent-network + uv + OptMem + swarmkit)
swarmkit/   the Python package: runner.py (one agent on the Agents SDK), orchestrate.py (agents-as-tools), tools.py (bash), netshim.py, prompt.py
prompts/    prompt.template.md (generic contract) · lanes.example.json · kickoff.example.md · render-prompts.sh
shared/     seeds for <swarm>/shared: gpuclaim.sh, ramcheck.sh, README.template.md
cloud/      how an agent outside the box joins (the relay) + the Codex and Claude Code wrappers
gateway/    OPTIONAL: a shell in a sandbox for a cloud agent, over HTTPS (not needed for communication)
mac-sandbox/ one pi agent in a Docker sandbox on a Mac (CPU base)
examples/glm-swarm-2026-10/  a worked example: the prompts, lanes, kickoff and runbook of a 13-agent run
```

## Run a 3-agent swarm on one box in 10 minutes

Box: Docker (with the NVIDIA container toolkit and CDI when it has GPUs — `nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml`),
Node 22+, bash 4+, python3 (3.10+), jq, git, tmux. One provider API key (the examples use DeepSeek's `deepseek-flash`; any OpenAI-compatible endpoint works).

```bash
git clone https://github.com/srikanthsrnvs/swarmkit ~/swarmkit && cd ~/swarmkit
bin/stage-agent-network.sh v0.3.0 --build        # agent-network at a pinned tag -> image/agent-network (also the host's anet/keeper/observer)
bin/swarmctl build --tag v0.3.0                   # -> swarmkit-agent:v0.3.0  (add --cpu on a box without GPUs; ~10 min the first time)

# 1. a swarm home: room, keeper, owner identity, names.json, shared/, prompt template
bin/swarm-init demo --room demo-lab --env-file deepseek.env            # deepseek.env: DEEPSEEK_API_KEY=…
#    --keeper-address 0x… reuses a running room-keeper (e.g. the hosted relay's); without it a keeper identity is created
#    and the command to run the keeper service is printed — run it (tmux) before launching agents
export SWARM_DIR=~/swarms/demo
$EDITOR $SWARM_DIR/mission.md                                         # one paragraph: what done looks like, constraints, proof

# 2. three agents: two pi coding agents and one OpenAI Agents SDK runner, each in its own sandbox
bin/add-agent.sh alice --lane "BUILD LEAD. …"      --mem 48g --cpus 16                  # pi, deepseek/deepseek-flash
bin/add-agent.sh bob   --lane "MEASUREMENT. …"     --mem 48g --cpus 16                  # pi
bin/add-agent.sh cara  --lane "RESEARCH. …" --harness sdk --model deepseek-flash        # python -m swarmkit.run in its sandbox
bin/swarmctl launch all                                                                  # staggered; tmux session "agent" in each

# 3. kickoff, as owner, into the room; then watch
bin/swarm-say "$(cat prompts/kickoff.example.md)"
bin/swarmctl status                      # containers, caps, GPU, RAM, locks; detects a harness that died inside tmux
bin/swarmctl screen alice                # what pi shows; `swarmctl say alice "…"` types an owner line into it
tail -f $SWARM_DIR/cara/net.jsonl        # the SDK runner's receives, turns, tool calls, sends
(cd image/agent-network && AGENT_HOME=$SWARM_DIR/owner/home AGENT_NAME=owner ROOM=demo-lab \
   KEEPER_ADDRESS=$(cat $SWARM_DIR/keeper/address) PORT=8787 npm run observer)   # the room UI at :8787; `bin/swarm-say --inbox` reads owner's DMs
```

What each step made: `~/swarms/demo/{room,mission.md,names.json,agents.txt,limits.conf,env,keeper/,owner/home,prompts/,
pi-seed/,shared/}` plus `<name>/{home,memory,work,pi,harness,…}` per agent; containers `swarmkit-demo-<name>` with
`/swarm/me` (the agent's dir), `/swarm/shared`, `/swarm/prompts:ro`, a RAM/CPU cap, the GPUs through CDI, host network
(ports `9100+100·i`), and the env `AGENT_HOME=/swarm/me/home AGENT_NAME KEEPER_ADDRESS XMTP_ENV` the pi adapter and `anet`
read. pi is launched as `pi -e /opt/agent-network/adapters/pi --system-prompt /swarm/prompts/<name>.md --tools
read,bash,edit,write,grep,find,ls,send,join,leave,members`; the SDK runner as `anet daemon && python -m swarmkit.run
--name <name> --lane-file … --room <room>` over the sandbox's own daemon socket. `swarm-join join <name> --harness
pi|sdk|cli|relay|gateway` wraps add-agent + launch + the hand-over text for one agent; `swarm-join selftest <name>` proves
the sandbox reaches the keeper; `swarm-join status` is one line per agent. `swarm-status-writer` (host, tmux) keeps
`shared/status/host.txt` fresh so agents can see the whole box from inside their cgroup.

## Add a cloud agent

An agent that is not on the box — Codex in its cloud, Claude Code on a laptop, an SDK program anywhere — joins through
the **relay** (agent-network's daemon for N identities behind bearer tokens, HTTPS; hosted at `https://relay.deepshard.org`,
or run your own). `bin/swarm-join join dana --harness relay` creates the identity on the relay host and prints the
two ways in: `anet` in HTTPS mode (`AGENTNET_URL` + `AGENTNET_TOKEN`, same verbs) for any shell-capable agent, or MCP over
HTTP (`claude mcp add --transport http agentnet $URL/v1/mcp --header "Authorization: Bearer …"`) for Claude Code / Codex /
the Agents SDK. Details, prompts and the two wrapper kits: [cloud/README.md](cloud/README.md). A cloud agent that should
also *work* on the box gets a sandbox plus the optional exec gateway: [gateway/README.md](gateway/README.md).

## What is borrowed from the OpenAI Agents SDK

| SDK piece | where it is used |
|---|---|
| `Agent` / `Runner.run(…, session=…, max_turns=N)` | `swarmkit/runner.py`: every inbound network message is one run; instructions = the rendered prompt + `anet.SKILL_SHORT` |
| function tools | the four network verbs `send`, `join`, `leave`, `members` as `FunctionTool`s (`net.tools()`), plus `bash` (`swarmkit/tools.py`): the sandbox's own shell, so the agent measures instead of inventing (`--no-bash` to drop it) |
| `OpenAIChatCompletionsModel` + `AsyncOpenAI(base_url=…)` | any OpenAI-compatible endpoint (DeepSeek, a local server, …); `--model --base-url --api-key-env` |
| `SQLiteSession` | per-agent history across turns and restarts, in `<swarm>/<name>/sessions.db` (`/swarm/me/sessions.db` in the sandbox) |
| tracing | on when `OPENAI_API_KEY` is set, else `set_tracing_disabled(True)`; the jsonl log (`net.jsonl`) is always written |
| agents-as-tools (`Agent.as_tool`) | `swarmkit/orchestrate.py`: a coordinator with two member agents as tools — in-process orchestration; cross-sandbox or cross-machine work is `send` |
| MCP servers (`MCPServerStreamableHttp`) | the relay's `/v1/mcp` for an SDK program that wants the verbs without any package of ours (cloud/README.md) |

The runner adds what the SDK does not have: the inbox loop, a heartbeat (one turn with a `[heartbeat]` input after H quiet
minutes, `--heartbeat-minutes`), keeper confirmations logged without a model turn, and `--max-messages` / `--idle-exit` for
smoke tests. `python -m swarmkit.run --help`.

## The dependency on agent-network

Pinned by tag. `bin/stage-agent-network.sh <tag>` puts a `git archive` of that tag in `image/agent-network/` (git-ignored;
`--from <local clone>` when the box cannot clone); the image copies it to `/opt/agent-network`, runs `npm ci && npm run build`
and installs `/usr/local/bin/anet`; `--build` builds the same copy on the host for `swarm-init`, `add-agent.sh`
(`anet init`), `swarm-say`, the keeper and the observer. The Python side uses the `anet` package from agent-network's
`python/` (ships with its v0.3.0 tag: `pip install -e ../agent-network/python`, or the `anet` extra in `pyproject.toml`);
until it is installed `swarmkit/netshim.py` provides the same API (`connect`, `Net.tools()`, `Net.inbox()`,
`Message.as_input()`, `SKILL_SHORT`) over httpx against the relay (`/v1/…`, bearer) or the local daemon (`unix://…/netd.sock`).

```bash
uv venv && uv pip install -e .            # openai-agents + httpx; python -m swarmkit.run --help
uv pip install -e ../agent-network/python # the anet package, when you have it
```

## Prompts

`prompts/prompt.template.md` is the contract every agent gets, mission-agnostic: `{{NAME}}`, `{{LANE}}`, `{{ROOM}}`,
`{{MISSION}}` (from `<swarm>/mission.md`), `{{SWARM}}`. It carries the conventions that live runs taught (one send then end
the turn, no acknowledgements, address people, claim before work, provenance on every number, the GPU lock, the owner
protocol, memory across compaction, the never-list). `add-agent.sh` renders it per agent into `<swarm>/prompts/<name>.md`
(pi) and the SDK runner renders the same template itself; `render-prompts.sh --lanes lanes.json` renders a whole set.
`lanes.example.json` and `kickoff.example.md` are starting points; `examples/glm-swarm-2026-10/` is the full set from a real
13-agent run (GLM 5.3 Flash at 2-bit on a Threadripper), kept as a worked example of how specific a mission and its lanes get.

## Secrets

Never committed: `*.token`, `gateway-tokens.json`, `observer.basic`, `<swarm>/env`, agent keys. Tokens are created by
`anet relay add-identity` / `swarm-join` and only ever written to files (0600); no command here prints one.

## Test box

Developed and smoke-tested on one workstation (2 GPUs, Docker + NVIDIA CDI, Node 24, python3.14/uv) reachable only over
ssh; the hosted relay runs there too. Nothing in bin/ or prompts/ assumes that machine: the box name, GPU count, caps and
ports are all per-swarm data under `~/swarms/<name>/`.
