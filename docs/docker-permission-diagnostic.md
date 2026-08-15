# Docker permission diagnostic

The official runners require access to the Docker Desktop named pipe. The
Codex sandbox account is not necessarily the same Windows account that owns
the interactive Docker Desktop session. A running `Docker Desktop.exe` alone
does not prove that the current account can access the engine.

Run the diagnostic first:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File benchmarks/diagnose_docker_desktop.ps1
```

If `docker_info_ok` is false or the probe reports `Access denied`, open an
Administrator PowerShell under the same interactive account that owns Docker
Desktop and run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File benchmarks/repair_docker_desktop.ps1
```

The Codex sandbox account is intentionally isolated. Adding
`codexsandboxoffline` to `docker-users` is not a reliable fix when Docker
Desktop is owned by the interactive `zzz` account; run the repair and the
benchmark from that same interactive account instead.

The authorized benchmark wrapper now performs this preflight before prompting
for an API key. This prevents credentials from being entered into a run that
cannot reach Docker.
