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


def begin_tool(state: dict, tool_id: str) -> None:
    """Capture a tool's input state, not changes made while this chat was idle."""
    pending = state.setdefault("pending_tools", {})
    if tool_id in pending:
        raise ValueError(f"Duplicate PreToolUse for {tool_id}")
    before: dict = {}
    initialize(before, Path(state["root"]), Path(state["config"]))
    pending[tool_id] = before
    state["paired_tracking"] = True


def claim_changes(state: dict, before: dict) -> None:
    owned = set(state["touched"])
    for name in changes(before):
        if name not in owned:
            # Semantic diffs start before THIS tool, including externally updated
            # or preexisting dirty contents, rather than at session startup.
            state["initial"][name] = original(before, name)
            owned.add(name)
    state["touched"] = sorted(owned)


def tool_changes(state: dict, event: str, tool_id: str | None) -> tuple[dict, str | None]:
    """Retain owned paths; missing/interrupted hook pairs stay conservative."""
    error = None
    pending = state.setdefault("pending_tools", {})
    if event == "PostToolUse":
        before = pending.pop(tool_id, None)
        if before is None:
            # Old hosts without IDs retain the original conservative contract.
            # A missing pair on a paired host must not silently excuse a write.
            current = changes(state)
            if tool_id or state.get("paired_tracking"):
                error = "Bully is missing PreToolUse for this tool; checking the session baseline conservatively."
            return current, error
        claim_changes(state, before)
    elif event in ("Stop", "SubagentStop"):
        if not state.get("paired_tracking"):
            return changes(state), None
        # A killed tool may write without producing PostToolUse. Claim its edits
        # once, then close the interval so future external writes are not owned.
        for before in pending.values():
            claim_changes(state, before)
        pending.clear()
    else:
        return {}, None
    root = Path(state["root"])
    return {name: content(root / name) for name in state["touched"]}, error


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
