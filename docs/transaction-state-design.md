# Transaction state and historical capital validation

Implement the user's generalized rules without security-, issuer-, or accession-specific branches.

1. Reproduce stale closing selection, lost cash/stock terms, amendment precedence, weak identity joins, historical confidence downgrades and unresolved subsequent events in source-text fixtures.
2. Reduce correlated transaction filings chronologically. Use agreement dates, legal parties/defined aliases and original-agreement references together; preserve evidence and per-field source provenance. Explicit actual closing/termination overrides earlier states. Future/approval/financing language cannot close a transaction.
3. Recover economics independently of lifecycle. Current evidence and later operative amendments supersede earlier terms; incomplete amendments mark affected economics unresolved. Common-holder exchange ratios and ownership remain transaction terms, never current FD shares.
4. Classify read-only financial capital records as historical included or requiring current reconciliation using action dates, financial period, share baseline and surviving instruments. Keep independent issuance/retirement IDs, source corroboration and no balance mutation.
5. Run all tests and independent code review. Ship both engines and run a full universe scan. Replay the previous engine on the same captured SEC/market inputs for comparable impact counts; report automated differences separately from source-validated errors.

Unknown links, unreadable sources, conflicting terms or unresolved current instruments retain DATA_HOLD and SAFE_TO_ACT=FALSE. Historical context never grants PASS or cancels an independent dilution warning.
