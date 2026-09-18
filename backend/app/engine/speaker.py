"""
VoiceShield AI — Lightweight language-agnostic speaker embedding.

Deterministic 64-dim DSP descriptor: log band energies, spectral shape
moments, f0 statistics, and temporal energy dynamics.

This is a one-way mathematical transform — audio cannot be reconstructed
from the descriptor — keeping the DPDP posture intact at rest.
"""

import numpy as np

_DIM = 64
_MISMATCH_SIMILARITY = 0.80  # below this cosine similarity => mismatch


def extract_embedding(audio: np.ndarray, sr: int = 16000, dim: int = _DIM) -> np.ndarray:
    """Return a normalized float64 embedding vector for the whole utterance."""
    x = np.asarray(audio, dtype=np.float32)
    if x.size < 512:
        return np.zeros(dim, dtype=np.float64)

    vec: list[float] = []

    # ── 1) log band energies, 24 geomspace bands 80 Hz..Nyquist ─────────
    spec = np.abs(np.fft.rfft(x * np.hanning(x.size))) ** 2
    freqs = np.fft.rfftfreq(x.size, d=1.0 / sr)
    edges = np.geomspace(80.0, sr / 2.0, 25)
    for i in range(24):
        sel = (freqs >= edges[i]) & (freqs < edges[i + 1])
        e = float(np.mean(spec[sel])) if np.any(sel) else 0.0
        vec.append(float(np.log10(e + 1e-9)))

    # ── 2) spectral shape moments ───────────────────────────────────────
    total = float(np.sum(spec)) + 1e-9
    centroid = float(np.sum(freqs * spec) / total)
    spread = float(np.sqrt(float(np.sum(((freqs - centroid) ** 2) * spec)) / total))
    flatness = float(np.exp(np.mean(np.log(spec + 1e-9))) / (np.mean(spec) + 1e-9))
    cum = np.cumsum(spec)
    rolloff = float(np.searchsorted(cum, 0.85 * total) / max(1, spec.size))
    vec += [centroid / 1000.0, spread / 1000.0, flatness, rolloff]

    # ── 3) f0 statistics (language-independent voicing behaviour) ───────
    f0 = _yin_f0(x, sr)
    voiced = f0[f0 > 0]
    if voiced.size >= 3:
        vec += [
            float(np.mean(voiced)) / 400.0,
            float(np.std(voiced)) / 100.0,
            float(np.mean(np.abs(np.diff(voiced)))) / 50.0,
            float(voiced.size) / float(max(1, f0.size)),
        ]
    else:
        vec += [0.0, 0.0, 0.0, 0.0]

    # ── 4) temporal energy dynamics ─────────────────────────────────────
    frames = _frames(x, 400, 200)
    e = np.sqrt(np.mean(frames ** 2, axis=1)) + 1e-9
    db = 20.0 * np.log10(e / float(e.max()))
    vec += [
        float(np.std(db)) / 10.0,
        float(np.mean(np.abs(np.diff(db)))) / 5.0,
        float(np.mean(db < -35.0)),
        float(np.max(e) / (np.mean(e) + 1e-9) / 4.0),
    ]

    out = np.asarray(vec[:dim], dtype=np.float64)
    if out.size < dim:
        out = np.pad(out, (0, dim - out.size))
    norm = float(np.linalg.norm(out))
    return out / norm if norm > 1e-9 else out


def embedding_to_bytes(embedding: np.ndarray) -> bytes:
    return np.asarray(embedding, dtype=np.float64).tobytes()


def bytes_to_embedding(data: bytes) -> np.ndarray:
    return np.frombuffer(data, dtype=np.float64).copy()


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def is_speaker_mismatch(similarity: float, threshold: float = _MISMATCH_SIMILARITY) -> bool:
    return similarity < threshold


def _yin_f0(x: np.ndarray, sr: int) -> np.ndarray:
    try:
        import librosa

        f0, _vflag, _vprob = librosa.pyin(
            x, fmin=65, fmax=400, sr=sr, frame_length=1024, hop_length=320
        )
        return np.nan_to_num(np.asarray(f0, dtype=np.float64), nan=0.0)
    except Exception:  # noqa: BLE001
        return np.zeros(1)


def _frames(x: np.ndarray, n: int, hop: int) -> np.ndarray:
    count = max(1, 1 + (x.size - n) // hop)
    idx = np.arange(n)[None, :] + hop * np.arange(count)[:, None]
    return x[np.clip(idx, 0, x.size - 1)]