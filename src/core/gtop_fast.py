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
_int_arr = ndpointer(ctypes.c_int, flags='C_CONTIGUOUS')

for name in ['cassini1_eval', 'cassini2_eval', 'messenger_eval', 'rosetta_eval']:
    fn = getattr(_lib, name)
    fn.argtypes = [_dbl_arr]
    fn.restype = ctypes.c_double

_lib.generic_mga_1dsm_eval.argtypes = [_dbl_arr, _int_arr, ctypes.c_int, ctypes.c_int]
_lib.generic_mga_1dsm_eval.restype = ctypes.c_double

# Body name to C index mapping
BODY_INDEX = {
    'mercury': 0, 'venus': 1, 'earth': 2, 'mars': 3,
    'jupiter': 4, 'saturn': 5, 'uranus': 6, 'neptune': 7,
}


def cassini1_evaluate_fast(x):
    return _lib.cassini1_eval(np.ascontiguousarray(x, dtype=np.float64))

def cassini2_evaluate_fast(x):
    return _lib.cassini2_eval(np.ascontiguousarray(x, dtype=np.float64))

def messenger_evaluate_fast(x):
    return _lib.messenger_eval(np.ascontiguousarray(x, dtype=np.float64))

def rosetta_evaluate_fast(x):
    return _lib.rosetta_eval(np.ascontiguousarray(x, dtype=np.float64))


def make_generic_evaluator(sequence, add_vinf_dep=True):
    """Create a fast C-backed evaluator for an arbitrary planetary sequence.

    Args:
        sequence: list of body names, e.g. ['earth', 'venus', 'earth', 'jupiter']
        add_vinf_dep: include departure v_inf in objective

    Returns:
        evaluate(x) function that calls the C generic_mga_1dsm_eval
    """
    seq_arr = np.array([BODY_INDEX[b] for b in sequence], dtype=np.int32)
    n_bodies = len(sequence)
    vinf_flag = 1 if add_vinf_dep else 0

    def evaluate(x):
        return _lib.generic_mga_1dsm_eval(
            np.ascontiguousarray(x, dtype=np.float64),
            seq_arr, n_bodies, vinf_flag,
        )

    return evaluate
