# Swarm "{{SWARM}}" — shared conventions

Room: {{ROOM}}. The operator is the scoped contact `owner`. Mission: mission.md.
Your rendered prompt describes your execution environment; being in this swarm does not imply owning a Docker sandbox.

## Durable state

BOARD.md records claims, roles and resource windows. RESULTS.md records measurements and raw-log pointers.
RUNBOOK.md records reproduction. Read current state before acting and after compaction. Claims and results name their host.
If there is no shared filesystem across PCs, appoint a ledger keeper and publish updates through the room or configured
storage. A join kit contains snapshots, not a live shared directory. Never store credentials in shared files.

## Sandbox hosts

When explicitly provided, /swarm/me is your persistent private directory, /swarm/shared is the host's shared mount,
and /swarm/prompts is read-only. bash runs inside the sandbox; sudo there does not grant host access.
Read cgroup RAM/CPU caps and status/host.txt before large jobs. Limits are ceilings, not reservations. SWARM_CPUS reflects
initial allocation; cgroup cpu.max is authoritative after a live limit change. Download shared models once and assign
one owner per build. Keep long jobs detached with logs and resume commands.

GPU claims are host-local and shared across swarms controlled by the same host state directory. Take with gpuclaim.sh,
refresh long claims, release promptly, and set CUDA_VISIBLE_DEVICES to the held devices. A stale timer cannot prove a job
is dead, so it never automatically evicts another owner. Use assigned host-wide port blocks and announce served ports.
On another PC, use that PC's locks, caps and port assignments. No peer's processes, files, venvs or claims may be changed.

## Evidence and communication

Only send delivers. Findings and warnings go to the room with exact inputs, versions, conditions and raw evidence.
Keep long material in accessible storage with a pointer and summary. Correct mistakes openly; verify major findings
independently. Send operator requests to owner and follow the mission's stop/continue policy.
