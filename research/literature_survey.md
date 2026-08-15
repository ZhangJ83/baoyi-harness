# Literature survey and novelty audit

Status: primary metadata retrieved from the arXiv API on 2026-08-09. This pass
updates the earlier informal notes; it is not a claim that every paper was read
in full. Recent papers are treated as novelty threats until their methods can be
checked in detail.

## Search ledger

| Query bucket | Purpose | Outcome |
|---|---|---|
| reasoning/acting/search | establish inference-time agent baselines | ReAct, Tree of Thoughts, Reflexion, LATS |
| software agents | establish interface and workflow baselines | SWE-agent, Agentless, SWE-Edit |
| adaptive computation | locate budget allocation precedents | ACT and Duo-LLM; mostly model/token-level rather than harness-level |
| staleness/freshness/verification | actively try to invalidate FreshCert | EA-Graph and STALE make freshness alone non-novel |
| contextual verification | locate evidence-selection precedents | Agentic Rubrics and evidence-grounding work overlap verifier design |

## Retained papers

1. Yao et al., **ReAct: Synergizing Reasoning and Acting in Language Models**,
   arXiv:2210.03629 (2022). Establishes interleaved thought/action trajectories.
   It does not optimize whether an extra reasoning/tool step is worth its cost.
2. Yao et al., **Tree of Thoughts: Deliberate Problem Solving with Large
   Language Models**, arXiv:2305.10601 (2023). Establishes explicit search over
   reasoning states. It motivates the expensive-compute arm in our controller.
3. Shinn et al., **Reflexion: Language Agents with Verbal Reinforcement
   Learning**, arXiv:2303.11366 (2023). Uses feedback and verbal memory for
   iterative improvement; it is a key repair baseline, not a freshness proof.
4. Zhou et al., **Language Agent Tree Search Unifies Reasoning Acting and
   Planning in Language Models**, arXiv:2310.04406 (2023). Combines MCTS-style
   search and reflection. It is the strongest classical always-search neighbor.
5. Yang et al., **SWE-agent: Agent-Computer Interfaces Enable Automated
   Software Engineering**, arXiv:2405.15793 (2024). Shows that the agent-computer
   interface and tool feedback materially affect SWE outcomes.
6. Xia et al., **Agentless: Demystifying LLM-based Software Engineering
   Agents**, arXiv:2407.01489 (2024). Shows a simple localized workflow can be
   competitive, directly motivating a never/limited-deliberation baseline.
7. Anonymous authors in current arXiv metadata, **Duo-LLM: A Framework for
   Studying Adaptive Computation in Large Language Models**, arXiv:2410.10846
   (2024). Studies adaptive computation in LMs; its level of control is closer
   to model routing than evidence-aware harness metareasoning.
8. **Agentic Rubrics as Contextual Verifiers for SWE Agents**,
   arXiv:2601.04171 (2026). Treats contextual verification as a source of
   inference-time gains; this is close to verifier selection and must be a
   direct empirical comparator when implementation details are available.
9. **SWE-Edit: Rethinking Code Editing for Efficient SWE-Agent**,
   arXiv:2604.26102 (2026). Identifies context coupling in code editing. It
   threatens broad efficiency claims but not the joint evidence/compute policy.
10. **When Agents Overtrust Environmental Evidence**, arXiv:2605.08828
    (2026). Studies evidence-grounding defects. It limits any claim that tool
    observations are automatically authoritative.
11. **When Memory Updates but Behavior Does Not**, arXiv:2608.01619 (2026).
    Introduces the STALE setting for implicit stale dependencies. It shows that
    detecting stale memory is insufficient if policy behavior remains anchored.
12. **EA-Graph: Artifact-Anchored Verification Memory for Coding Agents under
    Upstream Drift**, arXiv:2608.04278 (2026). Directly binds verification
    memory to changing artifacts. This invalidates “epoch freshness alone” as
    the main novelty claim.

## Novelty map

| Component | Closest work | Verdict |
|---|---|---|
| interleaved tool loop | ReAct, SWE-agent | established |
| search/reflection | ToT, Reflexion, LATS | established |
| simple workflow | Agentless | essential baseline |
| adaptive compute | ACT/Duo-LLM and test-time scaling | established in adjacent levels |
| contextual verification | Agentic Rubrics | close overlap |
| stale evidence invalidation | STALE, EA-Graph | not novel alone |
| joint allocation of *which evidence* and *how much deliberation* under measured cost/risk, with correlation-robust certificates | no exact match found in this bounded pass | candidate gap; must remain a qualified claim |

## Claim boundary

The paper must not claim invention of agent search, reflection, adaptive
computation, verifier cascades, or freshness tracking. The defensible research
question is narrower: can a harness jointly allocate deliberation and evidence
acquisition under a cost/risk constraint, while refusing certificates invalidated
by mutations, and thereby improve the success-cost-risk frontier across coding
and document tasks? “No exact match found” is not proof of novelty; the search
will be refreshed before submission and the three most recent threats require
full-method reading.

## Unresolved overlap

- Retrieve and inspect the full methods of EA-Graph, Agentic Rubrics, EnvProbe,
  and GraSP when arXiv rate limits clear.
- Check proceedings/Scholar for non-arXiv metareasoning and selective-prediction
  work that jointly controls tests and computation.
- Verify authors and final publication venues from versioned primary records.

