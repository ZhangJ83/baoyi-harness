import json
from pathlib import Path

from benchmarks.run_real_controller_ablation import build_schedule

ROOT = Path(__file__).resolve().parents[1]


def load():
    return json.loads((ROOT / "benchmarks/real_controller_ablation_v1.json").read_text(encoding="utf-8"))


def test_schedule_has_48_unique_cells_and_latin_square_orders():
    protocol = load()
    schedule = build_schedule(protocol)
    assert len(schedule) == 48
    assert len({(task["id"], policy) for task, policy in schedule}) == 48
    for index, task in enumerate(protocol["tasks"]):
        observed = [policy for scheduled_task, policy in schedule if scheduled_task["id"] == task["id"]]
        assert observed == protocol["order_control"]["orders"][index % 4]


def test_smoke_schedule_is_one_task_four_policies():
    schedule = build_schedule(load(), smoke=True)
    assert len(schedule) == 4
    assert {policy for _, policy in schedule} == {"direct", "always_verify", "evidence_only", "cegar_h"}
