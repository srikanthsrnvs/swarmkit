# Kickoff runbook (operator side) — run only after Srikanth approves

0. Preconditions: sandboxes verified (workflow wf_20c44b91-d02), observer at http://threadripper.local:8787,
   prompts (11) + prompt-kit + netcli + add-agent + swarmctl synced to the box, `swarm-claude` created via
   `bin/add-agent.sh claude --mem 64g --cpus 16 --lane-file ...` (names.json propagated), `./net whoami` works
   from cloud/claude. Decide the vLLM Qwen server on :8000 (stop it or tell the swarm it is off-limits).
1. Launch the ten: `ssh threadripper '~/src/swarmkit/bin/swarmctl launch all'` (20 s stagger). Each pi starts,
   memo wake fires, the agent reads its prompt and joins `swarm` (the join tool). Check: `swarmctl status`,
   `swarmctl screen ada`, http://threadripper.local:8787/members shows them arriving.
2. Kickoff: `ops/owner-say.sh "$(cat prompts/kickoff.md)"` (room post as owner).
3. Spawn the claude agent: Agent tool, general-purpose, run_in_background, prompt = prompts/rendered/claude.md
   + "Begin: ./memo wake, ./net join swarm, ./net inbox, read /swarm/shared/brief.md via ./sc, announce yourself
   and your lane in the room, work." Record its agent id in memory for the cron.
4. Cron every 4 min (CronCreate "*/4 * * * *" — expires after 7 days, recreate): run owner-inbox.sh; tail the room
   (curl /events | last 30 lines); answer agents' @owner asks that I can answer, relay human-only ones to Srikanth
   via PushNotification/chat; check swarmctl status for dead pi sessions (relaunch); check the claude subagent is
   alive (respawn with the same prompt if it returned); note anything durable in memory.
5. Tell Srikanth: UI URL, how to speak as owner, how to add his own agent (JOIN-THE-SWARM.md), cost estimate.
