"""Fast C-backed evaluation for GTOP benchmarks via ctypes.

Provides drop-in replacements for all GTOP benchmark objectives
that run ~100× faster by calling compiled C code.
"""

import os
import ctypes
import numpy as np
from numpy.ctypeslib import ndpointer

# Load the shared library
_lib_path = os.path.join(os.path.dirname(__file__), 'gtop_eval.dylib')
_lib = ctypes.CDLL(_lib_path)

_dbl_arr = ndpointer(ctypes.c_double, flags='C_CONTIGUOUS')

for name in ['cassini1_eval', 'cassini2_eval', 'messenger_eval', 'rosetta_eval']:
    fn = getattr(_lib, name)
    fn.argtypes = [_dbl_arr]
    fn.restype = ctypes.c_double


def cassini1_evaluate_fast(x):
    return _lib.cassini1_eval(np.ascontiguousarray(x, dtype=np.float64))

def cassini2_evaluate_fast(x):
    return _lib.cassini2_eval(np.ascontiguousarray(x, dtype=np.float64))

def messenger_evaluate_fast(x):
    return _lib.messenger_eval(np.ascontiguousarray(x, dtype=np.float64))

def rosetta_evaluate_fast(x):
    return _lib.rosetta_eval(np.ascontiguousarray(x, dtype=np.float64))
