# 报一 (Baoyi) Architecture Guide

**报一 (Baoyi)** is a contract-driven, verifiable agent execution harness specializing in autonomous presentation authoring and general software tasks.

---

## 1. Native Execution Loop & Architecture

For PowerPoint domain tasks, every production agent turn flows deterministically from the user request through the native composition root (`runner.runtime.compile_runtime_task`) down to verification and the finish gate:

```text
                       User Request
                            │
                            ▼
                 ┌─────────────────────┐
                 │  Baoyi Agent Loop   │
                 │   agent.Harness     │
                 └─────────┬───────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │ Native Composition Root│
               │ runner.compile_runtime │
               └───────────┬────────────┘
                           │
                 ┌─────────▼─────────┐
                 │    DomainPack     │
                 │   domains/ppt     │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │   core compiler   │
                 │   TaskContract    │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ Runtime Projection│
                 │ ExecutionContract │
                 └─────────┬─────────┘
                           │
                           ▼
             ┌────────────────────────────┐
             │ RuntimeController / Planner│
             │ Phase-aware Tool Runtime   │
             └─────────────┬──────────────┘
                           │
                     Model chooses action
                           │
                           ▼
                     Tool Dispatch
                           │
                           ▼
                   Action / Mutation
                           │
                           ▼
                  Verification Evidence
                           │
                    ┌──────┴──────┐
                    │             │
                 repair         valid
                    │             │
                    └─────Loop────┤
                                  ▼
                              Finish Gate
                                  │
                                  ▼
                              Artifact
```

---

## 2. External Harness Interoperability & Export

For integration with third-party agent harnesses, Baoyi exposes an adapter-driven export root:

```text
TaskContract
     │
     ▼
HarnessAdapter
     │
 ┌───┼─────────────┐
 ▼   ▼             ▼
Claude Codex   OpenCode/WorkBuddy
```

- **`runner.runtime.compile_runtime_task`**: Native Baoyi composition root.
- **`runner.assemble(...)`**: External harness interoperability/export root.

---

## 3. Package Roles & Layering

### `core/` (Domain-Neutral Foundations)
Domain-agnostic protocols, data structures, and compilation primitives:
- **`core/compiler.py`**: Compiles raw user tasks into structured `TaskContract` obligations and capability requirements.
- **`core/contract.py`**: Defines runtime execution contracts, budget bounds, repair limits, and verifier requirements.
- **`core/transaction.py`**: Base `Transaction` protocol defining atomic lifecycle (`begin()`, `commit()`, `rollback()`).
- **`core/verification.py`**: Structural and semantic verification rules generating audit-verifiable certificates.
- *Boundary rule*: `core/` contains strictly **zero** domain-specific vocabulary (no PPT, no file format specifics, no vendor concepts).

### `domains/` (Domain Specialization Packs)
Encapsulates domain-specific semantics, ontology, IR, and operations:
- **`domains/ppt/`**: Fully realized DomainPack implementation featuring:
  - Task ontology: 8 canonical portable task types (`domains/ppt/task_types.py`).
  - Presentation object models (shapes, cards, pipelines, tables, typography).
  - Domain-specific transaction mutations (`set_shape_text`, `set_table`, `batch_updates`, `ppt_compose`).
  - Domain verifiers (shape bindings, provenance anchors, layout metrics).
- *Scope Note*: The contract-driven DomainPack architecture is fully implemented for the PowerPoint domain; generic code workflows execute via a compatibility projection in `runner/runtime.py` (future work will migrate code workflows into a dedicated `domains/code/` pack).
- *Boundary rule*: `domains/` is independent of vendor adapters.

### `runner/` (Composition Roots)
- **`runner/runtime.py` (`compile_runtime_task`)**: Native production composition root. Wires `DomainPack -> core.TaskContract -> TaskSpec -> ExecutionContract`.
- **`runner/__init__.py` (`assemble`)**: External harness adapter composition root.

### `adapters/` (Vendor & Ecosystem Adapters)
Translates tool specifications and execution protocols for external agent ecosystems:
- `adapters/claude_code.py`
- `adapters/codex.py`
- `adapters/opencode.py`
- `adapters/workbuddy.py`

### `agent/` (Interactive Runtime & Session Management)
- **`agent/harness.py`**: Interactive turn loop, CEGAR-H progression monitor, tool dispatch, and streaming.
- **`agent/web_server.py` & `agent/web/`**: Web GUI server, real-time SSE stream, right-sidebar PPT preview, and session manager.
- **`agent/session_store.py`**: Durable, multi-session state serialization and replay.
