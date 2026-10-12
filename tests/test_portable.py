"""Real setup scripts with throwaway identities; SDK runs use a local fake model, never a paid endpoint."""
import asyncio
import json
import os
import socket
import subprocess
from pathlib import Path

import pytest
from swarmkit.registry import allocate_ports, export, register, sync
from swarmkit.prompt import render_prompt
from swarmkit.runner import Log, run_turn

KIT = Path(__file__).resolve().parents[1]
PROTOCOL = Path(os.environ.get("TEST_AGENT_NETWORK", KIT.parent.parent / "agent-network"))
ADDR = "0x" + "1" * 40


@pytest.fixture
def swarm(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SWARM_HOST_STATE", str(tmp_path / "host-state"))
    home = tmp_path / "swarms" / "demo"
    env = {**os.environ, "AGENT_NETWORK": str(PROTOCOL), "SWARM_DIR": str(home)}
    mission = tmp_path / "mission.md"; mission.write_text("Prove a reproducible result with raw evidence.")
    subprocess.run(["bash", str(KIT / "bin/swarm-init"), "demo", "--room", "demo-room", "--keeper-address", ADDR,
                    "--mission-file", str(mission)], env=env, check=True, capture_output=True, text=True)
    return home, env


def test_local_setup_without_docker_and_mission_refresh(swarm):
    home, env = swarm
    assert (home / "shared/mission.md").read_text() == (home / "mission.md").read_text()
    subprocess.run(["bash", str(KIT / "bin/swarm-join"), "join", "alice", "--harness", "local", "--lane", "Verify evidence"], env=env, check=True, capture_output=True, text=True)
    names = json.loads((home / "alice/home/names.json").read_text())
    assert names["owner"] == names["demo.owner"]
    assert names["alice"] == names["demo.alice"]
    assert not (home / "alice/home/netd.lock").exists()
    assert "No sandbox or sudo permission is assumed" in (home / "prompts/alice.md").read_text()
    (home / "mission.md").write_text("Changed acceptance criteria")
    subprocess.run(["bash", str(KIT / "bin/swarm-refresh")], env=env, check=True, capture_output=True)
    assert "Changed acceptance criteria" in (home / "prompts/alice.md").read_text()
    assert (home / "shared/mission.md").read_text() == "Changed acceptance criteria"


def test_export_and_worker_pc_reuse_owner_without_copying_keys(swarm, tmp_path):
    home, env = swarm
    register(home, "alice", "0x" + "2" * 40)
    out = tmp_path / "kit"; export(home, "alice", out, "cloud", None, None)
    assert "no automatic sandbox" in (out / "PROMPT.md").read_text()
    assert not list(out.rglob("key")) and not list(out.rglob("*.token"))
    worker = tmp_path / "worker/demo"
    subprocess.run(["bash", str(KIT / "bin/swarm-init"), "demo", "--from", str(out), "--dir", str(worker)],
        env=env, check=True, capture_output=True, text=True)
    assert not (worker / "owner/home/key").exists()
    assert json.loads((worker / "names.json").read_text())["owner"] == json.loads((home / "names.json").read_text())["owner"]
    subprocess.run(["bash", str(KIT / "bin/swarm-init"), "demo", "--from", str(out), "--dir", str(worker)], env=env, check=True, capture_output=True)


def test_registry_rejects_conflicting_import(swarm, tmp_path):
    home, _ = swarm
    register(home, "alice", "0x" + "2" * 40)
    conflict = tmp_path / "names.json"; conflict.write_text(json.dumps({"alice": ADDR}))
    before = (home / "names.json").read_text()
    with pytest.raises(ValueError, match="contact conflict"): sync(home, conflict)
    assert (home / "names.json").read_text() == before


def test_relay_provisioning_is_scoped_and_never_prints_tokens(swarm, tmp_path):
    home, env = swarm
    relay_home = tmp_path / "relay"; relay_home.mkdir()
    shared = {"owner": ADDR}; (relay_home / "names.json").write_text(json.dumps(shared))
    env["RELAY_HOME"] = str(relay_home)
    got = subprocess.run(["bash", str(KIT / "bin/swarm-join"), "join", "alice", "--harness", "relay", "--lane", "Research"],
        env=env, check=True, capture_output=True, text=True)
    token_file = relay_home / "tokens/demo.alice.token"
    token = token_file.read_text().strip()
    assert token not in got.stdout and token not in got.stderr
    scoped = json.loads((relay_home / "identities/demo.alice/names.json").read_text())
    assert scoped["owner"] != ADDR
    assert json.loads((relay_home / "names.json").read_text()) == shared
    assert "no automatic sandbox" in (home / "prompts/alice.md").read_text()


@pytest.mark.parametrize("name", ["shared", "prompts", "observer", "secrets"])
def test_reserved_paths_cannot_expose_identity_keys(swarm, name):
    home, env = swarm
    got = subprocess.run(["bash", str(KIT / "bin/swarm-join"), "join", name, "--harness", "local"], env=env, capture_output=True)
    assert got.returncode != 0 and not (home / name / "home/key").exists()


def test_log_redacts_environment_secrets(tmp_path, monkeypatch):
    secret = "throwaway-secret-for-this-test"
    monkeypatch.setenv("TEST_API_KEY", secret)
    file = tmp_path / "net.jsonl"
    Log(file).write("turn", items=[{"tool_output": "credential=" + secret}])
    assert secret not in file.read_text() and "[redacted]" in file.read_text()


def test_port_blocks_are_host_wide_and_skip_listening_ports(swarm, tmp_path):
    home, _ = swarm
    with socket.socket() as listener:
        listener.bind(("0.0.0.0", 9100))
        first = allocate_ports(home, "alice")
        assert first != 9100
    second = allocate_ports(tmp_path / "other", "alice")
    assert abs(first - second) >= 100
    assert allocate_ports(home, "alice") == first
    with pytest.raises(ValueError): allocate_ports(home, "bob", first)


def test_stale_gpu_lock_does_not_evict_a_running_owner(tmp_path):
    lock = tmp_path / "locks/gpu0"; lock.mkdir(parents=True)
    (lock / "owner").write_text("alice"); (lock / "last_active").write_text("1")
    os.utime(lock, (1, 1))
    env = {**os.environ, "GPU_LOCK_DIR": str(lock.parent), "GPU_LOCK_STALE_MIN": "1"}
    got = subprocess.run(["bash", str(KIT / "shared/gpuclaim.sh"), "0", "take", "bob", "test"], env=env, capture_output=True)
    assert got.returncode == 1 and (lock / "owner").read_text() == "alice"


def test_sdk_turn_records_usage_and_never_exposes_orphan_tool_results(tmp_path):
    from agents import Agent, Model, ModelResponse, SQLiteSession, Usage, set_tracing_disabled
    from openai.types.responses import ResponseOutputMessage, ResponseOutputText
    set_tracing_disabled(True)

    class FakeModel(Model):
        def __init__(self): self.inputs = []
        async def get_response(self, system_instructions, input, *args, **kwargs):
            self.inputs.append(input)
            return ModelResponse(output=[ResponseOutputMessage(id="answer", type="message", role="assistant", status="completed",
                content=[ResponseOutputText(type="output_text", text="measured", annotations=[])])],
                usage=Usage(requests=1, input_tokens=9, output_tokens=1, total_tokens=10), response_id="fake")
        def stream_response(self, *args, **kwargs): raise NotImplementedError

    async def run():
        model = FakeModel(); session = SQLiteSession("test", str(tmp_path / "session.db"))
        await session.add_items([{"type": "function_call_output", "call_id": "missing", "output": "orphan"},
            {"role": "user", "content": "earlier turn"}, {"role": "assistant", "content": "earlier answer"}])
        await run_turn(Agent(name="test", model=model), session, "new turn", 2, Log(tmp_path / "net.jsonl"), "message", session_limit=3)
        assert model.inputs and model.inputs[0][0]["role"] == "user"
        assert len(await session.get_items()) > 3  # durable history retained
    asyncio.run(run())
    record = json.loads((tmp_path / "net.jsonl").read_text())
    assert record["kind"] == "turn" and record["usage"]["total_tokens"] == 10


def test_shell_timeout_returns_partial_output_instead_of_type_error():
    from swarmkit.tools import bash_tool
    tool = bash_tool()
    from agents.tool_context import ToolContext
    args = json.dumps({"command": "printf partial; sleep 3", "timeout_seconds": 1})
    ctx = ToolContext(context=None, tool_name="bash", tool_call_id="test", tool_arguments=args)
    result = asyncio.run(tool.on_invoke_tool(ctx, args))
    assert "exit 124" in result and "partial" in result


def test_parking_retains_the_rest_of_an_inbox_batch(tmp_path, monkeypatch):
    import swarmkit.runner as runner
    from swarmkit.netshim import Message
    home = tmp_path / "worker"; home.mkdir()
    (tmp_path / "mission.md").write_text("Test parking")

    class Net:
        closed = False
        def whoami(self): return {"name": "worker", "address": ADDR, "env": "dev"}
        def join(self, room, wait): return {"ok": True}
        def poll(self, wait): return [Message("one", "peer", "room", "first"), Message("two", "peer", "room", "second")]
        def close(self): self.closed = True

    net = Net()
    monkeypatch.setattr(runner, "connect", lambda *a: net)
    monkeypatch.setattr(runner, "build_agent", lambda *a: object())
    async def turn(*a): return 10
    monkeypatch.setattr(runner, "run_turn", turn)
    args = runner.parse_args(["--name", "worker", "--room", "room", "--swarm-dir", str(tmp_path), "--max-messages", "1"])
    assert asyncio.run(runner.main_async(args)) == 0 and net.closed
    pending = json.loads((home / "pending.json").read_text())
    assert [m["text"] for m in pending] == ["second"]
    assert (home / "pending.json").stat().st_mode & 0o777 == 0o600
    net.closed = False
    net.poll = lambda wait: pytest.fail("restart should process the durable pending message first")
    assert asyncio.run(runner.main_async(args)) == 0
    assert json.loads((home / "pending.json").read_text()) == []
