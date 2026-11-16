"""Cross-machine mailbox for Claude sessions, kept on the hub devboxes (~/peer-inbox on dev4, dev5).

Sessions on different Macs (K65, mbp14) cannot reach each other with the native
SendMessage, which crosses machines only over Remote Control on one claude.ai account,
while K65 rotates accounts with cswap. Both Macs reach the devboxes, so each session gets a
directory there and a message is a file in it. Deployed by `peer deploy`; driven over ssh:

    python3 peerbox.py put <to> <from> <host> <b64>   # body base64 in argv; prints the message id
    python3 peerbox.py follow <name> <host>       # one JSON line per message; `ack <id>` on stdin
    python3 peerbox.py list

follow moves a message to done/ only after `ack <id>` arrives (the channel pushed it into the
session), so a message sent while the link was down is pushed again by the next follower.
One follower per name: a new one ends the old (dev4 does not notice a dropped ssh). It exits
when stdin ends, so a killed ssh leaves nothing behind.

The body travels in argv, not stdin: over a multiplexed ssh connection, piping stdin adds about
a second before the remote side sees EOF (measured 2026-11-16: 1.5 s vs 0.5 s per send).
Several hubs can run this (dev4, dev5); each message lives on the one hub it was put on.
"""
import base64
import contextlib
import json
import os
import re
import signal
import sys
import threading
import time
import uuid
from pathlib import Path

ROOT = Path.home() / "peer-inbox"
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


def box(name):
    if not NAME.fullmatch(name):
        sys.exit(f"peerbox: bad session name {name!r}")
    d = ROOT / name
    (d / "new").mkdir(parents=True, exist_ok=True)
    (d / "done").mkdir(exist_ok=True)
    return d


def put(to, sender, host, b64):
    d = box(to)
    box(sender)  # so the recipient can always answer
    body = base64.b64decode(b64).decode()
    if not body.strip():
        sys.exit("peerbox: empty message")
    mid = f"{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    msg = {"id": mid, "to": to, "from": sender, "host": host, "sent": time.time(), "body": body}
    tmp = d / f".{mid}.tmp"
    tmp.write_text(json.dumps(msg, ensure_ascii=False))
    tmp.rename(d / "new" / f"{mid}.json")
    print(mid)


def follow(name, host):
    d = box(name)
    pidfile = d / "follow.pid"
    with contextlib.suppress(FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        old = int(pidfile.read_text())
        if old != os.getpid() and b"peerbox.py" in Path(f"/proc/{old}/cmdline").read_bytes():
            os.kill(old, signal.SIGTERM)
    pidfile.write_text(str(os.getpid()))
    (d / "info.json").write_text(json.dumps({"host": host, "since": time.time()}))

    def acks():
        for line in sys.stdin:
            if line.startswith("ack "):
                mid = line.split()[1]
                with contextlib.suppress(FileNotFoundError):
                    (d / "new" / f"{mid}.json").rename(d / "done" / f"{mid}.json")
        os._exit(0)

    threading.Thread(target=acks, daemon=True).start()
    sent = set()
    while True:
        for f in sorted((d / "new").glob("*.json")):
            if f.name in sent:
                continue
            with contextlib.suppress(FileNotFoundError, ValueError):
                print(json.dumps(json.loads(f.read_text()), ensure_ascii=False), flush=True)
                sent.add(f.name)
        time.sleep(0.1)  # a listdir of a few files: cheap, and well under a model turn


def follower_alive(d):
    with contextlib.suppress(FileNotFoundError, ValueError, PermissionError):
        pid = int((d / "follow.pid").read_text())
        return b"peerbox.py" in Path(f"/proc/{pid}/cmdline").read_bytes()
    return False


def list_():
    for d in sorted(p for p in ROOT.glob("*") if p.is_dir()):
        info = {}
        with contextlib.suppress(FileNotFoundError, ValueError):
            info = json.loads((d / "info.json").read_text())
        state = "online" if follower_alive(d) else "offline"
        pending = len(list((d / "new").glob("*.json")))
        print(f"{d.name}\t{info.get('host', '-')}\t{state}\t{pending} pending")


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    {"put": put, "follow": follow, "list": list_}[cmd](*args)
