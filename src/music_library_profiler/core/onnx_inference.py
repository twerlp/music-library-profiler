import ctypes
import logging
import os
import sys

import numpy as np
import librosa

logger = logging.getLogger(__name__)

MEL_BANDS = 128
MEL_FRAMES = 96
GENRE_SAMPLE_RATE = 16000
N_FFT = 1024
HOP_LENGTH = 256
FMAX = 4000
WINDOW = "hamming"

_session = None
_model_path = None
_ort = None


def _preload_cuda_libs():
    lib_dirs = []

    for base in sys.path:
        nvidia_root = os.path.join(base, "nvidia")
        if os.path.isdir(nvidia_root):
            for name in os.listdir(nvidia_root):
                lib_dir = os.path.join(nvidia_root, name, "lib")
                if os.path.isdir(lib_dir):
                    lib_dirs.append(lib_dir)

    if not lib_dirs:
        candidates = [
            os.path.expanduser("~/.local/lib/python3.10/site-packages/nvidia"),
            "/home/twerp/music-library-profiler/.venv/lib/python3.10/site-packages/nvidia",
        ]
        for nvidia_root in candidates:
            if os.path.isdir(nvidia_root):
                for name in os.listdir(nvidia_root):
                    lib_dir = os.path.join(nvidia_root, name, "lib")
                    if os.path.isdir(lib_dir):
                        lib_dirs.append(lib_dir)

    for d in lib_dirs:
        for fname in sorted(os.listdir(d)):
            if fname.startswith("lib") and fname.endswith(".so"):
                fpath = os.path.join(d, fname)
                try:
                    ctypes.CDLL(fpath, mode=ctypes.RTLD_GLOBAL)
                except OSError:
                    pass


_preload_cuda_libs()


def _get_ort():
    global _ort
    if _ort is None:
        import onnxruntime as ort

        _ort = ort
    return _ort


def load_onnx_session(model_path: str):
    global _session, _model_path
    if _session is not None and _model_path == model_path:
        return _session
    ort = _get_ort()
    try:
        _session = ort.InferenceSession(model_path, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    except Exception:
        _session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    _model_path = model_path
    provider = _session.get_providers()[0]
    logger.info(f"ONNX session loaded ({provider}), input={_session.get_inputs()[0].shape}")
    return _session


def compute_mel(audio: np.ndarray, sr: int) -> np.ndarray:
    audio = np.asarray(audio, dtype=np.float32).squeeze()
    if sr != GENRE_SAMPLE_RATE:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=GENRE_SAMPLE_RATE)
        sr = GENRE_SAMPLE_RATE

    min_samples = MEL_FRAMES * HOP_LENGTH + N_FFT
    if len(audio) < min_samples:
        audio = np.pad(audio, (0, min_samples - len(audio)), mode="constant")

    S = librosa.feature.melspectrogram(
        y=audio, sr=GENRE_SAMPLE_RATE,
        n_fft=N_FFT, hop_length=HOP_LENGTH, window=WINDOW,
        n_mels=MEL_BANDS, fmin=0, fmax=FMAX,
        power=1, center=True,
    )
    S = S[:, :MEL_FRAMES]
    if S.shape[1] < MEL_FRAMES:
        S = np.pad(S, ((0, 0), (0, MEL_FRAMES - S.shape[1])), mode="constant")
    S = np.log1p(S)
    return S.astype(np.float32)


def compute_genre_embeddings(audio_buffers: list[np.ndarray], onnx_session) -> list[np.ndarray]:
    mels = [compute_mel(audio, GENRE_SAMPLE_RATE) for audio in audio_buffers]
    batch = np.stack(mels, axis=0)
    results = onnx_session.run(["embeddings"], {"melspectrogram": batch})
    embeddings = results[0]
    return [embeddings[i].copy() for i in range(embeddings.shape[0])]
