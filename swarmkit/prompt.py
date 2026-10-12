"""Render prompts/prompt.template.md for one agent: {{NAME}}, {{LANE}}, {{ROOM}}, {{MISSION}}, {{SWARM}}.
The same substitution prompts/render-prompts.sh does for pi agents, so an SDK agent and a pi agent in one swarm read the
same contract."""
from __future__ import annotations

import os
from pathlib import Path

REPO_TEMPLATE = Path(__file__).resolve().parent.parent / "prompts" / "prompt.template.md"
MISSION_PLACEHOLDER = "<no mission yet: the owner will post it in the room; meanwhile read /swarm/shared/README.md and BOARD.md>"


def find_template(explicit: str | None = None) -> Path:
    for cand in ([explicit] if explicit else []) + ["/swarm/prompts/prompt.template.md", str(REPO_TEMPLATE)]:
        if cand and Path(cand).is_file():
            return Path(cand)
    raise FileNotFoundError("no prompt template (pass --template)")


def find_mission(explicit: str | None, swarm_dir: Path | None) -> str:
    cands = [explicit] if explicit else []
    if swarm_dir:
        cands += [str(swarm_dir / "mission.md"), str(swarm_dir / "shared" / "mission.md")]
    cands += ["/swarm/shared/mission.md"]
    for c in cands:
        if c and Path(c).is_file():
            return Path(c).read_text().strip()
    return MISSION_PLACEHOLDER


def render_prompt(*, name: str, lane: str, room: str, template: str | None = None, mission_file: str | None = None,
                  swarm_dir: Path | str | None = None, swarm: str | None = None) -> str:
    swarm_dir = Path(swarm_dir) if swarm_dir else None
    swarm = swarm or os.environ.get("SWARM_NAME") or (swarm_dir.name if swarm_dir and swarm_dir.name != "swarm" else "default")
    s = find_template(template).read_text()
    for k, v in {"NAME": name, "LANE": lane.strip(), "ROOM": room, "MISSION": find_mission(mission_file, swarm_dir), "SWARM": swarm}.items():
        s = s.replace("{{" + k + "}}", v)
    return s
