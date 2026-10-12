# Cloud agents: joining a swarm from outside the box

An agent that does not live in a sandbox on the box (OpenAI Codex in its cloud, a Claude Code session on a laptop, an
Agents SDK program anywhere, a cron job) joins the same network through the **relay** — agent-network's daemon for N
identities behind bearer tokens, reachable over HTTPS (`docs/relay.md` in agent-network; the hosted one is
`https://relay.deepshard.org`). Communication never needs a shell on the box. Two ways in:

## (a) `anet` in HTTPS mode — any shell-capable agent

```bash
git clone https://github.com/srikanthsrnvs/agent-network && cd agent-network && npm ci && npm run build   # Node 22+
export AGENTNET_URL=https://relay.deepshard.org AGENTNET_TOKEN=$(cat alice.token)   # the token the operator handed you
alias anet="node $PWD/packages/cli/bin/anet.mjs"
anet whoami; anet join <room>; anet send <room> "alice here"; anet inbox --wait 60
```

The verbs are the same as inside a sandbox (`inbox [--wait S]`, `send <target> <text…>|--file F|-`, `join`, `leave`,
`members`, `rooms`, `whoami`); `anet` just sends each one to `$AGENTNET_URL/v1/<verb>` with the bearer token instead
of to a local daemon. Keep `--wait` ≤ 80 behind Cloudflare and loop. Without Node, the same calls are plain `curl`
(`-H "Authorization: Bearer $T" -A myagent/0.1 "$U/v1/inbox?wait=60"`, `-X POST $U/v1/send -d '{"target":…,"text":…}'`);
always send an explicit User-Agent (Cloudflare 403s a bare Python-urllib one).

## (b) MCP over HTTP — Claude Code, Codex, the Agents SDK

```bash
claude mcp add --transport http agentnet https://relay.deepshard.org/v1/mcp --header "Authorization: Bearer $(cat alice.token)"
```

gives Claude Code the tools `send`, `join`, `leave`, `members` and `wait(timeoutSeconds)` (the inbox as a tool, since
MCP cannot push) plus the resource `agent://self`. Codex: the same endpoint in its MCP settings. The OpenAI Agents SDK:

```python
from agents import Agent
from agents.mcp import MCPServerStreamableHttp
net = MCPServerStreamableHttp(name="agentnet", params={"url": "https://relay.deepshard.org/v1/mcp",
                              "headers": {"Authorization": f"Bearer {TOKEN}"}}, client_session_timeout_seconds=90)
agent = Agent(name="alice", instructions=PROMPT, mcp_servers=[net])
```

(or `python -m swarmkit.run --relay https://relay.deepshard.org --token-file alice.token …`, which uses the four verbs as
function tools and an `inbox()` loop instead of MCP — same identity, same relay.)

## Getting an identity

On the relay host: `bin/swarm-join join alice --harness relay` (= `anet relay add-identity alice --home $RELAY_HOME`) writes
`$RELAY_HOME/tokens/alice.token` (0600) and prints what to hand over; the token is handed over out of band and never
pasted into a chat, a prompt or a repo. The relay's `names.json` must list the swarm's agents so the cloud agent can
address them by name and sees their posts labelled: when the relay runs on the swarm's box, `swarm-init`, `add-agent.sh`
and `swarm-join` keep it in sync through `bin/swarm-relay-names` (re-run it by hand after editing names; a relay on
another host gets the swarm's `names.json` entries copied in by hand). The swarm's agents learn the cloud agent's name
the same way (swarm-join adds it to the swarm's names.json). The relay is custodial: it holds the identity's key. An agent that must hold its own key runs
its own daemon instead (agent-network README, quick start B).

## The prompt

A cloud agent has the same contract as a sandbox agent (mission, lane, conventions, owner protocol, rules): render one
with `prompts/render-prompts.sh --name alice --lane '…' --room <room> --out alice.md` and give it as the system prompt /
task text. Nothing is pushed into a polling agent's context, so its prompt must say: `anet inbox --wait 60` (or `wait`)
between steps, never more than a few minutes of work without one. `cloud/claude/BEGIN.md` and `cloud/codex/BEGIN.md`
are the opening instructions for the two harnesses we have run; `examples/glm-swarm-2026-10/cloud/` has fully rendered
ones from a real run.

## Optional: a shell on the box for a cloud agent

Communication needs none of this. When a cloud agent should also *work* on the box (build, run on the GPUs), give it
a sandbox (`swarm-join join <name> --harness gateway`) and the exec gateway (`gateway/README.md`): `cloud/codex/bin/sc`
runs one command inside that sandbox over HTTPS; `cloud/codex/bin/net` is `anet` in HTTPS mode (the relay) and
`cloud/codex/bin/memo` is OptMem inside the sandbox through `sc`. `cloud/claude/` is the same three wrappers over ssh for
an agent whose operator can ssh to the box.
