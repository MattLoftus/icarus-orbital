"""Fast C-backed evaluation for GTOP benchmarks via ctypes.

Provides drop-in replacements for cassini1_gtop_evaluate and cassini2_evaluate
that run ~100× faster by calling compiled C code.
"""

import os
import ctypes
import numpy as np
from numpy.ctypeslib import ndpointer

# Load the shared library
_lib_path = os.path.join(os.path.dirname(__file__), 'gtop_eval.dylib')
_lib = ctypes.CDLL(_lib_path)

# Cassini1: double cassini1_eval(const double *x)  — 6 variables
_lib.cassini1_eval.argtypes = [ndpointer(ctypes.c_double, flags='C_CONTIGUOUS')]
_lib.cassini1_eval.restype = ctypes.c_double

# Cassini2: double cassini2_eval(const double *x)  — 22 variables
_lib.cassini2_eval.argtypes = [ndpointer(ctypes.c_double, flags='C_CONTIGUOUS')]
_lib.cassini2_eval.restype = ctypes.c_double


def cassini1_evaluate_fast(x):
    """Evaluate Cassini1 GTOP objective (C implementation)."""
    return _lib.cassini1_eval(np.ascontiguousarray(x, dtype=np.float64))


def cassini2_evaluate_fast(x):
    """Evaluate Cassini2 GTOP objective (C implementation)."""
    return _lib.cassini2_eval(np.ascontiguousarray(x, dtype=np.float64))
