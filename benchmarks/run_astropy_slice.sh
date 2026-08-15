#!/usr/bin/env bash
set -euo pipefail
src=${1:?source checkout required}
expected=${2:?expected commit required}
test_cmd=${3:-"pytest -q astropy/modeling/tests/test_separable.py --disable-warnings --maxfail=1"}
rm -rf /work/src
cp -a "$src" /work/src
cd /work/src
printf 'version = "5.0.4"\ngithash = "unknown"\nversion_info = (5, 0, 4)\n' > astropy/version.py
python /opt/xiaopu/astropy_minimal_build.py
python /opt/xiaopu/official_slice_runner.py --repo /work/src --expected-commit "$expected" --out /work/result.json -- bash -lc "$test_cmd"
cat /work/result.json
