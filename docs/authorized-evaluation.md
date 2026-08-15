# One-input authorized matched evaluation

`benchmarks/run_authorized_matched.ps1` is the single-entry wrapper for a
provider-backed matched Terminal-Bench run. It asks for the DeepSeek key once
only when `OPENAI_API_KEY` is absent, keeps it in the current process, and uses
the Flash model and fixed DeepSeek endpoints for Xiaopu and the comparator
adapters.

The default is the existing three-task pilot. Any larger slice requires both
`-AllowExpandedSlice` and `-ApproveProviderSpend`, plus explicit token/tool
caps. The wrapper never saves or prints the key.

Example after Docker is ready:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File benchmarks/run_authorized_matched.ps1 `
  -IncludeCompetitors -IncludeOpenCode
```

For the predeclared 12-task slice, use an explicit cap and approval:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File benchmarks/run_authorized_matched.ps1 `
  -TaskId (Get-Content benchmarks/matched_12_task_manifest.json | ConvertFrom-Json).task_ids `
  -MaxTasks 12 -AllowExpandedSlice -ApproveProviderSpend `
  -MaxTotalTokens 31344 -IncludeCompetitors -IncludeOpenCode
```

The 12-task command is intentionally not run by automation without an explicit
cost approval. Its output remains pilot/experimental evidence until the
predeclared inferential gate passes; the wrapper does not promote results to a
leaderboard claim.
