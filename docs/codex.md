# Codex automatic enforcement

This fork adds `bully-codex`, a POSIX command-hook adapter. The existing `bully`
CLI and Claude plugin are unchanged.

## Install

```sh
uv tool install git+https://github.com/TobiOnabolu/bully.git
bully-codex install
```

Open Codex's `/hooks`, review the five Bully entries and trust them. The installer
merges into `~/.codex/hooks.json` and keeps a timestamped backup. Start a new chat
after installation so SessionStart captures the initial Git state.

Each project needs a `.bully.yml`. Review its script commands, then run:

```sh
bully validate
bully trust
```

Config changes require another review and `bully trust --refresh`. Config trust
is per absolute path, so a new worktree needs its own approval. Projects without
a config are inactive. The adapter uses the config nearest the chat working
directory; nested configs require a chat rooted in that subproject.

## Behavior

```text
SessionStart / first PreToolUse → capture Git baseline
PostToolUse                    → detect changes → run Bully → return failures
Stop / SubagentStop            → rerun checks → require all error rules to pass
```

Tracked, staged, untracked and newly committed files are compared with the
session's starting state. Preexisting dirty content is left alone until it
changes. Git-ignored untracked files are excluded. File deletion still runs
project-level scripts (scripts without a `{file}` placeholder) and contributes
to session-rule matching. Per-file scripts and AST rules skip deleted files.

The hook includes shell and MCP tool calls, catching writes outside apply_patch.
It caches unchanged intermediate scans, but Stop always rechecks. State and
semantic receipts live under `~/.local/state/bully-codex`, isolated and locked
per session and worktree. `BULLY_CODEX_STATE_DIR` overrides this for testing.

Prose rules send Bully's policy/evidence payload to the current Codex agent. The
hook provides an exact `bully-codex verdict` command for each requested rule.
Codex must record pass/violation with evidence; missing verdicts and error
violations block completion. Receipts bind to the file contents, config checksum
and diff; changing the source or policy invalidates them. This uses the current
model's judgment, not Claude's isolated evaluator. No extra reviewer is launched.

## Limits and recovery

PostToolUse runs after writes and cannot undo them. A failed Stop asks Codex to
continue fixing the problem. These hooks are quality checks, not protection
against a malicious process that can edit the hooks or state. Codex hook timeout
or process-launch failures are host limitations; inspect `/hooks` diagnostics
if enforcement stops running. There is a 120-second hook deadline, and Bully's
script rules each retain their upstream 30-second timeout.

The adapter requires Git and Python 3.10+ on macOS/Linux. An in-scope symlink or
file over 2 MiB blocks with an explicit unsupported-file message. AST rules block
if ast-grep is unavailable. Untrusted configs and configuration errors block
completion without running their scripts.

To remove the adapter, remove only the entries marked `bullyCodex` from
`~/.codex/hooks.json` using `/hooks` or a JSON editor. Leave unrelated hooks in
place. The installed `bully` CLI can remain available.
