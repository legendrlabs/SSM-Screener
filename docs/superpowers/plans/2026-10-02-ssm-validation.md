# SSM validation and output publishing repair

> Execute inline, using test-driven-development and verification-before-completion.

**Goal:** Preserve DATA_HOLD for incomplete cap tables and publish generated snapshots without rebase conflicts.
**Spec:** SKILL.md (SEC-first, incomplete fully diluted economics => DATA_HOLD).
**Constraints:** No inferred financial quantities; retain GitHub authentication; no strategy changes.

## Tasks
- [x] Reproduce AGPU-like unresolved filing merged with an unrelated clean exhibit; keep low confidence.
- [x] Reproduce partial instrument extraction and pre-funded/common-warrant collisions; hold missing quantities and preserve distinct instruments.
- [x] Reproduce two scanners publishing over one another with temporary bare Git repos; replace snapshots on latest main, skip outdated source, retry ordinary push races.
- [ ] Run the full suite, publish one atomic commit, and verify GitHub tests and generated output.

## Review focus
Explicit overrides must remain authoritative. Equal-sized distinct instruments must not cancel one another. Never overwrite newer source output with stale source. Keep generated CSV/JSON/Markdown as one snapshot. GPRO without reliable cover-page shares must remain DATA_HOLD.
