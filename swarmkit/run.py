"""`python -m swarmkit.run …` — one swarm agent on the OpenAI Agents SDK (see swarmkit/runner.py)."""
import sys

from swarmkit.runner import main

if __name__ == "__main__":
    sys.exit(main())
