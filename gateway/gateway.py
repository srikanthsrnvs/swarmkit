#!/usr/bin/env python3
"""swarmkit exec gateway (OPTIONAL): plain-HTTP front door into one swarm's agent sandboxes; put your own HTTPS tunnel in front.

Listens on 127.0.0.1:8790 only. Every request needs `Authorization: Bearer <token>`; tokens live in
$SWARM_DIR/gateway-tokens.json ({agent-name: token}; default ~/swarms/default) and a token only ever reaches ITS
agent's sandbox `swarmkit-<swarm>-<name>` via `docker exec` (no shell on the host). stdlib only.

  POST /exec    {"cmd": str, "timeout": int (default 600, max 3600), "stdin": str?}
                -> {"exit": int, "stdout": str, "stderr": str, "ms": int}   (exit 124 on timeout)
  POST /upload  {"path": "/swarm/me/...|/swarm/shared/...|/tmp/...", "content": str, "mode": "0644"}
                -> {"ok": true, "bytes": n}
  GET  /health  -> {"ok": true, "agent": name, "container": "swarmkit-<swarm>-<name>", "running": bool}
One log line per request on stdout (run-gateway.sh appends it to $SWARM_DIR/gateway.log); never the token.
"""
import hmac, json, os, re, shlex, subprocess, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST, PORT = "127.0.0.1", 8790
SWARM_DIR = os.path.expanduser(os.environ.get("SWARM_DIR", "~/swarms/default"))
SWARM_NAME = os.path.basename(SWARM_DIR.rstrip("/"))
TOKENS_FILE = os.path.join(SWARM_DIR, "gateway-tokens.json")
CONTAINER_PREFIX = os.environ.get("SWARM_CONTAINER_PREFIX", f"swarmkit-{SWARM_NAME}-")
BODY_LIMIT = 2 * 1024 * 1024          # request body
OUT_LIMIT = 4 * 1024 * 1024           # per stream (stdout / stderr)
TRUNC = "\n...[truncated]"
DEFAULT_TIMEOUT, MAX_TIMEOUT = 600, 3600
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
MODE_RE = re.compile(r"^0?[0-7]{3}$")
UPLOAD_PREFIXES = ("/swarm/me/", "/swarm/shared/", "/tmp/")


def log(agent, status, ms, what):
    what = (what or "").replace("\n", "\\n")[:80]
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} agent={agent} exit={status} ms={ms} cmd={what!r}", flush=True)


def load_tokens():
    try:
        with open(TOKENS_FILE) as f:
            data = json.load(f)
    except Exception as e:  # missing / malformed file => nobody authenticates
        print(f"tokens: cannot read {TOKENS_FILE}: {e}", file=sys.stderr, flush=True)
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and NAME_RE.match(k) and isinstance(v, str) and v}


def authenticate(header):
    """Return agent name for a valid bearer token, else None. Constant-time per token; always walks all tokens."""
    if not header or not header.startswith("Bearer "):
        return None
    presented = header[7:].strip()
    found = None
    for name, tok in load_tokens().items():
        if hmac.compare_digest(presented.encode(), tok.encode()):
            found = name
    return found


def truncate(b):
    if len(b) > OUT_LIMIT:
        b = b[:OUT_LIMIT] + TRUNC.encode()
    return b.decode("utf-8", "replace")


def docker_exec(container, argv_in_container, stdin_bytes, timeout):
    argv = ["docker", "exec", "-i", "-u", "agent", "-w", "/swarm/me/work", container] + argv_in_container
    t0 = time.monotonic()
    try:
        p = subprocess.run(argv, input=stdin_bytes, capture_output=True, timeout=timeout + 30)
        code, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        code, out, err = 124, e.stdout or b"", (e.stderr or b"") + b"\n[gateway] docker exec exceeded timeout\n"
    ms = int((time.monotonic() - t0) * 1000)
    return code, out, err, ms


class Handler(BaseHTTPRequestHandler):
    server_version = "swarmkit-gateway/1"
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # silence default access log (we write our own line)
        pass

    def send_json(self, status, obj):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > BODY_LIMIT:
            return None
        return self.rfile.read(n) if n else b""

    def auth(self):
        agent = authenticate(self.headers.get("Authorization"))
        if agent is None:
            # drain body so the connection stays sane, then 401
            n = int(self.headers.get("Content-Length") or 0)
            if 0 < n <= BODY_LIMIT:
                self.rfile.read(n)
            self.send_json(401, {"error": "unauthorized"})
            log("-", 401, 0, f"{self.command} {self.path}")
        return agent

    def do_GET(self):
        if self.path != "/health":
            self.send_json(404, {"error": "not found"}); log("-", 404, 0, f"GET {self.path}"); return
        agent = self.auth()
        if agent is None:
            return
        container = f"{CONTAINER_PREFIX}{agent}"
        t0 = time.monotonic()
        try:
            r = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", container], capture_output=True, timeout=30)
            running = r.returncode == 0 and r.stdout.strip() == b"true"
        except Exception:
            running = False
        ms = int((time.monotonic() - t0) * 1000)
        self.send_json(200, {"ok": True, "agent": agent, "container": container, "running": running})
        log(agent, 200, ms, "GET /health")

    def do_POST(self):
        if self.path not in ("/exec", "/upload"):
            self.send_json(404, {"error": "not found"}); log("-", 404, 0, f"POST {self.path}"); return
        agent = self.auth()
        if agent is None:
            return
        container = f"{CONTAINER_PREFIX}{agent}"
        raw = self.read_body()
        if raw is None:
            self.send_json(413, {"error": f"body exceeds {BODY_LIMIT} bytes"}); log(agent, 413, 0, self.path); return
        try:
            req = json.loads(raw.decode("utf-8"))
            assert isinstance(req, dict)
        except Exception:
            self.send_json(400, {"error": "body must be a JSON object"}); log(agent, 400, 0, self.path); return

        if self.path == "/exec":
            cmd = req.get("cmd")
            if not isinstance(cmd, str) or not cmd.strip():
                self.send_json(400, {"error": "cmd (string) required"}); log(agent, 400, 0, "exec: no cmd"); return
            try:
                timeout = int(req.get("timeout") or DEFAULT_TIMEOUT)
            except (TypeError, ValueError):
                self.send_json(400, {"error": "timeout must be an integer"}); log(agent, 400, 0, cmd); return
            timeout = max(1, min(timeout, MAX_TIMEOUT))
            stdin = req.get("stdin")
            if stdin is not None and not isinstance(stdin, str):
                self.send_json(400, {"error": "stdin must be a string"}); log(agent, 400, 0, cmd); return
            code, out, err, ms = docker_exec(container, ["timeout", "-k", "5", str(timeout), "bash", "-lc", cmd],
                                             (stdin or "").encode(), timeout)
            self.send_json(200, {"exit": code, "stdout": truncate(out), "stderr": truncate(err), "ms": ms})
            log(agent, code, ms, cmd)
            return

        # /upload
        path, content, mode = req.get("path"), req.get("content"), str(req.get("mode") or "0644")
        if not isinstance(path, str) or not path.startswith(UPLOAD_PREFIXES) or "/../" in path + "/" or "\n" in path:
            self.send_json(400, {"error": "path must be under /swarm/me/, /swarm/shared/ or /tmp/"}); log(agent, 400, 0, f"upload {path}"); return
        if not isinstance(content, str):
            self.send_json(400, {"error": "content (string) required"}); log(agent, 400, 0, f"upload {path}"); return
        if not MODE_RE.match(mode):
            self.send_json(400, {"error": "mode must be octal like 0644"}); log(agent, 400, 0, f"upload {path}"); return
        q = shlex.quote(path)
        script = f"mkdir -p \"$(dirname {q})\" && cat > {q} && chmod {mode} {q}"
        data = content.encode()
        code, out, err, ms = docker_exec(container, ["timeout", "-k", "5", "60", "bash", "-lc", script], data, 60)
        if code == 0:
            self.send_json(200, {"ok": True, "bytes": len(data)})
        else:
            self.send_json(500, {"ok": False, "exit": code, "stderr": truncate(err)})
        log(agent, code, ms, f"upload {path} ({len(data)} bytes)")


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    srv.daemon_threads = True
    print(f"gateway listening on http://{HOST}:{PORT} tokens={TOKENS_FILE} ({len(load_tokens())} agents)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
