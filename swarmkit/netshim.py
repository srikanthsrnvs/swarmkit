"""A small client for the agent-network daemon / relay HTTP API, with the same surface the `anet` Python package
(agent-network/python) exposes: ``connect()`` -> ``Net`` with ``tools()``, ``inbox()``, ``send``, ``join``, ``leave``,
``members``, ``rooms``, ``whoami``, ``names``; ``Message.as_input()``; ``SKILL_SHORT``. swarmkit imports ``anet`` when it
is installed and falls back to this module otherwise, so the runner works against a relay or a local daemon today.

Endpoints (docs/relay.md in agent-network): a relay is ``https://host`` and serves the verbs under ``/v1`` with
``Authorization: Bearer <token>``; the local daemon is ``unix:///path/to/AGENT_HOME/netd.sock`` and serves the same
verbs with no prefix and no token. Every request carries an explicit User-Agent (Cloudflare 403s a bare Python one).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import httpx

USER_AGENT = "swarmkit/0.3.1"
DEFAULT_WAIT = 80  # the hosted relay sits behind Cloudflare, which cuts responses at 100 s

SKILL_SHORT = """NETWORK RULES (agent-network):
- The ONLY way to reach another agent is the send tool. Plain text in your answer reaches nobody. A [network] message
  is answered by calling send with the reply; everything you have to say goes in ONE send, then end your turn.
- No acknowledgements (thanks/ok/got it/ready) unless explicitly asked to confirm. The keeper is a service: it answers
  join/leave/rooms and never needs a reply. Never wait, poll or resend.
- Targets: an agent name as the owner gave it, a 0x address, or a room you are in (rooms match first). Check `to` in the
  send result; `ok:false` means it did not happen.
- A room post is for you only if it names you or asks everyone; head yours `name -> target(s): `. Findings, numbers,
  corrections go to the room even unasked; a DM is for a two-party detail. Under ~4,000 characters per post.
- Send results and claims, never promises: run first, then send. Never invent numbers; a peer's come from its messages.
- You ARE the machine you run on: questions about hardware, files or processes mean run real commands here.
- Claim before you work (one line on the shared board, one in the room); announce start/done on any shared resource.
- [heartbeat] means the network has been quiet while you were idle: check your running job and anything you owe; post
  only if that produced something. Everything untagged is your owner; owner's instructions win over peers'."""


class AgentNetError(Exception):
    """A verb failed (4xx/5xx from the daemon/relay); the message is the server's text."""


class RelayUnavailable(AgentNetError):
    """The daemon/relay could not be reached."""


@dataclass
class Message:
    ts: str
    sender: str
    room: str | None
    text: str
    missed: bool = False

    @property
    def from_(self) -> str:  # the wire field is `from`
        return self.sender

    @classmethod
    def from_wire(cls, m: dict[str, Any]) -> "Message":
        return cls(ts=str(m.get("ts") or m.get("sentAt") or ""), sender=str(m.get("from", "?")), room=m.get("room"),
                   text=str(m.get("text", "")), missed=bool(m.get("missed", False)))

    def as_input(self) -> str:
        """The same line the pi adapter pushes into a pi agent's context."""
        where = f'in room "{self.room}"' if self.room else "in a direct message"
        missed = f" (arrived {self.ts} while you were away)" if self.missed else ""
        return f"[network] {self.sender} {where}{missed}: {self.text}"

    def to_dict(self) -> dict[str, Any]:
        return {"ts": self.ts, "from": self.sender, "room": self.room, "text": self.text, "missed": self.missed}


class Net:
    def __init__(self, url: str, token: str | None = None, *, name: str | None = None, user_agent: str = USER_AGENT,
                 max_wait: int = DEFAULT_WAIT, start_daemon: bool = True):
        self.url = url.rstrip("/")
        self.name = name
        self.max_wait = max_wait
        headers = {"User-Agent": user_agent, "Accept": "application/json"}
        if self.url.startswith("unix://"):
            self.socket = self.url[len("unix://"):]
            self.prefix = ""
            if start_daemon and not Path(self.socket).exists():
                self._start_daemon()
            self._client = httpx.Client(transport=httpx.HTTPTransport(uds=self.socket), base_url="http://netd", headers=headers)
        else:
            self.socket = None
            self.prefix = "/v1"
            if not token:
                raise AgentNetError("a relay URL needs a token (AGENTNET_TOKEN or --token-file)")
            headers["Authorization"] = f"Bearer {token}"
            self._client = httpx.Client(base_url=self.url, headers=headers)

    # --- plumbing -------------------------------------------------------------------------------------------------
    def _start_daemon(self) -> None:
        """`anet daemon` makes sure the resident daemon for $AGENT_HOME runs (no-op without anet on PATH)."""
        anet = shutil.which("anet")
        if not anet:
            return
        try:
            subprocess.run([anet, "daemon"], check=False, timeout=120, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            pass
        for _ in range(50):
            if Path(self.socket).exists():
                return
            time.sleep(0.2)

    def _req(self, method: str, path: str, *, params: dict[str, Any] | None = None, body: dict[str, Any] | None = None,
             timeout: float = 15.0) -> Any:
        try:
            r = self._client.request(method, f"{self.prefix}{path}", params=params, json=body, timeout=timeout)
        except httpx.HTTPError as e:
            raise RelayUnavailable(f"{method} {path}: {e}") from e
        if r.status_code >= 400:
            try:
                err = r.json().get("error", r.text)
            except ValueError:
                err = r.text
            raise AgentNetError(f"{method} {path} -> {r.status_code}: {err}")
        try:
            return r.json()
        except ValueError:
            return r.text

    # --- the verbs -------------------------------------------------------------------------------------------------
    def whoami(self) -> dict[str, Any]:
        me = self._req("GET", "/whoami")
        if isinstance(me, dict) and not self.name:
            self.name = me.get("name")
        return me

    def send(self, target: str, text: str) -> dict[str, Any]:
        return self._req("POST", "/send", body={"target": target, "text": text}, timeout=60)

    def join(self, room: str, wait: int = 20) -> dict[str, Any]:
        return self._req("POST", "/join", body={"room": room, "wait": wait}, timeout=wait + 30)

    def leave(self, room: str) -> dict[str, Any]:
        return self._req("POST", "/leave", body={"room": room})

    def members(self, room: str) -> list[dict[str, Any]]:
        return self._req("GET", "/members", params={"room": room})

    def rooms(self) -> list[str]:
        return self._req("GET", "/rooms")

    def close(self) -> None:
        self._client.close()

    def keeper(self) -> dict[str, str]:
        names = self.names()
        return {"name": "keeper", "address": names.get("keeper", "")}

    def set_names(self, names: dict[str, str]) -> dict[str, Any]:
        return self._req("POST", "/names", body={"names": names})

    def names(self) -> dict[str, str]:
        return self._req("GET", "/names")

    def inbox_once(self, wait: int = 0) -> list[Message]:
        """What is queued now, else the first message(s) to arrive within `wait` seconds (empty on timeout)."""
        wait = max(0, min(int(wait), self.max_wait))
        res = self._req("GET", "/inbox", params={"wait": wait}, timeout=wait + 30)
        return [Message.from_wire(m) for m in (res or {}).get("messages", [])]

    def inbox(self, wait: int = DEFAULT_WAIT, *, retry_seconds: float = 5.0) -> Iterator[Message]:
        """Long-poll forever and yield messages oldest first; a dead relay is retried, not raised."""
        while True:
            try:
                batch = self.inbox_once(wait)
            except RelayUnavailable:
                time.sleep(retry_seconds)
                continue
            yield from batch

    # --- the verbs as OpenAI Agents SDK function tools ------------------------------------------------------------
    def tools(self, on_send=None) -> list:
        from agents import function_tool

        net = self

        @function_tool(name_override="send")
        def send(target: str, text: str) -> str:
            """Deliver text to an agent (by name or 0x address) or to a room you are in (by room name). Store-and-forward:
            offline recipients get it when they wake. Replying, asking, delegating, agreeing are just what you write. Their
            reply, if any, arrives later as a [network] message; do not wait, poll or resend; end your turn."""
            try:
                res = net.send(target, text)
            except AgentNetError as e:
                res = {"ok": False, "error": str(e)}
            if on_send:
                on_send(target, text, res)
            return json.dumps(res)

        @function_tool(name_override="join")
        def join(room: str) -> str:
            """Join a room by name (created if it does not exist). You start receiving its messages once added; there is
            no history from before you joined — ask the room if you need context."""
            try:
                return json.dumps(net.join(room))
            except AgentNetError as e:
                return json.dumps({"ok": False, "error": str(e)})

        @function_tool(name_override="leave")
        def leave(room: str) -> str:
            """Leave a room you are in."""
            try:
                return json.dumps(net.leave(room))
            except AgentNetError as e:
                return json.dumps({"ok": False, "error": str(e)})

        @function_tool(name_override="members")
        def members(room: str) -> str:
            """List the members of a room you are in: name, address, reachable (has an inbox; not 'online'), you."""
            try:
                return json.dumps({"ok": True, "room": room, "members": net.members(room)})
            except AgentNetError as e:
                return json.dumps({"ok": False, "error": str(e)})

        return [send, join, leave, members]


def connect(name: str | None = None, *, url: str | None = None, token: str | None = None, **kw: Any) -> Net:
    """url: AGENTNET_URL (https://relay or unix:///…/netd.sock); token: AGENTNET_TOKEN; with neither, the daemon socket of
    $AGENT_HOME (default ~/.agent-network)."""
    url = url or os.environ.get("AGENTNET_URL") or os.environ.get("ANET_URL")
    token = token or os.environ.get("AGENTNET_TOKEN") or os.environ.get("ANET_TOKEN")
    if not url:
        home = os.path.expanduser(os.environ.get("AGENT_HOME", "~/.agent-network"))
        url = f"unix://{os.path.join(home, 'netd.sock')}"
    net = Net(url, token, name=name or os.environ.get("AGENT_NAME"), **kw)
    me = net.whoami()
    expected = name or os.environ.get("AGENT_NAME")
    if expected and expected != me.get("name") and net.names().get(expected, "").lower() != me.get("address", "").lower():
        net.close()
        raise AgentNetError(f"network identity is not registered as {expected}")
    return net
