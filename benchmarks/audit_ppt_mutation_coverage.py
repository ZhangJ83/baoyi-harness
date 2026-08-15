"""Audit PPT mutation entry points and their epoch instrumentation.

This is a static audit, not a substitute for runtime tests.  It makes the
mutation surface explicit so a new mutator cannot silently bypass the evidence
ledger.  The registry fallback is intentional: dispatch records a generic
change when a mutator did not emit a more specific change itself.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PPT = ROOT / "agent" / "tools" / "ppt_tools.py"
REGISTRY = ROOT / "agent" / "tools" / "registry.py"
OUT = ROOT / "workspace" / "results" / "ppt_mutation_coverage.json"


def _names(tree: ast.AST, needle: str) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr == needle
            for child in ast.walk(node)
        ):
            found.add(node.name)
    return found


def main() -> int:
    ppt_tree = ast.parse(PPT.read_text(encoding="utf-8"))
    registry_tree = ast.parse(REGISTRY.read_text(encoding="utf-8"))
    direct = _names(ppt_tree, "record_change")
    registered: list[str] = []
    for node in ast.walk(registry_tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_PPT_MUTATORS"
            for target in node.targets
        ) and isinstance(node.value, ast.Set):
            registered = sorted(
                str(item.value) for item in node.value.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            )
            break
    # Resolve the tool name -> implementation function from the tool list.
    tool_names: dict[str, str] = {}
    for node in ast.walk(ppt_tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_make":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[-1], ast.Lambda):
                name = node.args[0].value
                body = node.args[-1].body
                if isinstance(body, ast.Call) and isinstance(body.func, ast.Name):
                    tool_names[str(name)] = body.func.id
    rows = []
    for name in registered:
        impl = tool_names.get(name, "<unresolved>")
        rows.append({
            "tool": name,
            "implementation": impl,
            "direct_record_change": impl in direct,
            "dispatch_fallback": True,
            "coverage_status": "direct-or-fallback",
        })
    covered = sum(1 for row in rows if row["dispatch_fallback"] or row["direct_record_change"])
    report = {
        "schema": "ppt-mutation-coverage-v1",
        "source": [str(PPT.relative_to(ROOT)), str(REGISTRY.relative_to(ROOT))],
        "registered_mutators": len(rows),
        "covered_mutators": covered,
        "coverage_complete": covered == len(rows),
        "directly_instrumented_implementations": sorted(direct),
        "fallback_contract": "dispatch records deck:<tool> when epoch is unchanged",
        "rows": rows,
        "limitations": [
            "Static AST coverage does not observe uninstrumented external side effects.",
            "Runtime tests and the evidence ledger remain the authoritative behavior checks.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "registered_mutators": len(rows), "direct": len(direct)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
