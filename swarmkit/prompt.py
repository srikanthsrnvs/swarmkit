"""Render prompts/prompt.template.md for one agent: {{NAME}}, {{LANE}}, {{ROOM}}, {{MISSION}}, {{SWARM}}.
The same substitution prompts/render-prompts.sh does for pi agents, so an SDK agent and a pi agent in one swarm read the
same contract."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

REPO_TEMPLATE = Path(__file__).resolve().parent.parent / "prompts" / "prompt.template.md"
MISSION_PLACEHOLDER = "<no mission yet: the owner will post it in the room; meanwhile read /swarm/shared/README.md and BOARD.md>"


def find_template(explicit: str | None = None) -> Path:
    for cand in ([explicit] if explicit else []) + ["/swarm/prompts/prompt.template.md", str(REPO_TEMPLATE), str(Path(__file__).with_name("prompt.template.md"))]:
        if cand and Path(cand).is_file():
            return Path(cand)
    raise FileNotFoundError("no prompt template (pass --template)")


def find_mission(explicit: str | None, swarm_dir: Path | None) -> str:
    if explicit:
        return Path(explicit).read_text().strip()
    cands = []
    if swarm_dir:
        cands += [str(swarm_dir / "mission.md"), str(swarm_dir / "shared" / "mission.md")]
    cands += ["/swarm/shared/mission.md"]
    for c in cands:
        if c and Path(c).is_file():
            return Path(c).read_text().strip()
    return MISSION_PLACEHOLDER


def render_prompt(*, name: str, lane: str, room: str, template: str | None = None, mission_file: str | None = None,
                  swarm_dir: Path | str | None = None, swarm: str | None = None, execution: str = "sandbox", workspace: str | None = None, shared: str | None = None) -> str:
    swarm_dir = Path(swarm_dir) if swarm_dir else None
    swarm = swarm or os.environ.get("SWARM_NAME") or (swarm_dir.name if swarm_dir and swarm_dir.name != "swarm" else "default")
    contracts = {
        "sandbox": "You work inside your own Docker container. bash runs there. sudo is limited to the container. Check cgroup RAM/CPU caps before large jobs. Ports and GPUs belong to the physical host and are shared.",
        "local": "You work in the current host environment. A shell, when provided, runs on that host. No sandbox or sudo permission is assumed. Follow the operator's filesystem and resource boundaries.",
        "remote": "Use the operator-provided SSH or exec-gateway wrapper for work and measurements on the remote machine. Your local shell describes your local machine. No remote shell exists unless explicitly configured.",
        "cloud": "Your network identity lives on a relay. You have no automatic sandbox, GPU or access to another machine. Use only tools actually provided. Join-kit files are snapshots, not a live shared filesystem. Publish updates through the room or configured shared storage.",
    }
    if execution not in contracts:
        raise ValueError("execution must be sandbox, local, remote or cloud")
    workspace = workspace or ("/swarm/me/work" if execution == "sandbox" else ".")
    shared = shared or ("/swarm/shared" if execution == "sandbox" else str(swarm_dir / "shared") if execution == "local" and swarm_dir else "shared/")
    s = find_template(template).read_text()
    for k, v in {"NAME": name, "LANE": lane.strip(), "ROOM": room, "MISSION": find_mission(mission_file, swarm_dir), "SWARM": swarm, "EXECUTION": contracts[execution], "WORKSPACE": workspace, "SHARED": shared}.items():
        s = s.replace("{{" + k + "}}", v)
    return s


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ("template", "name", "lane", "lane-file", "out", "lanes", "out-dir", "mission-file", "swarm", "workspace", "shared"):
        p.add_argument("--" + flag)
    p.add_argument("--execution", choices=["sandbox", "local", "remote", "cloud"], default="sandbox")
    swarm_dir = Path(os.environ.get("SWARM_DIR", "~/swarms/default")).expanduser()
    p.add_argument("--room", default=(swarm_dir / "room").read_text().strip() if (swarm_dir / "room").exists() else "swarm")
    a = p.parse_args()
    lanes = json.loads(Path(a.lanes).read_text()) if a.lanes else {a.name: Path(a.lane_file).read_text() if a.lane_file else a.lane}
    if not a.lanes and (not a.name or not a.out or not lanes[a.name]):
        p.error("--name, --out and --lane/--lane-file are required")
    for name, lane in lanes.items():
        out = Path(a.out_dir or "rendered") / f"{name}.md" if a.lanes else Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_prompt(name=name, lane=lane, room=a.room, template=a.template, mission_file=a.mission_file,
            swarm_dir=swarm_dir, swarm=a.swarm, execution=a.execution, workspace=a.workspace, shared=a.shared))
        print(f"rendered {out}")

if __name__ == "__main__":
    main()
