# Observable-budget comparator adapter checklist

- [x] Freeze the claim boundary and common observable fields.
- [x] Implement schema-specific Claude event normalization.
- [x] Implement schema-specific Codex event normalization.
- [x] Add malformed and missing-usage tests.
- [x] Record the Codex step-observability gap instead of inventing a proxy.
- [ ] Add bounded subprocess supervision and durable ledger output after the
  common observable contract is re-pre-registered.
- [x] Run focused tests (4 passed).
- [x] Run full regression (78 passed, 5 skipped).
- [x] Refresh evidence audits after claim-map update (valid).
- [x] Update protocol without flipping the parity gate.
- [x] Refresh package after the full regression.
