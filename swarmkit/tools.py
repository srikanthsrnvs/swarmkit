"""Local tools for an SDK agent that lives in its own sandbox: the shell. The pi harness has read/write/edit/bash/grep/
find/ls; here one `bash` FunctionTool covers them (the runner runs INSIDE the agent's container, so the shell it gets is
the sandbox's own, with the same caps). Without it a model that is told it owns a sandbox invents the numbers it cannot
measure — seen in the first smoke run."""
from __future__ import annotations

import os
import subprocess

OUTPUT_LIMIT = 16_000  # characters per stream handed back to the model


def _clip(s: str, limit: int = OUTPUT_LIMIT) -> str:
    return s if len(s) <= limit else s[: limit // 2] + f"\n...[{len(s) - limit} chars cut]...\n" + s[-limit // 2:]


def bash_tool(cwd: str | None = None, default_timeout: int = 120, max_timeout: int = 3600):
    from agents import function_tool

    workdir = cwd or os.environ.get("SWARM_WORKDIR") or ("/swarm/me/work" if os.path.isdir("/swarm/me/work") else os.getcwd())

    @function_tool(name_override="bash")
    def bash(command: str, timeout_seconds: int = default_timeout) -> str:
        """Run a shell command inside YOUR sandbox (bash -lc; cwd /swarm/me/work) and return exit code, stdout and stderr.
        Use it for everything local: reading and writing files, grep, builds, measurements (hostname, nproc, nvidia-smi,
        cat /sys/fs/cgroup/memory.max). Long jobs: start them in tmux (`tmux new -d -s job '…'`) and poll their log."""
        t = max(1, min(int(timeout_seconds or default_timeout), max_timeout))
        try:
            p = subprocess.run(["bash", "-lc", command], cwd=workdir, capture_output=True, text=True, timeout=t, errors="replace")
        except subprocess.TimeoutExpired as e:
            return f"exit 124 (timed out after {t} s)\nstdout:\n{_clip(e.stdout or '')}\nstderr:\n{_clip(e.stderr or '')}"
        except OSError as e:
            return f"exit 127\nstderr:\n{e}"
        return f"exit {p.returncode}\nstdout:\n{_clip(p.stdout)}\nstderr:\n{_clip(p.stderr)}"

    return bash
