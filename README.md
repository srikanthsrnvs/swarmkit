# swarmkit

Run N sandboxed agents on one box, on top of the [agent-network](https://github.com/srikanthsrnvs/agent-network)
protocol and the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python). agent-network gives every
agent an identity, a name, store-and-forward messaging and rooms across machines; this kit is everything an
operator needs around that to put a dozen agents with their own sandboxes, GPUs, memory and prompts on one
machine and keep them working for days. Private: it carries one operator's box layout and hostnames.

> **Nothing here is live.** The GLM 2-bit swarm that is running on the Threadripper uses frozen copies of this
> material on the box (`~/agent-network/swarm/*`, `~/swarm/gateway.py`, the `swarm-agent` image built from the
> pre-split layout) and Codex's cloud environment is still created from agent-network `main`. This repo is the
> place that material lives from now on; switching the box or Codex to it is a later, explicit step.

## Orchestration: built on the OpenAI Agents SDK

Everything that is "run agents" rather than "connect agents" is the SDK's job, not ours. Declared as a
dependency from day one (`pyproject.toml`: `openai-agents`, `httpx`). What we borrow and where it lands:

| borrowed from the SDK | used for |
|---|---|
| `Agent` / `Runner` | the per-agent loop: an inbound network message becomes a `Runner.run(agent, msg.as_input(), session=…)` turn; replaces the hand-written loop that used to live in `packages/client/src/loop.ts` |
| function tools | the four network primitives (`send`, `join`, `leave`, `members`) as `FunctionTool`s over the agent-network daemon/relay HTTP API (`httpx`) |
| agents-as-tools | a lane specialist (research, build, review) callable by a coordinator without leaving the process |
| Sessions (SQLite) | per-agent history across turns, in `/swarm/me/`; replaces the OptMem-only memory for in-process agents |
| tracing | one trace per network turn, so a 13-agent run can be read afterwards without grepping tmux logs |
| sandbox backends | the execution side of what `bin/swarmctl` + `gateway/gateway.py` do with Docker today |

The shell tooling in this repo is what the swarm ran on in October 2026 and still works; the orchestration
layer moves into `swarmkit/` (Python) as the SDK pieces above replace it, kit by kit.

## Layout

- `image/` — `Dockerfile` for one sandbox per agent (CUDA devel + node + pi + the agent-network pi adapter + uv +
  OptMem) and the `.dockerignore` for its build context
- `bin/` — `swarmctl` (build / create / start / launch / screen / say / attach / shell / limits / status),
  `add-agent.sh` (identity + names.json + limits + prompt + sandbox), `swarm-join` (one command: identity, prompt,
  sandbox, and for cloud agents a gateway token; `selftest`, `status`)
- `cloud/codex/` — the Codex cloud-environment kit (`setup.sh`, `bin/{sc,net,memo}` over the HTTPS gateway,
  `PROMPT.md`, `BEGIN.md`, `README.md`)
- `cloud/claude/` — the same three wrappers over ssh for a Claude Code agent driven from the operator's Mac, plus
  its `BEGIN.md` and the owner-side `CRON-PROMPT.md`
- `gateway/` — `gateway.py` (127.0.0.1:8790, bearer token → `docker exec` into that agent's sandbox only; stdlib)
  and `run-gateway.sh`; fronted by a named Cloudflare tunnel
- `mac-sandbox/` — a Docker sandbox for a single agent on a Mac (no host filesystem, host Ollama)
- `prompts/` — `prompt.template.md` + `lanes.json` → `render-prompts.sh` → `rendered/<name>.md` (not committed);
  `derive-agent-prompt.py` turns a pi prompt into the polling variant for Claude Code / Codex; `kickoff.md`;
  `JOIN-THE-SWARM.md` (how a new agent of any harness joins a running swarm)
- `ops/` — `owner-say.sh` / `owner-inbox.sh` (speak and listen as the owner through the observer), `deploy.sh`
  (sync to the box; read its warning first), `KICKOFF-RUNBOOK.md`
- `swarmkit/` — the Python package (SDK-based orchestration lands here)
- `AGENTS.md` — the pointer Codex reads when its environment is created from this repo

## Depending on agent-network

The sandbox image needs the protocol repo built inside it. Today `bin/swarmctl build` takes an agent-network
checkout as the Docker context (`REPO`, default `~/agent-network`). The target (PR5 in agent-network's plan) is a
pinned tag with no clone credentials on the box:

```bash
TAG=v0.2.0
mkdir -p image/agent-network && git -C ~/src/agent-network archive "$TAG" | tar -x -C image/agent-network
# then build with image/ as the context; image/agent-network/ is git-ignored here
```

The per-agent CLI inside a sandbox is agent-network's `anet` (`inbox`, `send`, `join`, `leave`, `members`,
`rooms`, `whoami`, backed by its resident daemon). The frozen box image still calls it as
`npx tsx swarm/netcli.ts`, so `cloud/codex/bin/net` and `cloud/claude/net` keep that spelling until the box is
switched.

## Secrets

Never committed: `gateway-tokens.json`, `*.token`, `observer.basic`, `swarm.env`, agent keys. Tokens are created
by `swarm-join join <name> --harness gateway` on the box and read by the gateway on every request.

## Provenance

Moved out of `srikanthsrnvs/agent-network` at tag `pre-split-2026-10-12` (plain copy, no history). The run
artifacts that used to sit next to these files (prompts per agent, briefs, checkpoints, assessments, session
logs) are archived on the operator's machine, not in any repo.
