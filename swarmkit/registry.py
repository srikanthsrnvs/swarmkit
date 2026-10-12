"""Public swarm membership and portable join kits. Never reads or exports keys/tokens."""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import socket
from pathlib import Path
from swarmkit.prompt import render_prompt

NAME = re.compile(r"^[a-z][a-z0-9]{1,15}$")
ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(path)


def sync(swarm: Path, incoming: Path | None = None) -> dict[str, str]:
    names = json.loads((swarm / "names.json").read_text())
    if incoming:
        peers = json.loads(incoming.read_text())
        if not isinstance(peers, dict):
            raise ValueError("names must be an object")
        for n, a in peers.items():
            if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", n) or not isinstance(a, str) or not ADDRESS.fullmatch(a):
                raise ValueError("invalid contact")
            if n in names and names[n].lower() != a.lower():
                raise ValueError(f"contact conflict for {n}; use one authoritative swarm roster")
        names.update(peers)
    namespace = (swarm / "swarm-name").read_text().strip() if (swarm / "swarm-name").exists() else swarm.name
    for name, address in list(names.items()):
        if "." not in name:
            qualified = f"{namespace}.{name}"
            if qualified in names and names[qualified].lower() != address.lower():
                raise ValueError(f"contact conflict for {qualified}")
            names[qualified] = address
    write_json(swarm / "names.json", names)
    for home in swarm.glob("*/home"):
        write_json(home / "names.json", names)
    return names


def register(swarm: Path, name: str, address: str) -> None:
    if not NAME.fullmatch(name) or name in ("owner", "keeper", "observer") or not ADDRESS.fullmatch(address):
        raise ValueError("name must be 2–16 lowercase letters/digits, not owner/keeper/observer; address must be 0x...")
    names = json.loads((swarm / "names.json").read_text())
    if name in names and names[name].lower() != address.lower():
        raise ValueError(f"{name} already belongs to another identity")
    names[name] = address
    write_json(swarm / "names.json", names)
    sync(swarm)


def export(swarm: Path, name: str, out: Path, execution: str, workspace: str | None, shared: str | None) -> None:
    if name not in json.loads((swarm / "names.json").read_text()):
        raise ValueError(f"register {name} before exporting its kit")
    if out.exists() and any(out.iterdir()):
        raise ValueError("output directory must be empty (avoid overwriting an existing kit)")
    out.mkdir(parents=True, exist_ok=True)
    namespace = (swarm / "swarm-name").read_text().strip() if (swarm / "swarm-name").exists() else swarm.name
    room = (swarm / "room").read_text().strip()
    relay = (swarm / "relay").read_text().strip()
    names = sync(swarm)
    write_json(out / "names.json", names)
    lane_file = swarm / "prompts" / f"{name}.lane"
    lane = lane_file.read_text() if lane_file.exists() else "Read the shared ledger and claim useful unclaimed work."
    (out / "PROMPT.md").write_text(render_prompt(name=name, lane=lane, room=room, template=str(swarm / "prompts/prompt.template.md"),
        swarm_dir=swarm, swarm=namespace, execution=execution, workspace=workspace, shared=shared or ("/swarm/shared" if execution == "sandbox" else "shared/")))
    if execution != "sandbox" and shared is None:
        with (out / "PROMPT.md").open("a") as f:
            f.write("\nJOIN KIT: shared/ contains snapshots. Use the room/ledger keeper for current state until live shared storage is configured.\n")
    for f in ("mission.md", "shared/README.md", "shared/BOARD.md", "shared/RESULTS.md"):
        src = swarm / f
        if src.exists():
            dest = out / "shared" / src.name
            dest.parent.mkdir(exist_ok=True)
            dest.write_text(src.read_text())
    write_json(out / "agent.json", {"name": name, "swarm": namespace, "room": room, "relay": relay,
        "address": names[name], "owner": names["owner"], "keeper": names["keeper"], "execution": execution})
    (out / "env.example").write_text(f"export AGENTNET_URL={shlex.quote(relay)}\n# Supply AGENTNET_TOKEN through your secret store; this kit contains no credentials.\n")
    (out / "join.sh").write_text('''#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if command -v anet >/dev/null; then cmd=(anet)
else cmd=(node "${AGENT_NETWORK:?set AGENT_NETWORK to a built agent-network clone}/packages/cli/bin/anet.mjs"); fi
me=$("${cmd[@]}" whoami --no-inbox)
python3 - agent.json "$me" <<'VERIFY'
import json, sys
expected=json.load(open(sys.argv[1]))["address"].lower()
actual=json.loads(sys.argv[2])["address"].lower()
if actual != expected: raise SystemExit("this identity is not the agent registered in the kit; use its correct home/token")
VERIFY
"${cmd[@]}" contacts --file names.json --no-inbox
''' + f'"${{cmd[@]}}" join {shlex.quote(room)} --wait 60\n')
    (out / "join.sh").chmod(0o755)
    (out / "README.md").write_text("Read PROMPT.md. Supply a relay token out of band, or set AGENT_HOME/AGENT_NAME for your own local identity. "
        "Run join.sh with agent-network supporting contacts. Poll inbox/wait between work steps. "
        "shared/ contains snapshots: it is not a cross-machine live filesystem. Re-export/resync contacts when membership changes. "
        "A different PC uses the same owner and keeper addresses; never copy another agent's identity database.\n")


def allocate_ports(swarm: Path, name: str, requested: int | None = None) -> int:
    """Reserve a stable 100-port block across swarms on this host; skip occupied TCP ports."""
    import fcntl
    state = Path(os.environ.get("SWARM_HOST_STATE", "~/.local/state/swarmkit")).expanduser()
    state.mkdir(parents=True, exist_ok=True)
    key = str(swarm.resolve()) + "/" + name
    with (state / "ports.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        file = state / "ports.json"
        allocations = json.loads(file.read_text()) if file.exists() else {}
        if key in allocations:
            if requested is not None and requested != allocations[key]:
                raise ValueError("port block already reserved with a different base")
            return allocations[key]
        candidates = [requested] if requested is not None else range(9100, 65401, 100)
        for base in candidates:
            if not 1024 <= base <= 65436:
                raise ValueError("port base must leave 100 ports below 65536")
            if any(base < other + 100 and other < base + 100 for other in allocations.values()):
                continue
            sockets = []
            try:
                for port in range(base, base + 100):
                    sock = socket.socket()
                    sockets.append(sock)
                    sock.bind(("0.0.0.0", port))
            except OSError:
                continue
            finally:
                for sock in sockets:
                    sock.close()
            allocations[key] = base
            write_json(file, allocations)
            return base
    raise ValueError("no free 100-port block (or requested block is reserved/in use)")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--swarm-dir", default=os.environ.get("SWARM_DIR", "~/swarms/default"))
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("sync"); s.add_argument("--names")
    r = sub.add_parser("register"); r.add_argument("name"); r.add_argument("--address", required=True)
    e = sub.add_parser("export"); e.add_argument("name"); e.add_argument("--out", required=True)
    e.add_argument("--execution", choices=["sandbox", "local", "remote", "cloud"], default="cloud")
    e.add_argument("--workspace"); e.add_argument("--shared")
    ports = sub.add_parser("ports"); ports.add_argument("name"); ports.add_argument("--base", type=int)
    a = p.parse_args(); swarm = Path(a.swarm_dir).expanduser()
    try:
        if a.command == "sync": sync(swarm, Path(a.names) if a.names else None)
        elif a.command == "register": register(swarm, a.name, a.address)
        elif a.command == "export": export(swarm, a.name, Path(a.out), a.execution, a.workspace, a.shared)
        else: print(allocate_ports(swarm, a.name, a.base))
    except (ValueError, OSError) as err:
        p.exit(1, f"swarm registry: {err}\n")


if __name__ == "__main__":
    main()
