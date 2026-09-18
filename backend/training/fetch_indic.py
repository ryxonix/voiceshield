"""
VoiceShield AI — Real Indic Voice Dataset Downloader (v2)
Downloads genuine Indian voice data from google/fleurs via direct parquet download.

Strategy: Download parquet files directly using requests + pyarrow.
This bypasses the `datasets` library entirely, avoiding version conflicts
with torchcodec / dill / multiprocess that plague datasets 2.x and 5.x.

Datasets used (CC-BY-4.0, SIH-compliant):
  BONAFIDE: google/fleurs — real human Indian voice recordings
  SPOOF:    Locally generated phase-locked synthetic speech
"""

import os
import io
import logging
import argparse
import tempfile

import numpy as np
import soundfile as sf
import requests
import pyarrow.parquet as pq
from scipy.signal import resample_poly
from math import gcd

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

TARGET_SR = 16000

# FLEURS parquet URLs (direct download, no auth gate on public datasets)
FLEURS_PARQUET = {
    "hindi":   "https://huggingface.co/datasets/google/fleurs/resolve/main/parquet-data/hi_in/train-00000-of-00001.parquet",
    "english": "https://huggingface.co/datasets/google/fleurs/resolve/main/parquet-data/en_us/train-00000-of-00001.parquet",
    "kannada": "https://huggingface.co/datasets/google/fleurs/resolve/main/parquet-data/kn_in/train-00000-of-00001.parquet",
}


def resample_audio(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    if orig_sr == target_sr:
        return audio
    g = gcd(orig_sr, target_sr)
    return resample_poly(audio, target_sr // g, orig_sr // g).astype(np.float32)


from huggingface_hub import hf_hub_download

def download_parquet(language: str, token: str, cache_dir: str) -> str:
    """Download a parquet file from google/fleurs using huggingface_hub (atomic & cached)."""
    os.makedirs(cache_dir, exist_ok=True)
    subpaths = {
        "hindi":   ("hi_in", "train-00000-of-00001.parquet"),
        "english": ("en_us", "train-00000-of-00001.parquet"),
        "kannada": ("kn_in", "train-00000-of-00001.parquet"),
    }
    locale, filename = subpaths[language]
    logger.info(f"  Fetching parquet for {language} ({locale}) via HuggingFace Hub...")
    local_path = hf_hub_download(
        repo_id="google/fleurs",
        filename=f"parquet-data/{locale}/train-00000-of-00001.parquet",
        repo_type="dataset",
        token=token if token else None,
        local_dir=cache_dir,
    )
    logger.info(f"  Parquet ready at: {local_path}")
    return local_path


def extract_audio_from_parquet(parquet_path: str, num_samples: int, language: str, output_dir: str):
    """Read audio bytes from a FLEURS parquet file and save as 16kHz WAVs."""
    logger.info(f"  Reading parquet: {parquet_path}")
    table = pq.read_table(parquet_path)
    
    # Inspect available columns
    cols = table.column_names
    logger.info(f"  Columns: {cols}")

    # FLEURS audio column is 'audio' containing a struct with 'bytes'
    # In newer parquet format it may be stored differently
    audio_col = None
    for col in ["audio", "audio_path", "path"]:
        if col in cols:
            audio_col = col
            break
    
    if audio_col is None:
        raise ValueError(f"No audio column found in {cols}")

    file_paths = []
    labels = []
    saved = 0

    for i in range(min(num_samples, len(table))):
        try:
            row = table.slice(i, 1).to_pydict()
            audio_entry = row[audio_col][0]

            # Handle different formats
            if isinstance(audio_entry, dict):
                audio_bytes = audio_entry.get("bytes")
                audio_path  = audio_entry.get("path")
            elif isinstance(audio_entry, bytes):
                audio_bytes = audio_entry
                audio_path  = None
            else:
                logger.warning(f"  Unknown audio format at row {i}: {type(audio_entry)}")
                continue

            if audio_bytes:
                audio_data, sr = sf.read(io.BytesIO(audio_bytes))
            elif audio_path:
                audio_data, sr = sf.read(audio_path)
            else:
                continue

            audio_data = np.array(audio_data, dtype=np.float32)
            if audio_data.ndim > 1:
                audio_data = audio_data.mean(axis=1)
            if sr != TARGET_SR:
                audio_data = resample_audio(audio_data, sr, TARGET_SR)
            peak = np.max(np.abs(audio_data))
            if peak > 0:
                audio_data = audio_data / peak

            file_id = f"FLEURS_{language}_{saved:04d}"
            wav_path = os.path.join(output_dir, f"{file_id}.wav")
            sf.write(wav_path, audio_data, TARGET_SR)
            file_paths.append(file_id)
            labels.append("bonafide")
            saved += 1

            if saved % 50 == 0:
                logger.info(f"  [{language}] {saved}/{num_samples} bonafide saved...")

        except Exception as e:
            logger.warning(f"  Skipping row {i}: {e}")
            continue

    logger.info(f"  Extracted {saved} bonafide audio files for {language}")
    return file_paths, labels


# ── Sentence banks for each language (for TTS diversity) ─────────────────
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

# gTTS language codes
_GTTS_LANG = {"hindi": "hi", "kannada": "kn", "english": "en"}


def _gtts_synthesize(text: str, lang_code: str, output_path: str) -> bool:
    """Synthesize text with gTTS and save as 16kHz WAV. Returns True on success."""
    try:
        from gtts import gTTS
        import io as _io
        tts = gTTS(text=text, lang=lang_code, slow=False)
        mp3_buf = _io.BytesIO()
        tts.write_to_fp(mp3_buf)
        mp3_buf.seek(0)

        # Decode MP3 → float32 PCM via soundfile (uses libsndfile MP3 if available)
        # Fallback: use pydub if soundfile can't read mp3
        try:
            audio_data, sr = sf.read(mp3_buf, dtype="float32")
        except Exception:
            from pydub import AudioSegment
            mp3_buf.seek(0)
            seg = AudioSegment.from_mp3(mp3_buf)
            seg = seg.set_frame_rate(TARGET_SR).set_channels(1)
            samples = np.array(seg.get_array_of_samples(), dtype=np.float32)
            audio_data = samples / (2 ** (seg.sample_width * 8 - 1))
            sr = TARGET_SR

        audio_data = np.array(audio_data, dtype=np.float32)
        if audio_data.ndim > 1:
            audio_data = audio_data.mean(axis=1)
        if sr != TARGET_SR:
            audio_data = resample_audio(audio_data, sr, TARGET_SR)
        peak = np.max(np.abs(audio_data))
        if peak > 0:
            audio_data /= peak

        sf.write(output_path, audio_data, TARGET_SR)
        return True
    except Exception as e:
        logger.debug(f"gTTS failed for '{text[:30]}...': {e}")
        return False


def _voiced_noise_fallback(duration: float, output_path: str):
    """
    Voiced noise fallback — NOT a pure sine/beep.
    Uses shaped noise (pink noise filtered through a vocal tract envelope)
    to produce a voice-like waveform when gTTS is unavailable.
    """
    from scipy.signal import lfilter
    t = np.linspace(0, duration, int(TARGET_SR * duration), False)
    # Random F0 in voiced range
    f0 = np.random.uniform(100, 250)
    # Source: glottal pulse train (buzz)
    pulse = np.zeros_like(t)
    period_samples = int(TARGET_SR / f0)
    pulse[::period_samples] = 1.0
    # Vocal tract: simple 2-pole resonance filter (formants F1~700Hz, F2~1200Hz)
    b = [1.0]
    a = [1.0, -1.4, 0.6]  # approximate vocal tract
    voiced = lfilter(b, a, pulse)
    # Mix with shaped noise for breathiness
    noise = np.random.randn(len(t)) * 0.1
    audio = voiced + noise
    audio = audio / (np.max(np.abs(audio)) + 1e-8)
    sf.write(output_path, audio.astype(np.float32), TARGET_SR)


def generate_spoof_samples(language: str, num_samples: int, output_dir: str):
    """
    Generate realistic TTS-based spoof samples using gTTS (Google TTS).
    This replaces the previous sine-wave generator which produced beep sounds.
    Falls back to voiced-noise synthesis (not pure tones) if network unavailable.
    """
    file_paths, labels = [], []
    lang_code = _GTTS_LANG.get(language, "hi")
    sentences = SENTENCE_BANKS.get(language, SENTENCE_BANKS["hindi"])

    logger.info(f"  Generating {num_samples} TTS spoof samples for {language} (lang={lang_code})...")

    gtts_ok = True  # track if gTTS is working
    for i in range(num_samples):
        file_id = f"SPOOF_{language}_{i:04d}"
        wav_path = os.path.join(output_dir, f"{file_id}.wav")

        # Cycle through sentence bank with slight variation
        text = sentences[i % len(sentences)]
        success = False

        if gtts_ok:
            success = _gtts_synthesize(text, lang_code, wav_path)
            if not success:
                gtts_ok = False  # stop trying gTTS after first failure
                logger.warning("  gTTS unavailable (no internet?), switching to voiced-noise fallback.")

        if not success:
            duration = np.random.uniform(1.5, 3.0)
            _voiced_noise_fallback(duration, wav_path)

        file_paths.append(file_id)
        labels.append("spoof")

        if (i + 1) % 50 == 0:
            src = "gTTS" if gtts_ok else "voiced-noise"
            logger.info(f"  [{language}] {i+1}/{num_samples} spoof samples saved ({src})...")

    src = "gTTS" if gtts_ok else "voiced-noise fallback"
    logger.info(f"  Generated {num_samples} spoof samples for {language} via {src}")
    return file_paths, labels


def fetch_and_write_protocol(language, num_bonafide, num_spoof, output_dir, token=""):
    os.makedirs(output_dir, exist_ok=True)
    cache_dir = os.path.join(output_dir, ".parquet_cache")
    
    url = FLEURS_PARQUET.get(language)
    if not url:
        raise ValueError(f"Unknown language '{language}'. Supported: {list(FLEURS_PARQUET)}")

    logger.info(f"\nVoiceShield AI — Indic Dataset Download")
    logger.info(f"  Language : {language}")
    logger.info(f"  Source   : google/fleurs (CC-BY 4.0, SIH-compliant)")
    logger.info(f"  Bonafide : {num_bonafide} real FLEURS samples")
    logger.info(f"  Spoof    : {num_spoof} synthetic samples")
    logger.info(f"  Output   : {output_dir}")

    # Step 1: Download parquet via hf_hub_download
    parquet_path = download_parquet(language, token, cache_dir)

    # Step 2: Extract bonafide audio
    bonafide_ids, bonafide_labels = extract_audio_from_parquet(
        parquet_path, num_bonafide, language, output_dir
    )

    # Step 3: Generate spoof audio
    spoof_ids, spoof_labels = generate_spoof_samples(language, num_spoof, output_dir)

    # Step 4: Write ASVspoof protocol
    all_ids    = bonafide_ids + spoof_ids
    all_labels = bonafide_labels + spoof_labels
    protocol_path = os.path.join(output_dir, f"{language}_protocol.txt")
    with open(protocol_path, "w") as f:
        for idx, (fid, lbl) in enumerate(zip(all_ids, all_labels)):
            spk = f"SPK_{idx % 20:02d}"
            atk = "-" if lbl == "bonafide" else "A01"
            f.write(f"{spk} {fid} - {atk} {lbl}\n")

    logger.info(
        f"\n{language.upper()} protocol written: {protocol_path}\n"
        f"  Bonafide: {len(bonafide_ids)}\n"
        f"  Spoof:    {len(spoof_ids)}\n"
        f"  Total:    {len(all_ids)}"
    )
    return protocol_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download real Indic voices from google/fleurs")
    parser.add_argument("--language",  type=str, default="hindi",
                        choices=list(FLEURS_PARQUET.keys()))
    parser.add_argument("--bonafide",  type=int, default=200)
    parser.add_argument("--spoof",     type=int, default=200)
    parser.add_argument("--out",       type=str, default="data/indic")
    parser.add_argument("--token",     type=str, default=os.environ.get("HF_TOKEN", ""))
    args = parser.parse_args()

    fetch_and_write_protocol(
        language=args.language,
        num_bonafide=args.bonafide,
        num_spoof=args.spoof,
        output_dir=args.out,
        token=args.token,
    )
