# 报一 Harness (Baoyi)

## Evidence-aware PowerPoint and Coding Workflow

**报一 (Baoyi)** is a provider-neutral, contract-driven coding and PowerPoint agent harness. It combines a stateful tool loop, workspace confinement, command policy gating, structured task state, bounded retries, context compaction, parallel read-only inspection, and a robust PPT inspect/edit/verify workflow.

Every PowerPoint mutation increments an evidence epoch, so verifier evidence from before the latest deck edit cannot be used as fresh completion evidence.

---

## 🚀 Quick Start

```powershell
python -m pip install -e .
$env:OPENAI_API_KEY = "your-api-key"
$env:OPENAI_BASE_URL = "https://api.deepseek.com"
$env:OPENAI_MODEL = "deepseek-v4-flash"
baoyi "inspect this repository, fix the failing tests, and verify the result"
```

Run `baoyi-doctor` before running tasks. It verifies provider, endpoint, dependency, and renderer readiness without printing credential values:

```powershell
baoyi-doctor
```

For Anthropic-compatible endpoints, set `PROVIDER=anthropic`, `ANTHROPIC_BASE_URL=https://api.anthropic.com` (or proxy), and the corresponding model/key environment variables.

Shell command execution defaults to `ask` policy, requiring user confirmation in CLI/GUI. In an isolated benchmark container, set `COMMAND_POLICY=allow`.

---

## 📊 PowerPoint Workflow

The agent can create decks from scratch or load an existing `.pptx`, inspect stable shape IDs, replace text while preserving styling, add editorial and multi-column layouts, save, and run structural checks for bounds, overflow, and overlap. When a renderer is available, visual rendering is used for pixel-level verification.

```powershell
baoyi /demo
```

### Native GUI & Web Server

Launch the native desktop interface:

```powershell
agent-gui --workspace .\workspace
```

Or launch the Web GUI:

```powershell
baoyi --web
```

The desktop and web UIs reuse the complete Harness runtime: long-horizon Goal, planning events, Skill routing, code/PPT tools, transactions, verification, trajectory recording, and cancellation.

---

## 🧪 Container Benchmark Adapter

For isolated benchmark task evaluation:

```powershell
baoyi-bench --workspace C:\task --json "fix the repository and run its tests"
```

Validate a run bundle directory:

```powershell
baoyi-validate-run C:\path\to\run
```

The validator checks input, output, trajectory/events, tool calls, evaluation, and manifest readability.

---

## 🧪 Tests

Run the full test suite using `pytest`:

```powershell
pytest -q
```

Or run specific subsystem suites:

```powershell
pytest tests/test_harness.py tests/test_web_gui.py tests/test_layer_boundaries.py -q
```

---

## ⚙️ Operational Recording & Configuration

Operational evidence recording is configurable via `BAOYI_RECORD_MODE` (or `.env`):

- `minimal`: lifecycle milestones only.
- `audit` (default): compact redacted operational journal and provenance.
- `research`: larger redacted event payloads and trajectory exports for studies.

Copy `.env.example` to `.env` to customize your environment:

```powershell
cp .env.example .env
```

See [docs/architecture.md](docs/architecture.md) for detailed architecture documentation.
