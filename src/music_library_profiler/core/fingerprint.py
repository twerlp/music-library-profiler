import ctypes
import ctypes.util
import logging

import numpy as np

logger = logging.getLogger(__name__)

_chromaprint = None


def _load_lib():
    global _chromaprint
    if _chromaprint is not None:
        return _chromaprint

    libpath = ctypes.util.find_library("chromaprint")
    if libpath is None:
        libpath = "libchromaprint.so.1"

    try:
        lib = ctypes.CDLL(libpath, use_errno=True)
        lib.chromaprint_get_version.restype = ctypes.c_char_p
        _chromaprint = lib
        return lib
    except OSError:
        return None


def compute_fingerprint(audio: np.ndarray, sr: int) -> tuple[str, float] | None:
    lib = _load_lib()
    if lib is None:
        return None

    try:
        pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
        num_samples = pcm.size

        lib.chromaprint_new.argtypes = [ctypes.c_int]
        lib.chromaprint_new.restype = ctypes.c_void_p
        ctx = lib.chromaprint_new(0)

        if not ctx:
            return None

        lib.chromaprint_start.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        lib.chromaprint_start.restype = ctypes.c_int

        if not lib.chromaprint_start(ctx, sr, 1):
            lib.chromaprint_free(ctx)
            return None

        ptr = pcm.ctypes.data_as(ctypes.c_void_p)
        lib.chromaprint_feed.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
        lib.chromaprint_feed.restype = ctypes.c_int

        if not lib.chromaprint_feed(ctx, ptr, num_samples):
            lib.chromaprint_free(ctx)
            return None

        lib.chromaprint_finish.argtypes = [ctypes.c_void_p]
        lib.chromaprint_finish.restype = ctypes.c_int

        if not lib.chromaprint_finish(ctx):
            lib.chromaprint_free(ctx)
            return None

        lib.chromaprint_get_fingerprint.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p)]
        lib.chromaprint_get_fingerprint.restype = ctypes.c_int

        fp_ptr = ctypes.c_char_p()
        ok = lib.chromaprint_get_fingerprint(ctx, ctypes.byref(fp_ptr))
        if not ok or not fp_ptr.value:
            lib.chromaprint_free(ctx)
            return None

        fingerprint = fp_ptr.value.decode("utf-8")

        lib.chromaprint_dealloc.argtypes = [ctypes.c_void_p]
        lib.chromaprint_dealloc(fp_ptr)

        lib.chromaprint_free.argtypes = [ctypes.c_void_p]
        lib.chromaprint_free.restype = None
        lib.chromaprint_free(ctx)

        duration = num_samples / sr
        return fingerprint, duration

    except Exception as e:
        logger.debug(f"Fingerprint computation failed: {e}")
        return None
