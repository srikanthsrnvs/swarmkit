# Working in swarmkit

This public repository provides portable agent setup on top of agent-network and the OpenAI Agents SDK.
It supports cloud agents, agents in local environments, sandboxes on one PC, and agents across several PCs.

If your task explicitly says you are a swarm member, read the rendered prompt supplied by the operator.
When SWARM_JOIN_KIT is set, that prompt is $SWARM_JOIN_KIT/PROMPT.md. Otherwise use the prompt path in your task.
Do not infer a mission or machine from repository checkout paths. A missing prompt is a setup error.
The cloud/codex/bin/{net,sc,memo} wrappers are optional: net communicates; sc/memo require a configured remote sandbox.
Work and measure in the execution environment stated in the rendered prompt.

For repository changes, run pytest tests/ with the supported Agents SDK. Tests create throwaway identities and use a
local fake model; no paid API credentials are needed. TEST_AGENT_NETWORK selects a built protocol clone for setup tests.
