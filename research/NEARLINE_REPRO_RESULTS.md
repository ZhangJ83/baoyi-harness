# Near-line official issue reproductions

Environment: Linux container, `astropy==5.0.4`, `numpy==1.26.4`.

- `astropy__astropy-13033`: reproduced the misleading exception
  `expected 'time' as the first columns but found 'time'`.
- `astropy__astropy-13453`: supplied HTML `formats` was not reflected in the
  generated output (`1.24e-24` absent).
- `astropy__astropy-13236`: corrected structured-array reproduction produced
  ordinary `Column` objects for both fields (`['a', 'b']`), consistent with the
  intended post-patch behavior.

These are near-line release observations, not exact base-commit SWE-bench
scores.

- `astropy__astropy-13398`: the minimal ITRS→AltAz/HADec round-trip was
  attempted, but Astropy 5.0.4 under the selected NumPy environment failed
  before the transform with `TypeError: concatenate() got an unexpected
  keyword argument 'dtype'`; this is recorded as an environment incompatibility,
  not a task result.
