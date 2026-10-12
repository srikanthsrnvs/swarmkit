"""One swarm agent on the OpenAI Agents SDK: an inbound network message becomes one `Runner.run` turn.

    python -m swarmkit.run --name alice --lane "…" --model deepseek-flash --base-url https://api.deepseek.com/v1 \
        --api-key-env DEEPSEEK_API_KEY [--relay URL --token-file F | (AGENT_HOME + `anet daemon`)] [--room swarm]

What the SDK gives us and where it is used here: `Agent` (instructions = rendered prompt + anet.SKILL_SHORT, tools =
net.tools(), model = OpenAIChatCompletionsModel over any OpenAI-compatible endpoint), `Runner.run(..., session=…,
max_turns=N)` per message, `SQLiteSession` per agent under the swarm home (history across turns and restarts), tracing
(on when OPENAI_API_KEY is set, else `set_tracing_disabled`). What agent-network gives us: `anet.connect()` → inbox()
long-poll, the four verbs as FunctionTools, Message.as_input(). The heartbeat (one turn with a [heartbeat] input after
H quiet minutes) and the jsonl log of sends/receives are this file's.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:  # the anet Python package from agent-network (pip install -e ../agent-network/python), else the built-in client
    import anet  # type: ignore
    NET_IMPL = "anet"
except ImportError:  # pragma: no cover
    from swarmkit import netshim as anet  # type: ignore
    NET_IMPL = "swarmkit.netshim"

from swarmkit.prompt import render_prompt

HARNESS_NOTE = """HOW YOU RUN (this harness): you are an OpenAI Agents SDK agent in your sandbox. Each [network] message is one
turn: read it, use your tools, and when you have something to say call send; then end the turn. Your tools are exactly:
send, join, leave, members{bash}. There is no separate read/write/edit/grep tool{bash_hint}. Never report a number you did
not measure with a tool call in this turn."""

HEARTBEAT_TEXT = ("[heartbeat] {minutes} minutes with no network activity while you were idle. Check your running job, the "
                  "shared board and anything you owe; post only if that check produced something.")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Log:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path

    def write(self, kind: str, **fields) -> None:
        rec = {"ts": now(), "kind": kind, **fields}
        with self.path.open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        sys.stderr.write(f"[{rec['ts']}] {kind} {json.dumps({k: v for k, v in fields.items() if k != 'items'}, ensure_ascii=False)[:400]}\n")
        sys.stderr.flush()


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m swarmkit.run", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", required=True, help="agent name (also the SQLite session id)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--lane", default=None, help="the agent's starting lane (one paragraph)")
    g.add_argument("--lane-file", default=None)
    p.add_argument("--template", default=None, help="prompt template (default: /swarm/prompts/prompt.template.md, else the repo's prompts/)")
    p.add_argument("--mission-file", default=None, help="{{MISSION}} text (default: <swarm-dir>/mission.md or /swarm/shared/mission.md)")
    p.add_argument("--room", default=os.environ.get("SWARM_ROOM", "swarm"), help="room to join at start (default $SWARM_ROOM or swarm)")
    p.add_argument("--no-join", action="store_true")
    p.add_argument("--swarm-dir", default=os.environ.get("SWARM_DIR", "/swarm" if Path("/swarm/me").is_dir() else os.path.expanduser("~/swarms/default")))
    p.add_argument("--home", default=None, help="this agent's directory for sessions.db and net.jsonl (default <swarm-dir>/me or <swarm-dir>/<name>)")
    p.add_argument("--model", default="deepseek-flash")
    p.add_argument("--base-url", default="https://api.deepseek.com/v1")
    p.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    p.add_argument("--relay", default=None, help="AGENTNET_URL: https://relay… or unix:///…/netd.sock (default: $AGENTNET_URL, else $AGENT_HOME/netd.sock)")
    p.add_argument("--token-file", default=None, help="file holding the relay bearer token (never pass the token on the command line)")
    p.add_argument("--max-turns", type=int, default=8, help="SDK max_turns per inbound message")
    p.add_argument("--heartbeat-minutes", type=float, default=float(os.environ.get("AGENT_HEARTBEAT_MINUTES", 20)))
    p.add_argument("--wait", type=int, default=80, help="inbox long-poll seconds per request (≤80 behind Cloudflare)")
    p.add_argument("--announce", default=None, help="a first room post sent before the loop (no model turn)")
    p.add_argument("--max-messages", type=int, default=0, help="exit after this many model turns (smoke tests); 0 = forever")
    p.add_argument("--idle-exit", type=float, default=0, help="exit when nothing arrived for this many seconds (smoke tests); 0 = never")
    p.add_argument("--no-bash", action="store_true", help="do not give the agent the bash tool (its own sandbox's shell)")
    p.add_argument("--skip-keeper", action="store_true", default=True, help="log keeper confirmations without a model turn (default)")
    p.add_argument("--turn-on-keeper", dest="skip_keeper", action="store_false")
    return p.parse_args(argv)


def connect(name: str, url: str | None, token_file: str | None):
    """anet.connect in whichever spelling the installed package has; env is the common denominator."""
    token = None
    if token_file:
        token = Path(os.path.expanduser(token_file)).read_text().strip()
        os.environ["AGENTNET_TOKEN"] = token
    if url:
        os.environ["AGENTNET_URL"] = url
    for call in (lambda: anet.connect(name, url=url, token=token), lambda: anet.connect(name), lambda: anet.connect()):
        try:
            return call()
        except TypeError:
            continue
    raise SystemExit("anet.connect: no supported signature")


def build_agent(args: argparse.Namespace, net, instructions: str):
    from agents import Agent, OpenAIChatCompletionsModel, set_tracing_disabled
    from openai import AsyncOpenAI

    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit(f"{args.api_key_env} is not set (the provider API key; the sandbox gets it from <swarm>/env)")
    if not os.environ.get("OPENAI_API_KEY"):
        set_tracing_disabled(True)  # traces are uploaded to OpenAI only when their key exists
    client = AsyncOpenAI(base_url=args.base_url, api_key=api_key)
    model = OpenAIChatCompletionsModel(model=args.model, openai_client=client)
    tools = list(net.tools())
    if not args.no_bash:
        from swarmkit.tools import bash_tool
        tools.append(bash_tool())
    return Agent(name=args.name, instructions=instructions, tools=tools, model=model)


def summarize_items(result) -> list[dict]:
    """Tool calls and messages of one turn, for the jsonl log (works for any tools, ours or the anet package's)."""
    out = []
    for item in getattr(result, "new_items", []) or []:
        kind = type(item).__name__
        raw = getattr(item, "raw_item", None)
        if kind == "ToolCallItem":
            out.append({"tool": getattr(raw, "name", None), "args": getattr(raw, "arguments", None)})
        elif kind == "ToolCallOutputItem":
            o = getattr(item, "output", None)
            out.append({"tool_output": (o if isinstance(o, str) else json.dumps(o, default=str))[:500]})
        elif kind == "MessageOutputItem":
            try:
                from agents import ItemHelpers
                out.append({"message": ItemHelpers.text_message_output(item)[:500]})
            except Exception:  # pragma: no cover
                out.append({"message": str(raw)[:500]})
    return out


async def run_turn(agent, session, text: str, max_turns: int, log: Log, kind: str) -> None:
    from agents import Runner

    t0 = time.time()
    try:
        result = await Runner.run(agent, text, session=session, max_turns=max_turns)
        log.write("turn", trigger=kind, seconds=round(time.time() - t0, 1), final=str(result.final_output)[:1000], items=summarize_items(result))
    except Exception as e:  # a failed turn must not kill the loop; the message is already in the session
        log.write("error", trigger=kind, seconds=round(time.time() - t0, 1), error=f"{type(e).__name__}: {e}"[:800])


async def main_async(args: argparse.Namespace) -> int:
    from agents import SQLiteSession

    swarm_dir = Path(args.swarm_dir)
    home = Path(args.home) if args.home else (swarm_dir / "me" if (swarm_dir / "me").is_dir() else swarm_dir / args.name)
    home.mkdir(parents=True, exist_ok=True)
    log = Log(home / "net.jsonl")

    lane = Path(args.lane_file).read_text() if args.lane_file else (args.lane or "GENERALIST: read the shared board, take the most valuable unclaimed task, claim it in the room, do it.")
    harness = HARNESS_NOTE.format(bash="" if args.no_bash else ", bash", bash_hint="" if args.no_bash else " — bash does all of that")
    instructions = render_prompt(name=args.name, lane=lane, room=args.room, template=args.template, mission_file=args.mission_file,
                                 swarm_dir=swarm_dir) + "\n\n" + harness + "\n\n" + anet.SKILL_SHORT

    net = connect(args.name, args.relay, args.token_file)
    me = net.whoami()
    log.write("start", net=NET_IMPL, whoami={k: me.get(k) for k in ("name", "address", "env")} if isinstance(me, dict) else str(me),
              model=args.model, base_url=args.base_url, room=args.room, home=str(home))
    if not args.no_join:
        try:
            log.write("join", room=args.room, result=net.join(args.room))
        except Exception as e:
            log.write("error", trigger="join", error=str(e)[:400])
    if args.announce:
        log.write("send", target=args.room, text=args.announce, result=net.send(args.room, args.announce))

    agent = build_agent(args, net, instructions)
    session = SQLiteSession(args.name, str(home / "sessions.db"))

    turns = 0
    last_activity = time.time()
    last_heartbeat = time.time()
    heartbeat_s = args.heartbeat_minutes * 60 if args.heartbeat_minutes > 0 else 0
    while True:
        wait = args.wait
        if heartbeat_s:
            wait = max(1, min(wait, int(heartbeat_s - (time.time() - max(last_activity, last_heartbeat))) + 1))
        if args.idle_exit:
            wait = max(1, min(wait, int(args.idle_exit - (time.time() - last_activity)) + 1))
        try:
            batch = await asyncio.to_thread(net.inbox_once, wait) if hasattr(net, "inbox_once") else await asyncio.to_thread(lambda: list(_take_one(net.inbox(wait))))
        except Exception as e:
            log.write("error", trigger="inbox", error=str(e)[:400])
            await asyncio.sleep(5)
            continue
        for msg in batch:
            last_activity = time.time()
            wire = msg.to_dict() if hasattr(msg, "to_dict") else {"text": str(msg)}
            log.write("recv", **{("msg_ts" if k == "ts" else k): v for k, v in wire.items()})
            sender = (getattr(msg, "sender", None) or getattr(msg, "from_", None) or "").lower()
            if args.skip_keeper and sender == "keeper":
                continue
            await run_turn(agent, session, msg.as_input(), args.max_turns, log, "message")
            turns += 1
            if args.max_messages and turns >= args.max_messages:
                log.write("exit", reason=f"max-messages {args.max_messages} reached")
                return 0
        idle = time.time() - last_activity
        if heartbeat_s and idle >= heartbeat_s and time.time() - last_heartbeat >= heartbeat_s:
            last_heartbeat = time.time()
            await run_turn(agent, session, HEARTBEAT_TEXT.format(minutes=int(idle // 60)), args.max_turns, log, "heartbeat")
        if args.idle_exit and idle >= args.idle_exit:
            log.write("exit", reason=f"idle for {int(idle)} s")
            return 0


def _take_one(it):
    """For an inbox() that is only an iterator: one message per poll."""
    for m in it:
        yield m
        return


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        return asyncio.run(main_async(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
