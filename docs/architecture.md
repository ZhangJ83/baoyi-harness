# 报一 (Baoyi) Architecture Guide

**报一 (Baoyi)** is a provider-neutral, contract-driven agent execution harness designed for complex code and presentation automation workflows.

---

## 1. Architectural Philosophy & Structure

Baoyi separates portable foundational primitives from runtime interactive services:

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

## 2. Package Roles & Layering

### `core/` (Domain-Neutral Foundations)
Domain-agnostic protocols, data structures, and compilation primitives:
- **`core/compiler.py`**: Compiles raw user tasks into structured `TaskContract` obligations and capability requirements.
- **`core/contract.py`**: Defines runtime execution contracts, budget bounds, repair limits, and verifier requirements.
- **`core/transaction.py`**: Base `Transaction` protocol defining atomic lifecycle (`begin()`, `commit()`, `rollback()`).
- **`core/verification.py`**: Structural and semantic verification rules generating audit-verifiable certificates.
- *Boundary rule*: `core/` contains strictly **zero** domain-specific vocabulary (no PPT, no file format specifics, no vendor concepts).

### `domains/` (Domain Specialization Packs)
Encapsulates domain-specific semantics, IR, and operations:
- **`domains/ppt/`**:
  - Presentation object models (shapes, cards, pipelines, tables, typography).
  - Domain-specific transaction mutations (`set_shape_text`, `set_table`, `batch_updates`, `ppt_compose`).
  - Domain verifiers (shape bindings, provenance anchors, layout metrics).
- *Boundary rule*: `domains/` is independent of vendor adapters.

### `adapters/` (Vendor & Ecosystem Adapters)
Translates tool specifications and execution protocols for different agent ecosystems:
- `adapters/claude_code.py`
- `adapters/codex.py`
- `adapters/opencode.py`
- `adapters/workbuddy.py`

### `runner/` (Composition Root)
- **`runner.assemble()`**: The central composition root that binds `core + domain pack + vendor adapter` into an executable, isolated Harness instance.

### `agent/` (Interactive Runtime & Session Management)
- **`agent/harness.py`**: Interactive turn loop, CEGAR-H progression monitor, tool dispatch, and streaming.
- **`agent/web_server.py` & `agent/web/`**: Web GUI server, real-time SSE stream, right-sidebar PPT preview, and session manager.
- **`agent/session_store.py`**: Durable, multi-session state serialization and replay.

---

## 3. Architecture Evolution & Roadmap

### Current State
- The portable architecture (`core`, `domains`, `adapters`, `runner`) is fully defined, tested, and validated by architectural boundary tests (`tests/test_layer_boundaries.py`).
- Interactive execution is orchestrated via `agent.harness`, with domain logic in `agent/tools/` and `domains/ppt/`.

### Target Convergence
1. **Subsystem Modularization**: Deconstruct `agent/tools/ppt_tools.py` into dedicated modules under `domains/ppt/runtime/` (`inspect`, `text`, `style`, `compose`, `render`, `verify`).
2. **Transaction Unification**: Route all PPT mutations directly through `ActionTransaction` and domain action adapters.
3. **Finish Gate Unification**: Fully standardize all exit paths through certificate-driven verification in `core/verification.py`.
