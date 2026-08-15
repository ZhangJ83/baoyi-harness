# PPTBench v2 blinded review rubric

This rubric applies only to outputs from
`benchmarks/pptbench_model_eval_v2.json`. Reviewers receive anonymized IDs,
rendered slides, a montage, the task prompt and facts, but no system identity,
generation trace, filename or directory that exposes the producer.

## Eligibility before review

A deck is marked structurally ineligible, not assigned a subjective score, if
it cannot open or render, has a missing slide image, unintended overlap,
overflow, unresolved placeholders, or evidence that predates the final
mutation. All ineligible decks stay in the denominator with the preregistered
failure score; they are never silently removed.

## Scale

- 1 — unusable: the dimension materially prevents the deck from doing its job.
- 2 — weak: major defects remain and substantial repair is needed.
- 3 — adequate: usable with visible but non-fatal shortcomings.
- 4 — strong: clear and polished with only minor defects.
- 5 — exceptional: unusually effective for the task, with no material defect.

## Dimensions

| Dimension | Anchored question |
|---|---|
| Content fidelity | Are every required fact and the requested decision preserved without invention or overclaim? |
| Narrative hierarchy | Does each slide have one primary claim, and does the sequence lead the stated audience to the required outcome? |
| Layout | Are alignment, spacing, grouping and balance intentional, without accidental overlap or unusable empty space? |
| Typography | Are title/body hierarchy, wrapping, bilingual pairing, line length and contrast readable at presentation scale? |
| Visual consistency | Are palette, typography, spacing and visual treatments coherent while slide silhouettes still fit their content? |
| Density | Is the information concise without clipping, crowding, production notes or low-value repetition? |
| Edit fidelity | For fixed-input tasks, is the requested change made without unrelated damage? For from-scratch tasks, score 3 when no edit-specific issue applies. |

## Review procedure

1. Two reviewers score independently on the integer 1–5 scale.
2. They do not discuss artifacts until both blind forms are locked and hashed.
3. Reviewer order and anonymous artifact order are independently randomized.
4. Reviewers receive only anonymous task packets, montages, and slide PNGs;
   visible or metadata-level system identity causes packaging to fail.
5. Each reviewer declares independence from generation, non-authorship, and
   conflicts before the completed draft can be locked.
6. Optional adjudication happens only after locking and is excluded from the
   primary analysis.
7. Report deck-level dimension mean, paired task mean, quadratic-weighted
   kappa per dimension, and ICC(2,1) over the overall deck score.
8. Report paired 95% bootstrap intervals and two-sided paired permutation
   tests, with Holm correction across Xiaopu's two comparator contrasts.

## Claim boundary

Completing 12 paired tasks is transfer evidence for this frozen task set. It
does not by itself establish broad aesthetic superiority, official PPTBench
leadership, or ICLR Best Paper quality.
