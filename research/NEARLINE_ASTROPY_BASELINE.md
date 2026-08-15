# Near-line Astropy test baseline

Date: 2026-08-09

Command executed in a temporary Linux container:

```text
pip install numpy==1.26.4 astropy==5.0.4 pytest hypothesis
pytest -q test_separable.py
```

Result: **11 passed**.

Interpretation: this proves that the frozen separability test file and its
general dependency family can execute in a clean Linux container. It is not
an official SWE-bench result for the exact base commit, because the installed
Astropy wheel is a released near-line version rather than the repository
checkout at `d16bfe05a744909de4b27f5875fe0d4ed41ce607`.
