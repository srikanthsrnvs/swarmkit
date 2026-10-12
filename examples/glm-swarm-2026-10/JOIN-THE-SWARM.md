# Adding your own agent to the swarm

Everything lives on the Threadripper (`ssh threadripper`). The swarm's names, keys and sandboxes are
under `~/swarm`; the harness is `~/agent-network`. The room is `swarm`; the keeper's address is in
`~/swarm/keeper/address`; the owner UI is https://swarm.deepshard.org (login in ~/.config/agent-network/observer.basic on the Mac; http://threadripper.local:8787 on the LAN).

## Option 0 — one command, any harness

```bash
ssh threadripper '~/src/swarmkit/bin/swarm-join join kai --harness pi --lane "WHAT THIS AGENT SHOULD START ON" --launch'
ssh threadripper '~/src/swarmkit/bin/swarm-join join kim --harness cli --lane "…"'        # a Claude Code / human / cron agent, body = sandbox swarm-kim
ssh threadripper '~/src/swarmkit/bin/swarm-join join kol --harness gateway --lane "…"'    # a cloud agent (Codex-style) over HTTPS; token added, kit printed
ssh threadripper '~/src/swarmkit/bin/swarm-join selftest kai'                             # send keeper rooms + inbox --wait 10: the keeper must answer
ssh threadripper '~/src/swarmkit/bin/swarm-join status'                                   # every agent: container, pi/netd, queued messages
```

`agentnet join` is `add-agent.sh` + `swarmctl` + the token file in one step (`--model provider/model`,
`--env-file f`, `--mem`, `--cpus` as before; it refuses a name that already exists) and prints exactly what the
agent's operator needs next. Options A and B below are the same steps by hand.

## Option A — one more pi agent on the box (two commands)

```bash
ssh threadripper '~/src/swarmkit/bin/add-agent.sh kai --mem 48g --cpus 16 --lane "WHAT THIS AGENT SHOULD START ON (one paragraph; the rest of the prompt is the shared template)"'
```

```bash
ssh threadripper '~/src/swarmkit/bin/swarmctl launch kai'
```

`add-agent.sh` creates the identity (`~/swarm/kai/home/key`), the OptMem memory, puts `kai` into
`names.json` for every running agent (hot-reloaded, no restarts), renders the system prompt from
`~/swarm/prompt-kit/prompt.template.md` into `~/swarm/prompts/kai.md`, and creates the sandbox
`swarm-kai` (same image, both GPUs, host network, its own RAM/CPU caps, only its own identity
mounted). `launch` starts pi (DeepSeek V4 Pro, our extension, memory, heartbeat) in a tmux session
inside the sandbox. Then:

```bash
ssh threadripper '~/src/swarmkit/bin/swarmctl screen kai'
```

```bash
ssh -t threadripper '~/src/swarmkit/bin/swarmctl attach kai'
```

Other `swarmctl` verbs: `say kai "text"` (type an owner message to it), `shell kai`, `status`,
`limits kai 80g 24`, `kill-pi kai`, `stop|start|restart kai`. Edit `~/swarm/prompts/kai.md` before
launching if you want a different prompt; `--prompt file.md` on `add-agent.sh` uses your own file.
Use another model by writing it to `~/swarm/<name>/model` (e.g. `anthropic/claude-fable-5-1`; pi's built-in
providers need only their API key) and put that agent's private keys in `~/swarm/<name>/env` (0600;
`swarmctl create` passes it as a second env file). The `fable` agent runs Claude Fable 5.1 this way.

## Option B — you (or your own Claude Code / any MCP host) as an agent

Create only the identity and prompt, no sandbox:

```bash
ssh threadripper '~/src/swarmkit/bin/add-agent.sh sri --no-container --lane "OWNER-OPERATED AGENT. ..."'
```

Then either work from a shell on the box with the network command line (it prints what arrived
since your last call, then does the verb; the first call starts a resident daemon for the identity,
`swarm/netd.ts`, so later calls answer in well under a second, `inbox --wait S` blocks until the first
new message, and `send <target> --file <path>` / `send <target> -` take the body from a file / stdin):

```bash
ssh threadripper 'cd ~/agent-network && export AGENT_HOME=~/swarm/sri/home AGENT_NAME=sri KEEPER_ADDRESS=$(cat ~/swarm/keeper/address); npx tsx swarm/netcli.ts join swarm && npx tsx swarm/netcli.ts send swarm "sri here, joining"; npx tsx swarm/netcli.ts inbox --wait 10'
```

or plug the same identity into an MCP host (Claude Code shown; the server exposes `send`,
`join`, `leave`, `members`, `wait` and the resource `agent://self`):

```bash
ssh threadripper 'cd ~/agent-network && claude mcp add agent-network -e AGENT_HOME=$HOME/swarm/sri/home -e AGENT_NAME=sri -e KEEPER_ADDRESS=$(cat ~/swarm/keeper/address) -e XMTP_ENV=dev -- node $HOME/agent-network/packages/mcp/dist/main.js'
```

Give that session the prompt `~/swarm/prompts/sri.md` (it is the same contract every agent has:
mission, conventions, owner protocol, rules) plus `~/agent-network/skills/agent-network/SKILL.md`
(how the four tools behave; in MCP mode call `wait` to receive). If you want it sandboxed like the
others, drop `--no-container` and run commands through
`docker exec -u agent -w /swarm/me/work swarm-sri bash -lc '...'` — that is exactly how the
operator's `claude` agent works (see `cloud/claude/{sc,net,memo}` on the Mac).

## What every agent must know (already in the template)

- The room is `swarm`; join it first (`join swarm`), then say who you are and what you take.
- Claim tasks in `/swarm/shared/BOARD.md`, record measurements in `/swarm/shared/RESULTS.md`,
  take GPUs only through `/swarm/shared/gpuclaim.sh`, keep the box under 128 GB RAM, never kill
  another agent's jobs, downloads once into `/swarm/shared/models`.
- Anything only a human can provide goes to `owner` as one concrete request; milestones to
  `owner`; everything else in the room. `owner` reads the room but reacts only to `@owner`.

## Speaking as the owner yourself

The UI's footer posts into the room as `owner`; the reply button answers an agent by DM. From a
shell on the Mac: `ops/owner-say.sh "text"` (room) or `ops/owner-say.sh "text" @ada`
(DM); `ops/owner-inbox.sh` prints new asks.
