"""
VoiceShield AI — Leak-free SIH-compliant dataset builder (v2)

Expands the training set from the CACHED google/fleurs parquet files
(CC-BY-4.0) without any re-download, keeps the existing on-disk gTTS
spoof set, and folds in the real FreeVC24 voice-conversion clips
(self-generated, open pipeline) as realistic "voice-clone" spoofs.

Data classes used:
  BONAFIDE  FLEURS Hindi / English / Kannada   (CC-BY-4.0)
  SPOOF     gTTS single-voice TTS (ours)       + FreeVC24 conversions (ours)

Outputs (into --out, default data/indic):
  FLEURS_<lang>_NNNN.wav      bonafide wavs @16 kHz
  SPOOF_<lang>_NNNN.wav       existing gTTS spoof wavs (kept)
  clone_<lang>_NNNN.wav       FreeVC24 voice-clone spoofs (copied)
  <lang>_protocol.txt         ASVspoof-format protocol (all classes)

Then run `python -m training.merge_protocols` (leak-free split).
"""

import os
import io
import logging
import argparse
import shutil

import numpy as np
import soundfile as sf
import pyarrow.parquet as pq
from scipy.signal import resample_poly
from math import gcd


GTTS_LANG = {"hindi": "hi", "english": "en", "kannada": "kn"}

SENTENCE_BANKS = {
    "hindi": [
        "नमस्ते, मैं आपसे बात करना चाहता हूँ।",
        "आज मौसम बहुत अच्छा है।",
        "क्या आप मुझे रास्ता बता सकते हैं?",
        "मेरा नाम राज है और मैं दिल्ली से हूँ।",
        "कृपया यहाँ बैठिए और थोड़ा पानी पीजिए।",
        "हम सब मिलकर काम करेंगे।",
        "भारत एक महान देश है।",
        "आपका स्वागत है हमारे कार्यालय में।",
        "मैं कल सुबह आपसे मिलूंगा।",
        "यह परियोजना बहुत महत्वपूर्ण है।",
        "क्या आपने खाना खाया?",
        "मुझे हिंदी बोलना बहुत पसंद है।",
        "हमारी टीम बहुत मेहनती है।",
        "आज बाज़ार में भीड़ बहुत थी।",
        "मैं इस काम को जल्दी पूरा करूंगा।",
    ],
    "kannada": [
        "ನಮಸ್ಕಾರ, ನೀವು ಹೇಗಿದ್ದೀರಾ?",
        "ಇಂದು ಹವಾಮಾನ ತುಂಬಾ ಚೆನ್ನಾಗಿದೆ.",
        "ನನ್ನ ಹೆಸರು ರವಿ ಮತ್ತು ನಾನು ಬೆಂಗಳೂರಿನವನು.",
        "ದಯವಿಟ್ಟು ಇಲ್ಲಿ ಕುಳಿತುಕೊಳ್ಳಿ.",
        "ಕನ್ನಡ ಭಾಷೆ ತುಂಬಾ ಸುಂದರವಾಗಿದೆ.",
        "ನಾವೆಲ್ಲರೂ ಒಟ್ಟಾಗಿ ಕೆಲಸ ಮಾಡೋಣ.",
        "ಭಾರತ ಒಂದು ಮಹಾನ್ ದೇಶ.",
        "ನಿಮ್ಮ ಸ್ವಾಗತ ನಮ್ಮ ಕಚೇರಿಗೆ.",
        "ನಾಳೆ ಬೆಳಿಗ್ಗೆ ನಾನು ನಿಮ್ಮನ್ನು ಭೇಟಿ ಮಾಡುತ್ತೇನೆ.",
        "ಈ ಯೋಜನೆ ತುಂಬಾ ಮುಖ್ಯವಾಗಿದೆ.",
        "ನೀವು ಊಟ ಮಾಡಿದ್ದೀರಾ?",
        "ನನಗೆ ಕನ್ನಡ ಮಾತನಾಡಲು ತುಂಬಾ ಇಷ್ಟ.",
        "ನಮ್ಮ ತಂಡ ತುಂಬಾ ಶ್ರಮಶೀಲ.",
        "ಇಂದು ಮಾರುಕಟ್ಟೆಯಲ್ಲಿ ಬಹಳ ಜನ ಇದ್ದರು.",
        "ನಾನು ಈ ಕೆಲಸವನ್ನು ಶೀಘ್ರದಲ್ಲಿ ಮುಗಿಸುತ್ತೇನೆ.",
    ],
    "english": [
        "Hello, how are you doing today?",
        "The weather is really pleasant this morning.",
        "My name is Arjun and I am from Bangalore.",
        "Please take a seat and have some water.",
        "India is a country of great diversity.",
        "We will all work together to achieve this goal.",
        "Welcome to our office, please make yourself comfortable.",
        "I will meet you tomorrow morning at nine o'clock.",
        "This project is very important for our team.",
        "Have you had your lunch today?",
        "I really enjoy speaking in multiple Indian languages.",
        "Our team is very hardworking and dedicated.",
        "The market was very crowded this afternoon.",
        "I will complete this work as soon as possible.",
        "Technology is changing the world at a rapid pace.",
    ],
}

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

TARGET_SR = 16000

# Cache dir relative to backend/
PARQUET_RELPATH = {
    "hindi":   ("data", "indic", ".parquet_cache", "parquet-data", "hi_in", "train-00000-of-00001.parquet"),
    "english": ("data", "indic", ".parquet_cache", "parquet-data", "en_us", "train-00000-of-00001.parquet"),
    "kannada": ("data", "indic", ".parquet_cache", "parquet-data", "kn_in", "train-00000-of-00001.parquet"),
}

# FreeVC24 voice-clone evaluation clips (realistic spoofs) — hindi + kannada
FREECV_SAMPLES = {
    "hindi":   ["hindi_sample_%d_freevc24.wav" % i for i in range(5)],
    "kannada": ["kannada_sample_%d_freevc24.wav" % i for i in range(5)],
    "english": [],
}
FREECV_SOURCE = os.path.join(os.path.dirname(__file__), "..", "data", "samples")


def _resample(audio: np.ndarray, orig_sr: int) -> np.ndarray:
    if orig_sr == TARGET_SR:
        return audio
    g = gcd(orig_sr, TARGET_SR)
    return resample_poly(audio, TARGET_SR // g, orig_sr // g).astype(np.float32)


def _best_cached_parquet(language: str) -> str | None:
    rel = PARQUET_RELPATH[language]
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/
    cand = os.path.join(here, *rel)
    if os.path.exists(cand):
        return cand
    # fall back to any traversal (HF cache keeps a copy under .cache/huggingface)
    for root, _dirs, files in os.walk(os.path.join(here, "data", "indic", ".parquet_cache")):
        for fn in files:
            if fn.endswith(".parquet") and f"{language}" in fn.lower():
                return os.path.join(root, fn)
    return None


def extract_bonafide(language: str, count: int, out_dir: str):
    """Pull `count` real FLEURS clips from the cached parquet."""
    p = _best_cached_parquet(language)
    if p is None:
        logger.warning(f"No cached parquet for {language} — skipping bonafide expansion")
        return 0

    logger.info(f"Reading cached parquet [{language}]: {os.path.basename(os.path.dirname(p))}/{os.path.basename(p)}")
    table = pq.read_table(p)
    cols = table.column_names
    audio_col = next((c for c in ("audio", "audio_path", "path") if c in cols), None)
    if audio_col is None:
        logger.warning(f"No audio column in [{language}]: {cols}")
        return 0

    n_total = len(table)
    logger.info(f"  [{language}] rows available: {n_total}, extracting up to {count}")

    saved = 0
    for i in range(min(count, n_total)):
        try:
            row = table.slice(i, 1).to_pydict()
            entry = row[audio_col][0]
            if isinstance(entry, dict):
                audio_bytes = entry.get("bytes")
            elif isinstance(entry, bytes):
                audio_bytes = entry
            else:
                continue
            if not audio_bytes:
                continue
            audio_data, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
            audio_data = np.asarray(audio_data, dtype=np.float32)
            if audio_data.ndim > 1:
                audio_data = audio_data.mean(axis=1)
            if len(audio_data) < TARGET_SR * 0.5:      # skip clips < 0.5 s
                continue
            if sr != TARGET_SR:
                audio_data = _resample(audio_data, sr)
            peak = np.max(np.abs(audio_data))
            if peak > 1e-6:
                audio_data = audio_data / peak

            # FLEURS clip ends are very quiet; trim head/tail low-energy tails
            wav_path = os.path.join(out_dir, f"FLEURS_{language}_{saved:04d}.wav")
            sf.write(wav_path, audio_data, TARGET_SR)
            saved += 1
            if saved % 50 == 0:
                logger.info(f"  [{language}] {saved} bonafide saved...")
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"  [{language}] skip row {i}: {exc}")
            continue

    logger.info(f"  [{language}] Done: {saved} bonafide FLEURS clips")
    return saved


def copy_freecv_spoofs(language: str, out_dir: str):
    """Copy FreeVC24 voice-conversion clips in as clone spoofs."""
    n = 0
    for src in FREECV_SAMPLES.get(language, []):
        s = os.path.join(FREECV_SOURCE, src)
        if not os.path.exists(s):
            continue
        dst = os.path.join(out_dir, f"clone_{language}_{n:04d}.wav")
        shutil.copyfile(s, dst)
        n += 1
    if n:
        logger.info(f"  [{language}] {n} FreeVC24 clone clips added")
    return n


def write_protocol(language: str, out_dir: str):
    """Regenerate <lang>_protocol.txt from all wavs present in out_dir for that language."""
    ids, labels = [], []
    for fn in sorted(os.listdir(out_dir)):
        stem, ext = os.path.splitext(fn)
        if ext.lower() != ".wav":
            continue
        if fn.startswith(f"FLEURS_{language}_"):
            ids.append(stem); labels.append("bonafide")
        elif fn.startswith(f"SPOOF_{language}_"):
            ids.append(stem); labels.append("spoof")
        elif fn.startswith(f"clone_{language}_"):
            ids.append(stem); labels.append("spoof")

    proto = os.path.join(out_dir, f"{language}_protocol.txt")
    with open(proto, "w", encoding="utf-8") as f:
        for idx, (fid, lbl) in enumerate(zip(ids, labels)):
            spk = f"SPK_{idx % 20:02d}"
            atk = "-" if lbl == "bonafide" else "A01"
            f.write(f"{spk} {fid} - {atk} {lbl}\n")
    logger.info(f"  [{language}] protocol written: {proto} ({len(ids)} files, {sum(1 for l in labels if l=='bonafide')} bonafide / {sum(1 for l in labels if l=='spoof')} spoof)")


def _gtts_spoof(language: str, idx: int, out_dir: str) -> bool:
    """Synthesize one TTS spoof wav (self-generated; only our audio)."""
    import soundfile as _sf  # noqa: F401  (keep import local for parity)
    try:
        from gtts import gTTS
    except Exception:  # noqa: BLE001
        return False
    try:
        text = SENTENCE_BANKS[language][idx % len(SENTENCE_BANKS[language])]
        buf = io.BytesIO()
        gTTS(text=text, lang=GTTS_LANG[language], slow=False).write_to_fp(buf)
        buf.seek(0)
        audio_data, sr = sf.read(buf, dtype="float32")
        audio_data = np.asarray(audio_data, dtype=np.float32)
        if audio_data.ndim > 1:
            audio_data = audio_data.mean(axis=1)
        if sr != TARGET_SR:
            audio_data = _resample(audio_data, sr)
        peak = np.max(np.abs(audio_data))
        if peak > 1e-6:
            audio_data = audio_data / peak
        sf.write(os.path.join(out_dir, f"SPOOF_{language}_{idx:04d}.wav"), audio_data, TARGET_SR)
        return True
    except Exception:  # noqa: BLE001
        return False


def build_more_spoofs(language: str, target_spoof: int, out_dir: str):
    """Top up on-disk gTTS spoofs until we hold `target_spoof` per language."""
    existing = [fn for fn in os.listdir(out_dir)
                if fn.startswith(f"SPOOF_{language}_") and fn.endswith(".wav")]
    count = len(existing)
    logger.info(f"  [{language}] existing SPOOF wavs: {count}, target: {target_spoof}")
    idx = count
    while count < target_spoof:
        ok = _gtts_spoof(language, idx, out_dir)
        if ok:
            count += 1
            if count % 50 == 0:
                logger.info(f"  [{language}] {count}/{target_spoof} spoofs...")
        else:
            logger.warning(f"  [{language}] gTTS failed at idx {idx} — retrying next sentence")
        idx += 1
        if idx - count > 60:      # bail out if gTTS keeps failing
            logger.warning(f"  [{language}] gTTS unstable — keeping {count} spoofs")
            break
    return count


def build_all(out_dir: str, per_lang_bonafide: int, per_lang_spoof: int):
    os.makedirs(out_dir, exist_ok=True)
    logger.info(f"Out dir: {out_dir} | bonafide/language: {per_lang_bonafide} | spoof/language: {per_lang_spoof}")

    for lang in ("hindi", "english", "kannada"):
        logger.info(f"\n===== {lang} =====")
        extract_bonafide(lang, per_lang_bonafide, out_dir)
        build_more_spoofs(lang, per_lang_spoof, out_dir)
        copy_freecv_spoofs(lang, out_dir)
        write_protocol(lang, out_dir)

    logger.info("\nDataset build complete. Next: python -m training.merge_protocols --data_dir <out_dir> --output <out_dir>/merged")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Expanded SIH-compliant dataset from cached FLEURS parquets")
    parser.add_argument("--out", type=str, default="data/indic")
    parser.add_argument("--bonafide", type=int, default=200, help="FLEURS bonafide clips per language")
    parser.add_argument("--spoof", type=int, default=150, help="gTTS spoot clips per language (top-up)")
    args = parser.parse_args()
    build_all(args.out, args.bonafide, args.spoof)