# Codex session change attribution

Authorized fix: a planning chat must not inherit failures from another chat's
updates to the same checkout. Reproduced with the installed adapter: this chat's
baseline was 6e0ca7e, shared HEAD moved to 77a1b16, and a clean checkout was assigned
77 changed files including three GHL tests. No Sales OS product changes are needed.

## Contract

Use Codex's paired PreToolUse/PostToolUse `tool_use_id` to capture a Git/content
snapshot immediately before each tool and claim only changes observed during
that tool. Keep each claimed file's original contents for semantic diffs. Retain
claimed files across later calls, commits and stops; Stop always reruns their
checks. Separate pending snapshots by tool ID so parallel calls cannot overwrite
each other. Stop conservatively collects changes from interrupted pending calls, then closes
their intervals so later external changes cannot be inherited.

Changes present before a later tool, including externally committed/staged/dirty
files, do not become this session's edits. A shell write+commit within a tool must
still fail. Existing preexisting-dirty, deletion, trust and receipt protections
remain. Legacy hosts lacking tool IDs keep conservative session-baseline tracking;
existing touched state remains enforced when switching to paired tracking. An
unpaired PostToolUse must block rather than silently pass unverifiable writes.
Repeated SessionStart/compaction must not reset ownership or pending checks.

This is tool-interval attribution, not operating-system writer provenance. An
external writer overlapping a tool cannot be reliably distinguished; use isolated
worktrees for concurrent writers. Git updates performed within a tool remain
conservatively checked. No tool-name or shell-command allowlist bypass.

## Delivery

Change only the Codex adapter/state, focused subprocess probes and its docs/task
record. No hook configuration, rule, trust-store or GHL-test changes. Reuse existing
engines and state locks; no new dependencies. After verification and personal-fork
PR/CI/merge, install the exact merged revision. Back up this chat's obsolete state
and migrate its confirmed falsely attributed paths only; do not clear other
sessions' pending checks. Verify both a read-only pass and a real failing edit
through the installed hook in a disposable repo.

## Done means

- `uv run --no-sync pytest -q tests/test_codex_hooks.py` exits 0, including two-chat external
  commit/dirty-change isolation, same-tool commit rejection, preserved own failures
  after external updates, parallel/interrupted calls, missing pre-event rejection,
  legacy-state continuity and semantic original-content/receipt checks.
- `uv run --no-sync ruff check .`, `uv run --no-sync ruff format --check .`, `uv run --no-sync pytest -q`,
  `uv run --no-sync shellcheck hooks/hook.sh scripts/*.sh`, `uv run --no-sync bash scripts/dogfood.sh`
  and `git diff --check` exit 0. Regression probes fail on the original adapter.
- Exact-head hosted CI passes before merge. Installed CLI reproduces isolated
  two-chat behavior, blocks invalid shell syntax, accepts repair and evaluates
  this chat without unrelated GHL failures. Record results in tasks/todo.md.

Review: one self-review using the original adapter task's review model; no
independent reviewer is launched or claimed.


Local environment: package downloads for optional pre-commit dependencies failed.
Installed the test/lint tools at their existing uv.lock versions directly into the
isolated venv and use --no-sync locally; uv.lock and dependency declarations are
unchanged. Hosted CI performs the full locked all-extras installation.
