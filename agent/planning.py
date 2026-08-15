"""Auditable stage planning without exposing private chain-of-thought."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanningDecision:
    stage: str
    next_action: str
    evidence: tuple[str, ...]
    gaps: tuple[str, ...]
    reason: str
    revised: bool = False


def plan_next(state, contract) -> PlanningDecision:
    fresh = tuple(record.kind for record in state.fresh_evidence())
    if state.unresolved_checks:
        return PlanningDecision(
            stage="repair",
            next_action="仅修复验证反例指向的范围，然后重新保存和验证",
            evidence=fresh,
            gaps=tuple(sorted(state.unresolved_checks)),
            reason="最新证据包含未解决反例，禁止扩大探索范围",
            revised=True,
        )
    if not state.changed_files and state.mutation_epoch == 0:
        return PlanningDecision(
            stage=state.phase.value,
            next_action="完成一次最具体的目标检查，然后执行合同允许的修改",
            evidence=fresh,
            gaps=("candidate_artifact",),
            reason="尚无候选修改，行动价值高于继续广泛观察",
        )
    required = sorted(getattr(contract, "finish_certificates", ())) if contract else []
    kinds = set(fresh)
    gaps = tuple(req for req in required if not (set(req.split("|")) & kinds))
    if gaps:
        return PlanningDecision(
            stage="verify",
            next_action="保存最新 revision，并获取缺失的确定性 Certificate",
            evidence=fresh,
            gaps=gaps,
            reason="产物已修改，但完成合同尚未被当前 revision 的证据满足",
            revised=state.last_verification_failed,
        )
    return PlanningDecision(
        stage="deliver",
        next_action="停止探索并交付",
        evidence=fresh,
        gaps=(),
        reason="当前 revision 已满足完成合同",
    )

