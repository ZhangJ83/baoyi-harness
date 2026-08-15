from benchmarks.select_matched_tasks import select


def test_selection_is_deterministic_and_sorted(tmp_path):
    for name in ("z", "a", "m", "b"):
        (tmp_path / name).mkdir()
    first = select(tmp_path, 3, "seed")
    second = select(tmp_path, 3, "seed")
    assert first == second
    assert first == sorted(first)
    assert len(first) == 3


def test_selection_rejects_invalid_size(tmp_path):
    (tmp_path / "a").mkdir()
    try:
        select(tmp_path, 2, "seed")
    except ValueError as exc:
        assert "n must be" in str(exc)
    else:
        raise AssertionError("expected ValueError")
