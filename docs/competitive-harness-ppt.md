# Competitive harness study for office-document and PPT agents

Date: 2026-08-10

## Scope and evidence policy

This study separates three evidence levels:

- **documented**: stated in official documentation or visible in the local source/protocol snapshot;
- **observed structure**: directly visible in a local source or protocol definition, without claiming undocumented server behavior;
- **inference**: the smallest architecture needed to explain the documented behavior. Inference is not presented as a competitor fact.

The competitors do not publish a dedicated end-to-end PowerPoint harness. Their general coding-agent mechanisms are therefore mapped to document work, and the missing document-specific stages are made explicit.

## Claude Code

### Documented / observed

- The CLI exposes allowed/disallowed tools, permission modes, maximum turns, resumable sessions, MCP, and structured streaming output. Source: [Anthropic CLI reference](https://docs.anthropic.com/en/docs/claude-code/cli-usage).
- The local source snapshot contains a persistent bootstrap state for registered hooks, permission state, invoked skills, compaction state, request identifiers, and hook timing (`claude-code-source/source/src/bootstrap/state.ts`).
- The local source is organized around a query engine plus typed tools, hook callbacks, context/session history, permission callbacks, skills, and subagents.

### Inferred office-document flow

1. Parse the request and load relevant project/user instructions.
2. Inspect source files and attached artifacts through tools.
3. Let the model emit one or more typed tool calls.
4. Apply permission checks and pre-tool hooks.
5. Execute local or MCP-backed document operations.
6. Return observations to the model and repeat.
7. Compact long context while retaining durable state.
8. Stop when the model produces a final response or a turn/budget boundary is hit.

### What this omits for PPT

The generic loop does not itself guarantee that a deck was rendered, visually inspected, or re-verified after the last edit. A successful file write or renderer exit can be mistaken for a valid presentation unless the document workflow adds artifact-scoped completion gates.

## Cursor

### Documented / observed

- Cursor Agent exposes search, read, edit, terminal, MCP, guardrails, auto-apply, auto-run, and auto-fix controls. Source: [Cursor tools](https://docs.cursor.com/en/agent/tools).
- Rules provide persistent scoped instructions, while MCP adds external tools and data. Sources: [Cursor rules](https://docs.cursor.com/context/rules), [Cursor MCP](https://docs.cursor.com/context/model-context-protocol).
- Checkpoints automatically snapshot Agent changes and can restore them; they are distinct from version control. Source: [Cursor checkpoints](https://docs.cursor.com/en/agent/chat/checkpoints).
- The local reverse-engineered protocol snapshot exposes potentially cached context items, context hashes/status updates, client-side tool calls, agent conversation ids, composer generation ids, parallel apply, tool-content blocks, and background composer configuration (`cursor-grpc/server_chat.proto`, `cursor-grpc/server_config.proto`). These fields establish protocol shape, not hidden server policy.

### Inferred office-document flow

1. Assemble user-selected and automatically retrieved context.
2. Stream a composer/agent response that may include client-side tool calls.
3. Execute edits locally, potentially with fast or parallel apply.
4. Surface diffs/checkpoints so the user can review or restore.
5. Use terminal or MCP tools for conversion, rendering, or external systems.
6. Continue from updated context and tool output.

### What this omits for PPT

File checkpoints are useful recovery, but they do not express presentation semantics: slide roles, stable shape identities, overflow, theme consistency, rendered pixels, or whether a validation result predates the latest deck mutation.

## Codex and OpenAI plugins

### Documented / observed

- OpenAI describes a plugin as a package containing skills, an optional MCP server, and optional UI. Skills provide workflow instructions/resources; MCP exposes controlled tools, schemas, authentication, structured results, and optionally UI. Source: [OpenAI plugin architecture](https://developers.openai.com/plugins/concepts/plugins).
- Official Codex documentation separately exposes skills, plugins, hooks, MCP, sandboxing, approvals, AGENTS.md instructions, worktrees, and non-interactive execution. Source index: [OpenAI Developers](https://developers.openai.com/).
- The local `openai-codex` source snapshot contains explicit approval, sandbox, tool-call, compaction, skill, and plugin paths. This supports the architectural comparison, not claims about unreleased behavior.

### Office-document mapping

- **Skill only**: appropriate when existing local tools already manipulate and render the document and only a repeatable workflow is missing.
- **MCP/plugin**: appropriate when the harness must connect to Drive/SharePoint/Canva, authenticate users, call a remote renderer, or expose review UI.
- **Core harness tool**: appropriate for stateful, latency-sensitive deck mutations whose evidence must be tied to the current in-memory artifact.

## Architecture decision for Xiaopu

Use a hybrid design:

1. Keep deck inspection and mutation tools inside the harness. This preserves stable shape identity, in-memory state, sandbox boundaries, and mutation epochs.
2. Package the create/edit/restyle/repair workflow as a dynamically loaded PowerPoint skill.
3. Use plugin/MCP adapters only for external content sources, asset generation, cloud storage, remote rendering, or human review services.
4. Treat every deck mutation as an epoch transition. Structural, rendered-pixel, and semantic review evidence from older epochs becomes inadmissible.

This is better suited to office documents than either a pure hard-coded loop or a pure plugin design: the artifact state and safety invariant remain local, while integrations stay replaceable.

## Reconstructed complete PPT workflow

```text
request
  -> classify(create/edit/restyle/repair/extract)
  -> inspect sources and current deck
  -> derive slide-role outline and constraints
  -> choose semantic layout/tool
  -> mutate deck (epoch increments)
  -> structural verification
  -> save
  -> render to PNG
  -> deterministic pixel audit
  -> semantic/human or vision review when available
  -> targeted repair (epoch increments; old evidence invalid)
  -> repeat applicable checks
  -> finish only with current-epoch evidence and explicit limitations
```

The key reconstruction is the right-hand side of the loop. Generic agents often show `edit -> result`; office-document reliability requires `edit -> render -> inspect -> repair -> re-verify`, with provenance attached to the artifact version.

