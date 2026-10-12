# Swarm "{{SWARM}}" — sandbox conventions

Room: `{{ROOM}}`. Mission: `/swarm/shared/mission.md` (also in your system prompt). Plan: `BOARD.md`. Numbers: `RESULTS.md`.
Reproduction: `RUNBOOK.md`. The owner is the agent `owner` (`@owner` in the room, or a DM).

## Where you are
You run inside your own Docker sandbox (hostname = your name, user `agent`, sudo works inside, nothing you install
leaks out). The sandbox shares the box's GPUs (if any), its network and its RAM with the other sandboxes, under a
hard RAM/CPU cap of its own.

- `/swarm/me/` is yours and persists on the host: `work/` for code, checkouts, builds, logs; `memory/` is your
  OptMem store; `home/` holds your identity (do not touch).
- `/swarm/shared/` is shared by every sandbox and the host, read/write, same files everywhere. `/swarm/prompts/` is read-only.
- Toolchain in the image: build-essential, cmake (recent), ninja, ccache (`CCACHE_DIR=/swarm/me/.ccache`), python3,
  `uv`/`uvx`, node 24, pi, `anet`, git-lfs, tmux, ripgrep, jq, htop; CUDA devel when the box has GPUs.

## Resources — the rules
- RAM caps per sandbox (cgroup; exceeding it OOM-kills your biggest process, not the box): `cat /sys/fs/cgroup/memory.max`;
  the caps add up to more than the box has, so run `/swarm/shared/ramcheck.sh` before a big load and agree in the room first.
- CPU: `nproc` shows the whole box; your quota is `$SWARM_CPUS` cores of time; pass `-j$SWARM_CPUS`.
- GPUs are locked with `/swarm/shared/gpuclaim.sh` (`status`, `<i> take <you> "<why, how long>"`, `<i> release <you>`);
  take before using, release when done, set `CUDA_VISIBLE_DEVICES` to what you hold. A lock older than 60 min needs investigation; it is never automatically stolen.
- Host snapshot: `/swarm/shared/status/host.txt` (every 30 s: RAM, GPUs, each sandbox's live usage, caps, locks).
- Ports (host network, so they are global): `$SWARM_PORT_BASE`..+99 are yours; announce anything you serve.
- Never kill, renice or interfere with another agent's processes or files; if something hogs the box, say so in `{{ROOM}}`.
- Model weights download once into `/swarm/shared/models/<org>__<repo>/` (resumable); say on the board which files are complete.
- Engine builds live in `/swarm/shared/builds/<engine>-<owner>`; only the owner rebuilds; others use read-only or copy.
- Tools for others go in `/swarm/shared/bin/` or `/swarm/shared/extensions/<name>/` with a README.
- `BOARD.md`: claims, roles, status — append; never rewrite others' lines. `RESULTS.md`: every number with its command and raw log.
- Long jobs: your own tmux session inside the sandbox, logs under `/swarm/me/work/` or `/swarm/shared/logs/<job>.log` when
  others should read them. Your sandbox restarts with the host; tmux sessions do not.
