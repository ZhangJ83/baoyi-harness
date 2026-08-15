"""Build only the Astropy extensions needed by the separable test slice.

Run from an exact-commit Astropy source checkout.  This is intentionally a
small diagnostic build, not a replacement for the official SWE-bench image.
"""
import os, glob
from setuptools import Extension, setup
import numpy as np
from Cython.Build import cythonize

root = os.getcwd()
include = [os.path.join(root, "astropy", "utils", "include"), np.get_include()]
extensions = [
    Extension("astropy.utils._compiler", ["astropy/utils/src/compiler.c"], include_dirs=include),
    Extension("astropy.table._column_mixins", ["astropy/table/_column_mixins.pyx"], include_dirs=include),
    Extension("astropy.table._np_utils", ["astropy/table/_np_utils.pyx"], include_dirs=include),
    Extension("astropy.io.ascii.cparser", ["astropy/io/ascii/cparser.pyx", "astropy/io/ascii/src/tokenizer.c"], include_dirs=include),
    Extension("astropy.time._parse_times", ["astropy/time/src/parse_times.c"], include_dirs=include),
    Extension("astropy.io.fits._utils", ["astropy/io/fits/_utils.pyx"], include_dirs=include, libraries=["cfitsio"]),
]
wcs_root = os.path.join(root, "astropy", "wcs")
wcs_sources = [
    os.path.join(wcs_root, "src", name) for name in [
        "distortion.c", "distortion_wrap.c", "docstrings.c", "pipeline.c",
        "pyutil.c", "astropy_wcs.c", "astropy_wcs_api.c", "sip.c", "sip_wrap.c",
        "str_list_proxy.c", "unit_list_proxy.c", "util.c", "wcslib_wrap.c",
        "wcslib_auxprm_wrap.c", "wcslib_prjprm_wrap.c", "wcslib_celprm_wrap.c",
        "wcslib_tabprm_wrap.c", "wcslib_wtbarr_wrap.c"]
]
wcs_sources += [os.path.join(root, "cextern", "wcslib", "C", name) for name in [
    "flexed/wcsbth.c", "flexed/wcspih.c", "flexed/wcsulex.c", "flexed/wcsutrn.c",
    "cel.c", "dis.c", "lin.c", "log.c", "prj.c", "spc.c", "sph.c", "spx.c",
    "tab.c", "wcs.c", "wcserr.c", "wcsfix.c", "wcshdr.c", "wcsprintf.c",
    "wcsunits.c", "wcsutil.c"]]
extensions.append(Extension("astropy.wcs._wcs", wcs_sources,
    include_dirs=include + [os.path.join(wcs_root, "include"), os.path.join(root, "cextern", "wcslib", "C")],
    define_macros=[("ASTROPY_WCS_BUILD", "1")],
    extra_compile_args=["-include", "astropy_wcs/astropy_wcs_api.h"]))
setup(script_args=["build_ext", "--inplace"], ext_modules=cythonize(extensions, language_level=3))
