from benchmarks.power_analysis import mcnemar_two_sided


def test_power_plan_distinguishes_bootstrap_and_exact_thresholds():
    # Four wins and no losses (the optimistic 12-task pattern) is still not
    # an exact-test result at the conventional 0.05 level.
    assert mcnemar_two_sided(4, 0) == 0.125
    assert mcnemar_two_sided(6, 0) < 0.05
