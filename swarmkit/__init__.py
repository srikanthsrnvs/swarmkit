"""swarmkit: portable local, cloud and sandboxed swarms.

Connecting agents is agent-network's job (`anet`: identity, names, store-and-forward messages, rooms; a hosted relay
for agents that cannot run a daemon). Running agents is the OpenAI Agents SDK's job (Agent/Runner, function tools,
agents-as-tools, Sessions, tracing) — `swarmkit.runner` is one swarm agent on it, `swarmkit.orchestrate` shows
agents-as-tools. The shell side (bin/, image/) puts each agent in its own Docker sandbox with caps and GPUs.
"""

__version__ = "0.3.1"
