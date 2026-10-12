# The exec gateway (optional)

Not needed for communication — that is the relay (`cloud/README.md`). The gateway gives a **cloud agent a shell in its
own sandbox on the box** over HTTPS: `POST /exec {"cmd", "timeout"}` runs `bash -lc <cmd>` inside the agent's container
as user `agent` (cwd `/swarm/me/work`) and returns `{exit, stdout, stderr, ms}`; `POST /upload {"path", "content", "mode"}`
writes a text file under `/swarm/me/`, `/swarm/shared/` or `/tmp/`; `GET /health`. Every request needs
`Authorization: Bearer <token>`; tokens live in `$SWARM_DIR/gateway-tokens.json` (`{agent-name: token}`, 0600, re-read on
every request) and a token only ever reaches *its* agent's sandbox `swarmkit-<swarm>-<name>` — never the host, never
another sandbox. stdlib only.

```bash
SWARM_DIR=~/swarms/<name> bin/swarm-join join <agent> --harness gateway --lane '…'   # sandbox + token (never printed)
SWARM_DIR=~/swarms/<name> gateway/run-gateway.sh                                      # 127.0.0.1:8790, in tmux
# in front: your own HTTPS — a named Cloudflare tunnel ingress `gw.<domain> -> http://localhost:8790`, or any reverse proxy with TLS
```

Client: `cloud/codex/bin/sc` (`SWARM_GATEWAY_HOST`, `SWARM_GATEWAY_TOKEN`; `SC_TIMEOUT` ≤ 3600; retries 3× on transport
errors; `sc --upload <local> <remote>`). Cloudflare cuts responses at 100 s, so behind it keep `SC_TIMEOUT` ≤ 90 and run
anything longer in tmux inside the sandbox, polling its log with `sc`. Limits: 2 MB request body, 4 MB per output stream.
Revoke an agent by deleting its line from `gateway-tokens.json`.
