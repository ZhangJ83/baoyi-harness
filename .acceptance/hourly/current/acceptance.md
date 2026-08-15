# 小朴一小时验收报告

- 生成时间：`2026-08-13T22:36:58.800580+00:00`
- 总体结果：**passed**
- 通过：`8/8`

| 验收项 | 结果 |
|---|---|
| `transaction_success` | passed - 证据已写入 JSON |
| `transaction_scope_denied` | passed - 证据已写入 JSON |
| `transaction_execute_rollback` | passed - 证据已写入 JSON |
| `transaction_validation_rollback` | passed - 证据已写入 JSON |
| `transaction_cancel_rollback` | passed - 证据已写入 JSON |
| `ordinary_file_atomic_edit` | passed - 证据已写入 JSON |
| `ppt_xmind_from_outline` | passed - 证据已写入 JSON |
| `ppt_governance_batch_update` | passed - 证据已写入 JSON |

## 证据边界

- The two PPT checks reopen existing real benchmark smokes; they do not rerun a model trajectory.
- These historical XMind/governance checks do not claim fresh PNG rendering. A separate two-case PPT transaction smoke has artifact-tool PNG evidence under .acceptance/hourly/transaction-smoke/.
- The governance PPT is explicitly a representative batch-transaction smoke, not the full task submission.
- Historical source_unchanged and structural-gate claims are imported from the frozen smoke manifest; current source hashes are recorded separately.
