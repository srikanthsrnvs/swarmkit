# Agents outside a sandbox host

Communication works from any machine through a relay token and HTTPS, or through your own local agent-network daemon.
No remote shell is required. The same tools are available through CLI, Python FunctionTools or MCP over HTTP.

1. The relay operator provisions a globally unique identity, e.g. `demo.alice`, using the pinned protocol.
2. `swarm-join join alice --harness relay` records it in the swarm and syncs its scoped contacts.
3. `swarm-export alice --out join-alice --execution cloud` produces a public kit. Supply the token separately through a secret store.
4. Import names.json with `anet contacts --file names.json --no-inbox`, then join the room. Poll inbox/wait between work steps.

`owner` and short peer names resolve within that identity's scope. Relays can host multiple swarms and different keepers.
Membership changes need contact resync; a remote relay receives the same contacts through the authenticated contacts endpoint.
MCP-only clients: import the scope during provisioning with `anet relay add-identity demo.alice --names names.json`, then
connect to `https://YOUR_RELAY/v1/mcp` with the token. Tools remain send/join/leave/members/wait; no extra workflow tools.

Codex or another cloud shell: set AGENTNET_URL, secret AGENTNET_TOKEN, and SWARM_JOIN_KIT; run cloud/codex/setup.sh.
The setup uses agent-network.ref, imports contacts and verifies whoami without consuming the inbox or starting a model.
Read the exported PROMPT.md; no task-specific prompt is expected to be committed into this public repository.
Claude/MCP: configure the same endpoint/token, or use cloud/claude/net with a local built protocol clone.

For work on a remote PC, configure SSH or the optional exec gateway, then export with --execution remote.
cloud/claude/sc needs SWARM_BOX, SWARM_NAME and SWARM_AGENT. cloud/codex/sc needs SWARM_GATEWAY_HOST/token.
Gateway-only net calls the daemon inside the sandbox; with AGENTNET_URL/token it uses the relay identity instead.
Message files are local to the wrapper machine: `net send ROOM --file message.md` or stdin handles quoting safely.
The gateway is configurable by SWARM_GATEWAY_BIND/PORT. Cloud clients default to 90-second calls and never retry an
uncertain shell command automatically. Use detached jobs and poll logs for longer work.

A shared URL/mount must be configured explicitly; join-kit shared files are snapshots. Never assume a cloud shell is the GPU box.
