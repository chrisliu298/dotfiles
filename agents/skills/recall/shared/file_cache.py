"""Small per-transcript cache for already redacted recall turns.

Enabled only when RECALL_CACHE_DIR is set. Cache files are private, versioned,
and invalidated by the source file's size and nanosecond mtime.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Callable, TypeVar


T = TypeVar("T")


def get_or_build(path: Path, namespace: str, version: int, build: Callable[[], T]) -> T:
    root = os.environ.get("RECALL_CACHE_DIR")
    if not root:
        return build()
    try:
        stat = path.stat()
        base = Path(root).expanduser()
        base.mkdir(mode=0o700, parents=True, exist_ok=True)
        base.chmod(0o700)
        directory = base / namespace
        directory.mkdir(mode=0o700, exist_ok=True)
        directory.chmod(0o700)
        key = hashlib.sha256(str(path.resolve()).encode()).hexdigest()
        target = directory / f"{key}.json"
        stamp = [version, stat.st_size, stat.st_mtime_ns]
        try:
            cached = json.loads(target.read_text())
            if cached.get("stamp") == stamp:
                return cached["data"]
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            pass
        data = build()
        fd, temporary = tempfile.mkstemp(prefix=".recall-", dir=directory)
        try:
            with os.fdopen(fd, "w") as output:
                json.dump({"stamp": stamp, "data": data}, output, ensure_ascii=False)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return data
    except OSError:
        return build()
