"""Domain pack registry: name -> DomainPack for the generic compiler."""
from __future__ import annotations

from typing import Dict

DOMAIN_PACKS: Dict[str, object] = {}


def build_ppt_domain_pack():
    from core.compiler import DomainPack
    from domains.ppt import (
        PPT_SKILLS,
        build_presentation_source_ir,
        classify_ppt_task,
        collect_bindings,
        from_pptx,
        verification_policy,
    )
    from domains.ppt.profiles import PROFILE_FOR_TASK_TYPE, profile_for
    from domains.ppt.task_definition import definition_for
    from domains.ppt.task_types import PPTTaskType
    from domains.ppt.tools import CAPABILITIES, PPT_TOOL_FACADE
    from domains.ppt.transaction import (
        PptDelta,
        PptImmutabilityCertificate,
        PptMutationScope,
        delta_within_mutation,
        diff_decks,
    )

    profiles = {t.value: profile_for(t.value) for t in PPTTaskType}

    def classifier(text):
        task_type = classify_ppt_task(text)
        return task_type.value, profiles[task_type.value].capabilities

    return DomainPack(
        name="ppt",
        classifier=classifier,
        profiles=profiles,
        skills=dict(PPT_SKILLS),
        capabilities=CAPABILITIES,
        ir_builders=(("pptx", from_pptx),),
        intake_normalizer=build_presentation_source_ir,
        tool_facade=PPT_TOOL_FACADE,
        transaction_policy={
            "scope": PptMutationScope,
            "delta": PptDelta,
            "certificate": PptImmutabilityCertificate,
            "diff": diff_decks,
            "subset_check": delta_within_mutation,
            "profile_families": PROFILE_FOR_TASK_TYPE,
        },
        verification_policy=verification_policy,
        provenance_policy=collect_bindings,
        mutation_policy_for=lambda task_type: definition_for(task_type).mutation_policy,
    )


def get_domain_pack(name: str):
    """Return the complete DomainPack for a registered domain (lazy import)."""
    if name not in DOMAIN_PACKS:
        if name == "ppt":
            DOMAIN_PACKS[name] = build_ppt_domain_pack()
        else:
            raise KeyError(f"unknown domain pack: {name}")
    return DOMAIN_PACKS[name]


def get_domain_spec(name: str):
    """Backward-compatible alias for callers still using the old name."""
    return get_domain_pack(name)


__all__ = ["DOMAIN_PACKS", "get_domain_pack", "get_domain_spec", "build_ppt_domain_pack"]
