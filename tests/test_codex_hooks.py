"""Black-box Codex hook contract probes against real Git repos and Bully scripts."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SOURCE = str(Path(__file__).resolve().parents[1] / "src")
ENTRY = [sys.executable, "-c", "from bully.codex import main; main()"]
SCRIPT_CONFIG = """schema_version: 1
rules:
  syntax:
    description: Shell syntax must be valid.
    engine: script
    scope: ["*.sh"]
    severity: error
    script: "bash -n {file}"
"""
SEMANTIC_CONFIG = """schema_version: 1
rules:
  no-eval:
    description: Do not add calls to eval.
    engine: semantic
    scope: ["*.js"]
    severity: error
"""


class Workspace:
    def __init__(self, path):
        self.path = path / "repo"
        self.path.mkdir()
        self.env = os.environ.copy()
        self.env.pop("BULLY_TRUST_ALL", None)
        self.env.update(
            PYTHONPATH=SOURCE,
            BULLY_TRUST_STORE=str(path / "trust.json"),
            BULLY_CODEX_STATE_DIR=str(path / "state"),
        )
        self.git("init", "-q")
        self.git("config", "user.email", "probe@example.test")
        self.git("config", "user.name", "Bully Probe")
        self.write(".bully.yml", SCRIPT_CONFIG)
        self.write("one.sh", "echo initial\n")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        self.trust()

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.path, check=True, capture_output=True, text=True
        )

    def write(self, name, text):
        (self.path / name).parent.mkdir(parents=True, exist_ok=True)
        (self.path / name).write_text(text)

    def run(self, *args, payload=None):
        return subprocess.run(
            [*ENTRY, *args],
            cwd=self.path,
            env=self.env,
            input=json.dumps(payload) if payload else "",
            capture_output=True,
            text=True,
        )

    def trust(self):
        subprocess.run(
            [sys.executable, "-m", "bully", "trust"],
            cwd=self.path,
            env=self.env,
            check=True,
            capture_output=True,
        )

    def hook(self, event="PostToolUse", session="probe", **extra):
        result = self.run(
            "hook",
            payload={
                "hook_event_name": event,
                "session_id": session,
                "cwd": str(self.path),
                **extra,
            },
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    def receipt(self, verdict="pass", reason="The changed expression is a safe literal."):
        state_path = next(Path(self.env["BULLY_CODEX_STATE_DIR"]).glob("*.json"))
        state = json.loads(state_path.read_text())
        request = list(state["requests"])[-1]
        return self.run(
            "verdict",
            "--session",
            state_path.stem,
            "--request",
            request,
            "--rule",
            "no-eval",
            "--verdict",
            verdict,
            "--reason",
            reason,
        )


@pytest.fixture
def ws(tmp_path):
    return Workspace(tmp_path)


def test_multiple_files_and_spaces_block_then_recover(ws):
    assert ws.hook("SessionStart") == {}
    ws.write("one.sh", "echo good\n")
    ws.write("two space.sh", "if then\n")
    out = ws.hook(tool_name="apply_patch", tool_input={"command": "*** Begin Patch\n*** End Patch"})
    assert out["decision"] == "block" and "syntax" in out["reason"]
    assert ws.hook("Stop")["decision"] == "block"
    ws.write("two space.sh", "echo fixed\n")
    assert ws.hook() == {}
    assert ws.hook("Stop") == {}


def test_shell_write_and_commit_in_same_tool_cannot_hide_failure(ws):
    ws.hook("PreToolUse", tool_name="Bash")
    ws.write("one.sh", "if then\n")
    ws.git("add", "one.sh")
    ws.git("commit", "-qm", "bad edit")
    assert ws.hook(tool_name="Bash")["decision"] == "block"


def test_existing_dirty_file_is_ignored_until_changed(ws):
    ws.write("one.sh", "if then\n")
    ws.hook("SessionStart")
    assert ws.hook("Stop") == {}
    ws.write("one.sh", "if then broken\n")
    assert ws.hook()["decision"] == "block"


def test_stop_rechecks_dependencies_without_content_cache(ws):
    ws.write(".bully.yml", SCRIPT_CONFIG.replace("bash -n {file}", "test ! -f broken-dependency"))
    ws.trust()
    ws.hook("SessionStart")
    ws.write("one.sh", "echo changed\n")
    assert ws.hook() == {}
    ws.write("broken-dependency", "broken")
    assert ws.hook("Stop")["decision"] == "block"


def test_deleted_source_runs_project_wide_rules(ws):
    ws.write(".bully.yml", SCRIPT_CONFIG.replace("bash -n {file}", "test -f one.sh"))
    ws.trust()
    ws.hook("SessionStart")
    (ws.path / "one.sh").unlink()
    assert ws.hook()["decision"] == "block"


def test_untrusted_config_never_executes_and_blocks_completion(ws):
    ws.hook("SessionStart")
    ws.write(".bully.yml", SCRIPT_CONFIG.replace("bash -n {file}", "touch EXECUTED"))
    ws.write("one.sh", "echo changed\n")
    assert "mismatch" in ws.hook()["reason"]
    assert not (ws.path / "EXECUTED").exists()
    assert ws.hook("Stop")["decision"] == "block"


def test_config_removal_cannot_disable_gate_mid_session(ws):
    ws.hook("SessionStart")
    (ws.path / ".bully.yml").unlink()
    assert "disappeared" in ws.hook("Stop")["reason"]


def test_semantic_pending_and_passing_receipt(ws):
    ws.write(".bully.yml", SEMANTIC_CONFIG)
    ws.trust()
    ws.hook("SessionStart")
    ws.write("new.js", "const value = 1;\n")
    assert "SEMANTIC REVIEW REQUIRED" in ws.hook()["reason"]
    assert ws.hook("Stop")["decision"] == "block"
    result = ws.receipt()
    assert result.returncode == 0, result.stderr
    assert ws.hook("Stop") == {}


def test_semantic_violation_and_stale_receipt(ws):
    ws.write(".bully.yml", SEMANTIC_CONFIG)
    ws.trust()
    ws.hook("SessionStart")
    ws.write("new.js", "eval(input);\n")
    ws.hook()
    assert ws.receipt("violation", "Added eval(input).").returncode == 0
    assert "Added eval(input)" in ws.hook("Stop")["reason"]
    ws.write("new.js", "const value = 1;\n")
    assert ws.receipt().returncode == 1
    assert "SEMANTIC REVIEW REQUIRED" in ws.hook()["reason"]
    assert ws.receipt().returncode == 0
    assert ws.hook("Stop") == {}


def test_semantic_receipt_invalidated_by_config_change(ws):
    ws.write(".bully.yml", SEMANTIC_CONFIG)
    ws.trust()
    ws.hook("SessionStart")
    ws.write("new.js", "const value = 1;\n")
    ws.hook()
    assert ws.receipt().returncode == 0
    ws.write(".bully.yml", SEMANTIC_CONFIG.replace("calls to eval", "any constants"))
    ws.trust()
    assert "SEMANTIC REVIEW REQUIRED" in ws.hook("Stop")["reason"]


def test_semantic_addition_without_final_newline_is_not_skipped(ws):
    ws.write(".bully.yml", SEMANTIC_CONFIG)
    ws.write("new.js", "const value = 1;")
    ws.trust()
    ws.hook("SessionStart")
    ws.write("new.js", "eval(input);")
    out = ws.hook()
    assert "SEMANTIC REVIEW REQUIRED" in out["reason"]
    assert "+eval(input);" in out["reason"]


def test_sessions_are_isolated(ws):
    ws.hook("SessionStart", session="first")
    ws.write("one.sh", "if then\n")
    assert ws.hook(session="first")["decision"] == "block"
    ws.hook("SessionStart", session="second")
    assert ws.hook("Stop", session="second") == {}
    assert ws.hook("Stop", session="first")["decision"] == "block"


def test_session_requirement_tracks_deletions(ws):
    ws.write(
        ".bully.yml",
        """schema_version: 1
rules:
  tests-required:
    description: Source changes require tests.
    engine: session
    scope: ["*.sh"]
    severity: error
    when:
      changed_any: ["*.sh"]
    require:
      changed_any: ["test.txt"]
""",
    )
    ws.trust()
    ws.hook("SessionStart")
    (ws.path / "one.sh").unlink()
    assert "tests-required" in ws.hook("Stop")["reason"]
    ws.write("test.txt", "covered")
    assert ws.hook("Stop") == {}


def test_no_config_no_enforcement(ws):
    (ws.path / ".bully.yml").unlink()
    assert ws.hook("SessionStart") == {}
    ws.write("one.sh", "if then\n")
    assert ws.hook("Stop") == {}


def test_restoring_preexisting_dirty_file_is_a_change(ws):
    ws.write("one.sh", "echo dirty\n")
    ws.hook("SessionStart")
    ws.write("one.sh", "echo initial\n")
    ws.hook()
    state = json.loads(next(Path(ws.env["BULLY_CODEX_STATE_DIR"]).glob("*.json")).read_text())
    assert "one.sh" in state["touched"]


def test_invalid_config_blocks_instead_of_silently_passing(ws):
    ws.hook("SessionStart")
    ws.write(".bully.yml", SCRIPT_CONFIG.replace("engine: script", "engine: unknown"))
    ws.trust()
    ws.write("one.sh", "echo changed\n")
    out = ws.hook("Stop")
    assert out["decision"] == "block" and "ConfigError" in out["reason"]


def test_binary_file_outside_rule_scope_does_not_break_gate(ws):
    ws.hook("SessionStart")
    (ws.path / "image.bin").write_bytes(b"\xff\x80\x00")
    assert ws.hook("Stop") == {}


def test_staged_changes_are_checked(ws):
    ws.hook("SessionStart")
    ws.write("one.sh", "if then\n")
    ws.git("add", "one.sh")
    assert ws.hook("Stop")["decision"] == "block"


def test_missing_ast_executable_blocks_instead_of_skipping(ws):
    ws.write(
        ".bully.yml",
        """schema_version: 1
rules:
  no-eval:
    description: Avoid eval.
    engine: ast
    scope: ["*.js"]
    severity: error
    pattern: "eval($ARG)"
""",
    )
    ws.trust()
    ws.env["PATH"] = "/usr/bin:/bin"
    ws.hook("SessionStart")
    ws.write("new.js", "eval(input);\n")
    out = ws.hook("Stop")
    assert out["decision"] == "block" and "install ast-grep" in out["reason"]


def test_worktrees_use_separate_state(ws, tmp_path):
    worktree = tmp_path / "other"
    ws.git("worktree", "add", "--detach", str(worktree), "HEAD")
    ws.hook("SessionStart", session="same-session")
    result = ws.run(
        "hook",
        payload={
            "hook_event_name": "SessionStart",
            "session_id": "same-session",
            "cwd": str(worktree),
        },
    )
    assert json.loads(result.stdout) == {}
    states = list(Path(ws.env["BULLY_CODEX_STATE_DIR"]).glob("*.json"))
    assert len(states) == 2
    assert len({json.loads(p.read_text())["root"] for p in states}) == 2


def test_install_preserves_existing_hook_and_is_idempotent(ws, tmp_path):
    path = tmp_path / "hooks.json"
    existing = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo existing"}]}]}}
    path.write_text(json.dumps(existing))
    result = ws.run("install", "--hooks-file", str(path))
    assert result.returncode == 0, result.stderr
    data = json.loads(path.read_text())
    assert data["hooks"]["Stop"][0] == existing["hooks"]["Stop"][0]
    assert len(data["hooks"]["Stop"]) == 2
    assert len(list(tmp_path.glob("hooks.json.bully-backup-*"))) == 1
    assert ws.run("install", "--hooks-file", str(path)).returncode == 0
    assert json.loads(path.read_text()) == data
    assert len(list(tmp_path.glob("hooks.json.bully-backup-*"))) == 1
