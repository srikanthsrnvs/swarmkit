"""swarmkit: run N sandboxed agents on one box.

Orchestration is built on the OpenAI Agents SDK (``agents``): Agent/Runner, function tools, agents-as-tools,
Sessions, tracing and sandbox backends. Inter-agent messaging, identity and rooms come from the agent-network
protocol (``anet`` daemon / relay). This package is the landing place for that code; today the kit is the shell
scripts and prompt tooling in the repository root (see README.md).
"""

__version__ = "0.1.0"
