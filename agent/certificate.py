"""Certificate requirement evaluation independent of domain tool names."""
from __future__ import annotations


def missing_requirements(contract, evidence) -> list[str]:
    """Return unsatisfied finish-certificate requirements.

    ``evidence`` must already be epoch-filtered by the caller (for example
    ``RunState.fresh_evidence()``).  Certificates only ever consider
    current-epoch passing records; passing stale evidence is not a certificate.
    """
    if contract is None:
        return []
    kinds = {record.kind for record in evidence if record.passed}
    missing = []
    for requirement in contract.finish_certificates:
        if not (set(requirement.split("|")) & kinds):
            missing.append(requirement)
    return sorted(missing)


def require_finish_certificates(state) -> None:
    missing = missing_requirements(
        getattr(state, "execution_contract", None),
        state.fresh_evidence(),
    )
    if missing:
        raise ValueError(
            "cannot finish: execution contract requires fresh certificate(s): "
            + ", ".join(missing)
        )

