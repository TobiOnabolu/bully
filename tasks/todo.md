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
