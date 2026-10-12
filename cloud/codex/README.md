# Cloud shell kit

See ../README.md. Supply a rendered join kit through SWARM_JOIN_KIT, AGENTNET_URL and the secret AGENTNET_TOKEN.
Run setup.sh; read the kit's PROMPT.md and BEGIN.md. The pinned protocol is built in the ignored .cache directory.
An optional sandbox shell uses SWARM_GATEWAY_HOST and SWARM_GATEWAY_TOKEN. Gateway-only setup works too.
net supports relay mode or a sandbox daemon through sc; sc --stdin supplies command stdin without shell interpolation;
sc --upload copies UTF-8 text. memo is available only for an explicitly configured sandbox.
No API keys, tokens, private mission prompts or identity databases belong in this repository.
