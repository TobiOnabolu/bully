# Codex adapter delivery

- [x] Define hook and receipt contracts before implementation.
- [x] Implement global installer and isolated Git session tracking.
- [x] Verify real script failures, stale semantic receipts and config trust.
- [x] Install and trust hooks through Codex's supported review UI.
- [x] Verify hooks/list reports five trusted Bully handlers with no errors.
- [x] Verify real Codex shell edit receives a hook failure, repairs the file,
  and completes with HOOK_VERIFIED.
- [x] Verify real Codex apply_patch triggers semantic evaluation; Codex records
  the no-eval verdict and completes with SEMANTIC_HOOK_VERIFIED.
- [x] Final checks: 476 passed, one existing skip; all lint/dogfood checks passed.
- [x] Opened personal-fork PR #1 and enabled its existing CI workflow.
- [ ] PR/CI, merge and installation from the merged Git revision (see PR status).

## Review

Self-review covered Git baseline semantics, multiple sessions/worktrees, config
removal, trust changes, missing AST tooling, deleted sources, and stale receipts.
It found a missing-final-newline diff edge case; normalized diff line endings
and added a regression probe before publication. No independent reviewer was
launched. Semantic receipts enforce a recorded decision by the current model;
they do not claim independent model judgment or tamper resistance.

Final validation: 476 passed, one preexisting skip; 21 dedicated Codex subprocess
probes passed. Ruff lint/format, shellcheck, dogfood and whitespace checks passed.
Both live Codex integration fixtures passed, covering a shell edit and a native
apply_patch edit with a recorded semantic verdict. PR records CI/merge status.


# Codex shared-checkout attribution fix

Spec: [session attribution](specs/codex-session-attribution.md).

- [x] Reproduce a clean shared checkout being assigned another chat's committed changes.
- [x] Add black-box paired-hook regressions before changing the adapter.
- [x] Snapshot per tool ID and preserve owned files, semantic baselines and interrupted work.
- [ ] Pass focused/full tests, lint, dogfood and hosted CI; merge personal-fork PR.
- [ ] Install merged revision; back up and repair only this chat's verified false attribution.
- [ ] Verify installed-hook read-only isolation, real failure/repair and current chat Stop.

## Review

Self-review, matching the original adapter delivery; no independent reviewer or
PASS claimed. Preserve legacy pending failures and same-tool committed edits.
Missing hook pairs fail conservatively. Concurrent writes during the same tool
interval still require worktree isolation; no claim of OS-level provenance.


Verification checkpoint: 32 focused subprocess probes pass (21 existing and 11
new). The original adapter fails the two-chat committed-update probe at the
read-only observer's Stop. Ruff 0.15.12 lint/format and shellcheck/dogfood pass.
Self-review found that interrupted tool intervals must close after Stop while
retaining their claimed files; added a regression proving later external commits
are not absorbed. Final full-suite result and publication follow below.

Final local verification: **487 passed, 1 preexisting skip**, including all 32
Codex probes. Pinned Ruff lint/format, shellcheck, dogfood and whitespace checks
passed. No dependency/lockfile or Sales OS file changes. Existing legacy ownership
is retained by default; only this chat's confirmed false attribution will be
repaired after backing up its state. PR/CI/install receipts are recorded on the PR.
