"""Check executable argv, not wrapper-shell text, when reporting harness liveness."""
import shlex
import subprocess
import sys
from pathlib import Path


def matches(args, harness):
    if not args: return False
    exe = Path(args[0]).name
    if harness == "sdk":
        return exe.startswith("python") and len(args) > 2 and args[1:3] == ["-m", "swarmkit.run"]
    if harness == "pi":
        return exe == "pi" or (exe == "node" and len(args) > 1 and
            (Path(args[1]).name == "pi" or ("pi-coding-agent/" in args[1] and Path(args[1]).name == "cli.js")))
    if harness == "daemon":
        return exe == "node" and len(args) > 1 and args[1].endswith("packages/relay/dist/daemon.js")
    return False


def main():
    for line in subprocess.check_output(["ps", "-eo", "args="], text=True).splitlines():
        try: args = shlex.split(line)
        except ValueError: continue
        if matches(args, sys.argv[1]): return 0
    return 1


if __name__ == "__main__": raise SystemExit(main())
