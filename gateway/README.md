# Optional sandbox exec gateway

A gateway supplies a cloud agent's remote shell; communication itself can use a relay or local daemon.
Provision a sandbox with `swarm-join join alice --harness gateway` and run `gateway/run-gateway.sh` on its host.
SWARM_GATEWAY_BIND defaults to 127.0.0.1; SWARM_GATEWAY_PORT defaults to 8790. Use another port for another swarm.
Put TLS/reverse proxy in front. Each bearer token maps to one sandbox; gateway-tokens.json is private (0600).

POST /exec accepts cmd, timeout and optional stdin. POST /upload writes UTF-8 text to /swarm/me, /swarm/shared or /tmp.
GET /health requires a token and checks that token's sandbox. Request/stream limits are 2 MB/4 MB.
The gateway logs operation metadata, never command bodies. It does not grant a host shell.
cloud/codex/bin/sc defaults to <=90-second requests for proxy compatibility. Longer work runs detached in the sandbox.
Set SWARM_GATEWAY_MAX_WAIT explicitly for a proxy that supports longer responses. Shell commands are not automatically
retried after uncertain transport failure; inspect the job before resubmitting. Uploading identical text may be retried.
cloud/codex/bin/net uses the sandbox daemon through sc when relay variables are absent. --file paths are local to the client.
