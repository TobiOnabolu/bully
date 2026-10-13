"""Git change tracking and locked, per-Codex-session state (POSIX hosts)."""

from __future__ import annotations

import contextlib
import difflib
import hashlib
import json
import os
import subprocess
from pathlib import Path


def digest(value: str) -> str:
    return hashlib.sha256(value.encode(errors="surrogateescape")).hexdigest()


def state_dir() -> Path:
    return Path(os.environ.get("BULLY_CODEX_STATE_DIR", "~/.local/state/bully-codex")).expanduser()


@contextlib.contextmanager
def locked_state(key: str):
    import fcntl

    if len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
        raise ValueError("invalid session key")
    root = state_dir()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / f"{key}.json"
    with (root / f"{key}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(path.read_text()) if path.exists() else {}
        yield state
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state))
        tmp.chmod(0o600)
        tmp.replace(path)


def git(root: Path, *args: str, optional: bool = False) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=15)
    if result.returncode and not optional:
        raise RuntimeError(result.stderr.decode(errors="replace").strip())
    return result.stdout.decode(errors="surrogateescape") if result.returncode == 0 else ""


def content(path: Path) -> str | None:
    if path.is_symlink():
        return "SYMLINK:" + os.readlink(path)
    if not path.exists() or path.is_dir():
        return None
    if path.stat().st_size > 2 * 1024 * 1024:
        # Store only a fingerprint; matching oversized files fail explicitly below.
        return "OVERSIZED:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return path.read_bytes().decode(errors="surrogateescape")


def candidates(root: Path, ref: str) -> set[str]:
    tracked = (
        git(root, "diff", "--no-ext-diff", "--no-renames", "--name-only", "-z", ref, "--")
        if ref
        else git(root, "ls-files", "-z")
    )
    untracked = git(root, "ls-files", "--others", "--exclude-standard", "-z")
    return set(filter(None, (tracked + untracked).split("\0")))


def initialize(state: dict, root: Path, config: Path) -> None:
    if state:
        return
    ref = git(root, "rev-parse", "--verify", "HEAD", optional=True).strip()
    state.update(
        root=str(root),
        config=str(config),
        ref=ref,
        initial={name: content(root / name) for name in candidates(root, ref)},
        touched=[],
        requests={},
        receipts={},
    )


def original(state: dict, name: str) -> str | None:
    if name in state["initial"]:
        return state["initial"][name]
    if not state["ref"]:
        return None
    root = Path(state["root"])
    # A missing blob means a file added during this session.
    exists = git(root, "ls-tree", "--name-only", state["ref"], "--", name)
    return git(root, "show", f"{state['ref']}:{name}") if exists else None


def changes(state: dict) -> dict[str, str | None]:
    root = Path(state["root"])
    names = candidates(root, state["ref"]) | set(state["touched"]) | set(state["initial"])
    current = {}
    for name in sorted(names):
        value = content(root / name)
        if value != original(state, name) or name in state["touched"]:
            current[name] = value
    state["touched"] = list(current)
    return current


def diff_for(state: dict, name: str, value: str | None) -> str:
    before = original(state, name) or ""
    # Normalize line terminators so a missing final newline cannot glue a
    # deletion and addition together and defeat semantic add-line detection.
    return "\n".join(
        difflib.unified_diff(
            before.splitlines(),
            (value or "").splitlines(),
            fromfile=f"a/{name}",
            tofile=f"b/{name}",
            lineterm="",
        )
    )
