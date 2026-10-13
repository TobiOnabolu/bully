# Codex enforcement adapter

Install a global Codex command-hook adapter, preserving existing hooks. Reuse
Bully engines, scope matching, config trust and semantic payloads. Claude behavior
stays unchanged. Work in an isolated worktree of the personal fork.

Hooks discover the nearest .bully.yml from the session cwd. Projects without a
config are inactive. Scripts require Bully trust. Config errors, unavailable AST
tooling and changed untrusted configs block completion. Git workspaces are
required for tracking shell edits.

SessionStart/PreToolUse record a Git baseline. PostToolUse detects tracked,
untracked, staged and newly committed changes. Existing untouched dirty files
are excluded. Stop reruns checks over the changed set and evaluates session
requirements. State is isolated per session/worktree outside the repo and locked.

Semantic checks send upstream trusted-policy/untrusted-evidence payloads to the
current Codex agent. Each rule needs a verdict through bully-codex verdict, bound
to file contents, diff and config checksum. Missing, stale or error-violation
verdicts block Stop. This is model self-evaluation, not an independent reviewer
or isolated Claude evaluator. Warnings remain advisory after evaluation.

The installer preserves other hooks, backs up the source, and is idempotent.
Use Codex's supported hook-trust flow; never edit trust storage or disable trust
globally. PostToolUse cannot roll back edits; Stop requests continuation. This
is a quality gate, not a malicious-agent security boundary.

## Done means

- uv run pytest -q tests/test_codex_hooks.py exits 0: subprocess probes for
  multi-file edits, shell writes, committed changes, preexisting dirty files,
  deletions, trust, dependency rechecks, semantic receipts and session isolation.
- uv run ruff check . and uv run ruff format --check . exit 0.
- uv run pytest -q and uv run bash scripts/dogfood.sh exit 0.
- A real Codex run loads the hook, receives a failing rule, corrects the file
  and completes. Record evidence in tasks/todo.md.
- Installed hooks are listed as trusted by Codex; binary resolves in a fresh
  shell. PR to personal fork passes CI and merges.
- Separately enable the existing Sales OS typecheck in its own worktree/PR.
