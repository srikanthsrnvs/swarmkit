# Worked example: the GLM 5.3 Flash 2-bit swarm (October 2026)

The prompt material of a real 13-agent run on one workstation (ten pi agents on DeepSeek, one Claude agent driven from the
operator's laptop, one OpenAI Codex agent in its cloud, one Claude agent in the pi harness): the mission was to serve
GLM 5.3 Flash locally at 2-bit with its full context under a fixed memory budget and prove it with a coding agent on the
endpoint. Kept verbatim as an example of how specific a mission, its lanes and its kickoff get — not as a template.

- `prompt.template.md`, `lanes.json`, `kickoff.md`, `render-prompts.sh` — the per-agent prompts (`{{NAME}}`, `{{LANE}}`) and the kickoff post
- `derive-agent-prompt.py` — turns a rendered pi prompt into the polling variant for an agent that is not a pi process (Claude Code, Codex)
- `cloud/codex-PROMPT.md`, `cloud/codex-BEGIN.md`, `cloud/claude-BEGIN.md`, `cloud/claude-CRON-PROMPT.md`, `cloud/codex-README.md` — the two cloud agents' standing instructions, opening instructions, the operator's monitoring cron, and the Codex environment set-up of that run (exec gateway over a Cloudflare tunnel; the relay did not exist yet)
- `JOIN-THE-SWARM.md`, `KICKOFF-RUNBOOK.md`, `owner-say.sh`, `owner-inbox.sh` — the operator side of that run (observer at :8787, pre-split paths)

Paths in these files (`~/swarm`, `swarm/netcli.ts`, `packages/pi-extension`, a specific hostname) are the layout of that
run; the current kit uses `~/swarms/<name>`, `anet` and `adapters/pi` (see the repository README).
