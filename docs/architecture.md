# 报一 (Baoyi) Architecture Guide

**报一 (Baoyi)** is a provider-neutral, contract-driven agent execution harness designed for complex code and presentation automation tasks.

---

## 1. High-Level Architecture Overview

Baoyi is organized into a clean **portable layered architecture**:

```text
                      ┌───────────────────────────┐
                      │        User Request       │
                      └─────────────┬─────────────┘
                                    │
                       ┌────────────▼────────────┐
                       │   Intake & Task Compiler │
                       └────────────┬────────────┘
                                    │
                      ┌─────────────▼─────────────┐
                      │ Execution / Task Contract │
                      └─────────────┬─────────────┘
                                    │
             ┌──────────────────────┼──────────────────────┐
             ▼                      ▼                      ▼
    ┌─────────────────┐    ┌─────────────────┐   ┌───────────────────┐
    │  Model / LLM    │    │  Action Runtime │   │   Verification    │
    │  (OpenAI/Claude)│    │  (Transaction)  │   │   (Certificates)  │
    └─────────────────┘    └────────┬────────┘   └───────────────────┘
                                    │
                         ┌──────────▼──────────┐
                         │     Domain Pack     │
                         │   (domains/ppt, ...)│
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │   Vendor Adapter    │
                         │(Claude/Codex/Open...)│
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │   Finish Gate       │
                         └─────────────────────┘
```

---

## 2. Core Package Responsibilities

### `core/` (Domain-Neutral Foundations)
Contains pure, domain-agnostic abstractions and protocols:
- **`core/compiler.py`**: Compiles raw user tasks into structured `TaskContract` obligations.
- **`core/contract.py`**: Defines runtime execution contracts, bounds, repair limits, and verifier requirements.
- **`core/transaction.py`**: Action transaction lifecycle (`begin`, `mutate`, `commit`, `rollback`, `undo`).
- **`core/verification.py`**: Structural and semantic verification rules generating verifiable certificates.
- *Constraint*: `core` strictly contains **zero** domain vocabulary (no PPT, no vendor concepts).

### `domains/` (Domain Specialization Packs)
Encapsulates domain-specific semantics, IR, and operations:
- **`domains/ppt/`**:
  - Presentation object models (shapes, cards, pipelines, tables, typography).
  - Domain-specific transaction mutations (`set_shape_text`, `set_table`, `batch_updates`, `ppt_compose`).
  - Domain verifiers (shape bindings, provenance anchors, layout metrics).
- *Constraint*: `domains` is completely independent of vendor adapters and legacy runtime.

### `adapters/` (Vendor & Environment Adapters)
Translates tool specifications and execution protocols for different agent ecosystems:
- `adapters/claude_code.py`
- `adapters/codex.py`
- `adapters/opencode.py`
- `adapters/workbuddy.py`

### `runner/` (Composition Root)
- **`runner.assemble()`**: The central composition root that binds `core + domain pack + vendor adapter` into an executable, isolated Harness instance.

### `agent/` (Interactive Runtime & Session Management)
- **`agent/harness.py`**: Interactive model turn loop, CEGAR-H progression monitor, tool dispatch, and streaming.
- **`agent/web_server.py` & `agent/web/`**: Web GUI server, real-time SSE stream, right-sidebar PPT preview, and session manager.
- **`agent/session_store.py`**: Durable, multi-session state serialization and replay.

---

## 3. The Execution Lifecycle (CEGAR-H)

Baoyi implements **CEGAR-H (Counterexample-Guided Abstraction Refinement with Harness Gates)**:

1. **Intake & Understand**: Bounded observation to extract necessary context and shape metadata without infinite exploration loops.
2. **Produce (Mutation)**: Atomic edits performed within `ActionTransaction`. Unsaved mutations advance the artifact epoch.
3. **Verify (Structural Evidence)**: Automatic structural and contract checks. Failures generate concrete counterexamples (blockers) for targeted repair.
4. **Deliver (Finish Gate)**: Verified certificates are required before `finish` can succeed.
