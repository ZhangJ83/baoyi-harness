from experiments.paired_synthetic_ablation import sign_test_p


def test_sign_test_handles_all_ties_and_balanced_pairs():
    assert sign_test_p(0, 0) == 1.0
    assert sign_test_p(2, 2) == 1.0
    assert sign_test_p(4, 0) == 0.125
