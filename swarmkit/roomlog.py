"""Persist observer SSE events, deduplicating ring replay after a reconnect/restart."""
import argparse
import json
import time
import urllib.request
from collections import deque
from pathlib import Path


def key(event):
    return tuple(event.get(k) for k in ("ts", "from", "room", "kind", "text"))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", required=True); p.add_argument("--out", required=True)
    a = p.parse_args(); out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    recent = deque(maxlen=2000)
    if out.exists():
        with out.open("rb") as f:
            f.seek(max(0, out.stat().st_size - 2_000_000))
            for line in f:
                try: recent.append(key(json.loads(line)))
                except (ValueError, UnicodeError): pass
    while True:
        try:
            req = urllib.request.Request(a.url, headers={"User-Agent": "swarmkit-roomlog/1"})
            with urllib.request.urlopen(req, timeout=60) as response, out.open("a") as dest:
                for line in response:
                    if not line.startswith(b"data: "): continue
                    event = json.loads(line[6:]); k = key(event)
                    if k in recent: continue
                    dest.write(json.dumps(event, ensure_ascii=False) + "\n"); dest.flush(); recent.append(k)
        except (OSError, ValueError) as err:
            print(f"room logger reconnecting: {type(err).__name__}", flush=True)
        time.sleep(5)


if __name__ == "__main__": main()
