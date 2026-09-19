"""
VoiceShield AI — Cloud Dataset Builder (SIH-compliant, large-scale)

Designed to run inside free GPU notebooks: Google Colab & Kaggle.
Builds a BIG balanced corpus of:

    BONAFIDE  (real human speech)
        - google/fleurs   (CC-BY-4.0): hi, en, kn, ta, te, ml
        - mozilla Common Voice 17.0 (CC-BY-4.0; CC0 <= v13): hi, kn, ta, te, ml, en

    SPOOF     (REAL A.I. VOICE IMPERSONATION — cloned/converted voices)
        - Coqui XTTS-v2   (open voice-cloning model, CPML-1.0, free):
            clones the ACTUAL FLEURS/CommonVoice speaker's voice to say
            attacker-style phrases  → same-speaker impersonation.
            Languages: en, hi (and 15 more from XTTS multilingual).
        - RVC (Retrieval-based Voice Conversion)  (MIT, any language):
            converts real clips into a cloned target voice.
        - FreeVC / FreeVC24 (MIT, any language):
            zero-shot voice conversion with a pre-trained model.
        - edge-tts / gTTS (TTS) is kept ONLY as a small minority class
          representing the weaker "pure TTS" attack family.

Why this matters for SIH "Real-time AI voice detection / voice
impersonation": the model must catch someone whose VOICE was cloned and
replayed in real time. Plain TTS is a different (and easier) attack;
the dominant real-world attack is XTTS/RVC/FreeVC-style cloning, so the
training spoofs impersonate the SAME speakers the model logs as honest.

ALL data is CC-BY-4.0 / CC0 (<= v13) / self-generated ⇒ SIH-safe (see
SOURCES_AND_TECHNOLOGY.md). Licensed-research-only sets (ASVspoof) are
deliberately NOT bundled.

Output: balanced train/val CSVs
    audio_path | label | language | split
and an optional push to the Hugging Face Hub so all notebooks share
one dataset URL.
"""

import os
import io
import argparse
import random
import logging

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cloud")


def _load_audio(sample):
    """Extract (np.float32 mono array, sample_rate, file_path) from an HF dataset
    audio sample.  Works with both datasets 2.x (dict) and 3.x+torchcodec
    (AudioDecoder object)."""
    import io
    audio = sample["audio"]
    # ── datasets 2.x / decode=False: plain dict ─────────────────────────
    if isinstance(audio, dict):
        path = audio.get("path", "") or ""
        sr = audio.get("sampling_rate", 16000)
        if "array" in audio and audio["array"] is not None:
            return _to_mono(np.asarray(audio["array"], dtype=np.float32)), sr, path
        if "bytes" in audio and audio["bytes"] is not None:
            import soundfile as sf_mod
            buf = io.BytesIO(audio["bytes"])
            data, sr = sf_mod.read(buf, dtype="float32")
            return _to_mono(data), sr, path
    # ── datasets 3.x + torchcodec: AudioDecoder with get_all_samples() ──
    if hasattr(audio, "get_all_samples"):
        samples = audio.get_all_samples()
        arr = samples.data
        sr = samples.sample_rate
        if hasattr(arr, "cpu"):
            arr = arr.cpu().numpy()
        path = getattr(audio, "metadata", None)
        path = getattr(path, "path", "") or ""
        return _to_mono(np.asarray(arr, dtype=np.float32)), sr, path
    # ── fallback ────────────────────────────────────────────────────────
    return _to_mono(np.asarray(audio, dtype=np.float32)), 16000, ""


def _to_mono(arr):
    """Collapse to 1D mono, handling both (channels, samples) and (samples,
    channels) layouts."""
    if arr.ndim == 1:
        return arr
    if arr.ndim > 1:
        if arr.shape[0] <= 4:  # (channels, samples) — torchcodec / HF
            return arr.mean(axis=0) if arr.shape[0] > 1 else arr[0]
        return arr.mean(axis=1) if arr.shape[1] > 1 else arr[:, 0]
    return arr.reshape(-1)

# ── edge-tts voices (auxiliary pure-TTS minority class, no key) ─────────────
EDGE_VOICES = {
    "hindi":   [f"hi-IN-{n}Neural" for n in ["Kavya", "Madhur", "Swara"]],
    "english": [f"en-IN-{n}Neural" for n in ["Neerja", "Prabhat"]],
    "kannada": [f"kn-IN-{n}Neural" for n in ["Gagan", "Sapna"]],
    "tamil":   [f"ta-IN-{n}Neural" for n in ["Pallavi", "Valluvar"]],
    "telugu":  [f"te-IN-{n}Neural" for n in ["Mohan", "Shruti"]],
    "marathi": [f"mr-IN-{n}Neural" for n in ["Aarohi", "Manohar"]],
    "malayalam": [f"ml-IN-{n}Neural" for n in ["Midhun", "Sobhana"]],
    "bengali": [f"bn-IN-{n}Neural" for n in ["Bashkar", "Tanishaa"]],
    "gujarati": [f"gu-IN-{n}Neural" for n in ["Dhwani", "Niranjan"]],
}

SPOOF_PROMPTS = {
    "hindi": [
        "नमस्ते, क्या आप मेरी मदद कर सकते हैं? मेरा बैंक खाता बंद हो गया है।",
        "मैंने कल एक पैकेज भेजा था, क्या वह डिलीवर हुआ?",
        "कृपया अपना ओटीपी साझा न करें, यह सुरक्षा के लिए है।",
        "आपको तुरंत कार्रवाई करनी होगी, वरना आपका खाता जब्त हो जाएगा।",
        "मैं कस्टमर केयर से बोल रहा हूँ, आपकी जानकारी गलत है।",
    ],
    "english": [
        "Hello, could you please verify your account immediately?",
        "I haven't received my OTP, please resend it right away.",
        "This is an urgent matter regarding your electricity bill.",
        "Please confirm the last four digits of your card for security.",
        "We detected unusual activity, respond within five minutes.",
    ],
    "kannada": [
        "ನಮಸ್ಕಾರ, ನನ್ನ ಖಾತೆಯಿಂದ ಅನಧಿಕೃತ ವಹಿವಾಟು ಆಗಿದೆ.",
        "ದಯವಿಟ್ಟು ಒಟಿಪಿ ಕಳುಹಿಸಿ, ಬೇಗ ಮಾಡಿ.",
        "ನೀವು ಈಗಲೇ ಕ್ರಮ ತೆಗೆದುಕೊಳ್ಳದಿದ್ದರೆ ಖಾತೆ ಅಮಾನತ್ತು ಆಗುತ್ತದೆ.",
        "ನನ್ನ ಮೊಬೈಲ್ ನಂಬರ್ ನವೀಕರಿಸಿ, ಸಹಾಯ ಮಾಡಿ.",
        "ನಾನು ಬ್ಯಾಂಕ್ ಅಧಿಕಾರಿ, ನಿಮ್ಮ ಮಾಹಿತಿ ತಿದ್ದುಪಡಿ ಬೇಕು.",
    ],
    "tamil": [
        "வணக்கம், என் கணக்கில் அங்கீகாரமற்ற பரிவர்த்தனை நடந்தது.",
        "தயவுசெய்து ஓடிபியை உடனே அனுப்புங்கள்.",
        "நீங்கள் உடனே நடவடிக்கை எடுக்கவில்லை என்றால் கணக்கு முடக்கப்படும்.",
        "என் மொபைல் எண்ணை புதுப்பிக்கவும், உதவுங்கள்.",
        "நான் வங்கி அதிகாரி, உங்கள் விவரங்களை சரிபார்க்க வேண்டும்.",
    ],
    "telugu": [
        "నమస్కారం, నా ఖాతాలో అనధికార లావాదేవీ జరిగింది.",
        "దయచేసి ఒటిపి వెంటనే పంపండి.",
        "మీరు వెంటనే చర్య తీసుకోకపోతే ఖాతా ఫ్రీజ్ అవుతుంది.",
        "నా మొబైల్ నంబర్ అప్డేట్ చేయండి.",
        "నేను బ్యాంక్ అధికారిని, మీ వివరాలు ధృవీకరించాలి.",
    ],
    "marathi": [
        "नमस्कार, माझ्या खात्यात अनधिकृत व्यवहार झाला.",
        "कृपया ओटीपी लगेच पाठवा.",
        "आता कारवाई नाही केलात तर खाते गोठवले जाईल.",
        "माझा मोबाईल क्रमांक अपडेट करा.",
        "मी बँक अधिकारी बोलतोय, तुमची माहिती तपासावी लागेल.",
    ],
    "malayalam": [
        "നമസ്കാരം, എൻ്റെ അക്കൗണ്ടിൽ അനധികൃത ഇടപാട് നടന്നു.",
        "ദയവായി ഒടിപി ഉടൻ അയയ്ക്കുക.",
        "ഇപ്പോൾ നടപടി എടുത്തില്ലെങ്കിൽ അക്കൗണ്ട് മരവിപ്പിക്കും.",
        "എൻ്റെ മൊബൈൽ നമ്പർ അപ്ഡേറ്റ് ചെയ്യുക.",
        "ഞാൻ ബാങ്ക് ഉദ്യോഗസ്ഥനാണ്, വിശദാംശങ്ങൾ സ്ഥിരീകരിക്കണം.",
    ],
    "bengali": [
        "নমস্কার, আমার অ্যাকাউন্টে অননুমোদিত লেনদেন হয়েছে।",
        "অনুগ্রহ করে ওটিপি সাথে সাথে পাঠান।",
        "এখনই পদক্ষেপ না নিলে অ্যাকাউন্ট জব্দ হবে।",
        "আমার মোবাইল নম্বর আপডেট করুন।",
        "আমি ব্যাংক অফিসার বলছি, আপনার তথ্য যাচাই করতে হবে।",
    ],
    "gujarati": [
        "નમસ્તે, મારા ખાતામાં અનધિકૃત વ્યવહાર થયો છે.",
        "કૃપા કરીને ઓટીપી તરત મોકલો.",
        "હવે પગલું નહીં લેશો તો ખાતું જપ્ત થશે.",
        "મારો મોબાઈલ નંબર અપડેટ કરો.",
        "હું બેંક અધિકારી બોલું છું, તમારી વિગતો ચકાસવી પડશે.",
    ],
}

# ── Coqui XTTS-v2 ───────────────────────────────────────────────────────────
# Open voice-cloning model (Coqui CPML-1.0, free for research/non-commercial).
# Languages (XTTS-v2 multi-dataset): en, es, fr, de, it, pt, pl, tr, ru,
# nl, cs, ar, zh-cn, ja, ko, hu, hi.
XTTS_LANGUAGES = {"en", "hi"}
# XTTS cannot clone Hindi/Kannada speech for every target text perfectly, so
# we use it for en+hi (the attack languages that matter most for SIH), and
# RVC/FreeVC/edge-tts fill the rest.

XTTS_TEXT_BANK = {
    "hindi": [
        "मैं अभी मुश्किल में हूँ, मेरी मदद कर दो, बहुत जरूरी है।",
        "मेरा बैंक खाता ब्लॉक हो गया है, कृपया तुरंत बताइए क्या करना है।",
        "मैं क्रेडिट कार्ड की जानकारी लेने के लिए कॉल कर रहा हूँ।",
        "आपका ओटीपी मिला था, मुझे वह नंबर बताइए।",
        "यह बहुत गंभीर मामला है, आपको तुरंत कार्रवाई करनी होगी।",
    ],
    "english": [
        "I am in trouble right now, please help me, it is urgent.",
        "My bank account has been blocked, tell me what to do immediately.",
        "I am calling to verify your credit card information.",
        "I received an OTP, please share that number with me.",
        "This is a serious matter and you must act immediately.",
    ],
}


# ── FLEURS / Common Voice helpers ────────────────────────────────────────────
LOCALE_MAP = {
    "hindi": "hi_in", "english": "en_us", "kannada": "kn_in", "tamil": "ta_in",
    "telugu": "te_in", "marathi": "mr_in", "malayalam": "ml_in",
    "bengali": "bn_in", "gujarati": "gu_in",
}

# gTTS uses 2-letter ISO codes (same set as edge-tts voices above).
GTTS_LANG = {
    "hindi": "hi", "english": "en", "kannada": "kn", "tamil": "ta",
    "telugu": "te", "marathi": "mr", "malayalam": "ml",
    "bengali": "bn", "gujarati": "gu",
}


def save_audio(arr, sr, out_path, target_sr=16000):
    """Resample to target_sr, mono, peak-normalise, write WAV16."""
    import librosa
    import soundfile as sf

    if arr.ndim > 1:
        arr = arr.mean(axis=1)
    arr = librosa.resample(np.asarray(arr, dtype=np.float32), orig_sr=sr, target_sr=target_sr)
    peak = float(np.max(np.abs(arr)))
    if peak > 1e-6:
        arr = arr / peak
    sf.write(out_path, arr, target_sr)
    return out_path


def fetch_fleurs(out_dir, per_language, languages, seed=7):
    """Real Indian-language human speech from google/fleurs (CC-BY-4.0)."""
    import soundfile as sf
    from datasets import load_dataset

    rows, total = [], 0
    for lang in languages:
        locale = LOCALE_MAP.get(lang, lang)
        try:
            ds = load_dataset("google/fleurs", locale, split="train")
            count = 0
            for sample in ds:
                if count >= per_language:
                    break
                arr, sr, _ = _load_audio(sample)
                if arr is None or len(arr) < 4800:  # <0.3s skip
                    continue
                out_path = os.path.join(out_dir, f"bonafide_fleurs_{lang}_{count:04d}.wav")
                save_audio(arr, sr if sr else 16000, out_path)
                rows.append({"audio_path": out_path, "label": "bonafide", "language": lang})
                count += 1
                total += 1
            logger.info(f"  FLEURS [{lang}] → {count} clips")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"  FLEURS [{lang}] failed: {exc}")
    logger.info(f"FLEURS bonafide total: {total}")
    return pd.DataFrame(rows)


def fetch_commonvoice(out_dir, per_language, languages, seed=7):
    """Extra real Indian-language speech from Mozilla Common Voice 17.0 (CC-BY-4.0; CC0 <= v13)."""
    from datasets import load_dataset

    rows, total = [], 0
    for lang in languages:
        cfg = LOCALE_MAP.get(lang) or FLEURS_REV.get(lang)
        try:
            ds = load_dataset("mozilla-foundation/common_voice_17_0", cfg, split="train")
            count = 0
            for sample in ds:
                if count >= per_language:
                    break
                if "audio" not in sample or sample["audio"] is None:
                    continue
                arr, sr, _ = _load_audio(sample)
                if arr is None or len(arr) < 4800:
                    continue
                out_path = os.path.join(out_dir, f"bonafide_cv_{lang}_{count:04d}.wav")
                save_audio(arr, sr if sr else 16000, out_path)
                rows.append({"audio_path": out_path, "label": "bonafide", "language": lang})
                count += 1
                total += 1
            logger.info(f"  CommonVoice [{lang}] → {count} clips")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"  CommonVoice [{lang}] failed: {exc}")
    logger.info(f"CommonVoice bonafide total: {total}")
    return pd.DataFrame(rows)


# ── REAL VOICE IMPERSONATION GENERATORS ─────────────────────────────────────

def generate_xtts_spoofs(bonafide_df, out_dir, per_speaker=3, seed=7):
    """
    REAL impersonation: clone the actual bonafide speaker (a FLEURS/CommonVoice
    human) with Coqui XTTS-v2 so the spoof speaks THEIR voice but attacker text.

    bonafide_df: rows have audio_path + language (hindi/english supported).
    per_speaker: spoofs generated per bonafide clip.

    Uses the maintained `coqui-tts` fork (same `from TTS.api import TTS` API,
    supports Python 3.10-3.13). Colab requires this fork — the legacy `TTS`
    package has no wheels for Python >= 3.12.
    """
    os.environ.setdefault("COQUI_TOS_AGREED", "1")
    try:
        from TTS.api import TTS
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "XTTS not installed — run `!pip install coqui-tts` and retry. "
            "Original error: %s", exc)
        return pd.DataFrame()

    sub = bonafide_df[bonafide_df["language"].isin(["hindi", "english"])]
    if sub.empty:
        logger.warning("No hindi/english bonafides → no XTTS spoofs.")
        return pd.DataFrame()

    logger.info("Loading XTTS-v2 (first call downloads ~1.8 GB)...")
    try:
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    except Exception as exc:  # noqa: BLE001
        logger.warning("XTTS model load failed: %s", exc)
        return pd.DataFrame()
    try:
        import torch
        if torch.cuda.is_available():
            tts = tts.to("cuda")
            logger.info("XTTS on GPU")
    except Exception:  # noqa: BLE001
        pass

    rng = random.Random(seed)
    rows = []
    made = 0
    for _, rec in sub.iterrows():
        ref = rec["audio_path"]
        lang = rec["language"]
        code = "hi" if lang == "hindi" else "en"
        texts = rng.sample(XTTS_TEXT_BANK[lang], min(per_speaker, len(XTTS_TEXT_BANK[lang])))
        for i, text in enumerate(texts):
            stem = os.path.splitext(os.path.basename(ref))[0]
            out_path = os.path.join(out_dir, f"spoof_xtts_clone_{stem}_{i}.wav")
            try:
                tts.tts_to_file(text=text, speaker_wav=ref, language=code, file_path=out_path)
                rows.append({"audio_path": out_path, "label": "spoof",
                             "language": lang,
                             "attack": "xtts_cloning", "clone_of": ref})
                made += 1
                if made % 20 == 0:
                    logger.info(f"  XTTS clones: {made}")
            except Exception as exc:  # noqa: BLE001
                logger.debug("XTTS clone failed %s: %s", ref, exc)
    logger.info(f"XTTS-v2 real-clone spoofs generated: {made}")
    return pd.DataFrame(rows)


def generate_rvc_spoofs(bonafide_df, out_dir, rvc_model_dir, target_voice_id,
                        seed=7, per_speaker=2):
    """
    REAL impersonation via RVC (MIT): converts real clips into a cloned target
    voice (any Indian language). Requires an RVC .pth model + index in
    rvc_model_dir and its speaker id. Best effokort; if rvc_cli not installed
    it degrades gracefully.
    """
    try:
        from rvc_python.infer import RVCInference
    except Exception as exc:  # noqa: BLE001
        logger.warning("rvc_python not installed; skipping RVC spoofs: %s", exc)
        return pd.DataFrame()

    rvc = RVCInference(device="cuda:0")
    rvc.load_model(os.path.join(rvc_model_dir, "rvc-model.pth"), r"rvc-model", target_voice_id)
    rvc.set_params(f0method="rmvpe", f0up_key=0, index_path=os.path.join(rvc_model_dir, "added_IVF.index"))

    making = 0
    rng = random.Random(seed)
    rows = []
    for _, rec in bonafide_df.iterrows():
        for i in range(per_speaker):
            out_path = os.path.join(out_dir, f"spoof_rvc_{os.path.basename(rec['audio_path'])}.wav")
            try:
                rvc.infer_file(rec["audio_path"], out_path, transpose=0)
                rows.append({"audio_path": out_path, "label": "spoof",
                             "language": rec["language"],
                             "attack": "rvc_conversion", "clone_of": rec["audio_path"]})
                making += 1
            except Exception as exc:  # noqa: BLE001
                logger.debug("RVC fail: %s", exc)
    logger.info(f"RVC clone spoofs generated: {making}")
    return pd.DataFrame(rows)


def generate_freevc_spoofs(bonafide_df, out_dir, freevc_model_path, seed=7):
    """
    REAL impersonation via FreeVC (MIT): zero-shot voice conversion.
    freevc_model_path → FreeVC pretrained checkpoint (e.g. pretrained_v2).
    """
    try:
        from freevc.infer import main as freevc_infer
    except ImportError:
        try:
            import sys
            sys.path.insert(0, "FreeVC")  # notebook clones repo to ./FreeVC
            from freevc.infer import main as freevc_infer
        except Exception as exc:  # noqa: BLE001
            logger.warning("FreeVC not available; skipping: %s", exc)
            return pd.DataFrame()

    rows = []
    made = 0
    import tempfile
    for _, rec in bonafide_df.iterrows():
        out_path = os.path.join(out_dir, f"spoof_freevc_{os.path.basename(rec['audio_path'])}.wav")
        try:
            freevc_infer(rec["audio_path"], out_path, freevc_model_path)
            rows.append({"audio_path": out_path, "label": "spoof",
                         "language": rec["language"],
                         "attack": "freevc_conversion", "clone_of": rec["audio_path"]})
            made += 1
        except Exception as exc:  # noqa: BLE001
            logger.debug("FreeVC fail: %s", exc)
    logger.info(f"FreeVC clone spoofs generated: {made}")
    return pd.DataFrame(rows)


async def _edge_synthesize(text, voice, out_path):
    import edge_tts
    import io as _io

    raw = b""
    communicator = edge_tts.Communicate(text, voice, rate="+0%", pitch="-0Hz")
    async for chunk in communicator.stream():
        if chunk["type"] == "audio":
            raw += chunk["data"]
    if not raw:
        return False
    try:
        import soundfile as sf_mod
        data, sr = sf_mod.read(_io.BytesIO(raw), dtype="float32")
        save_audio(data, sr, out_path)      # → 16 kHz mono WAV (canonical)
        return os.path.getsize(out_path) > 1000
    except Exception:  # noqa: BLE001
        with open(out_path, "wb") as f:
            f.write(raw)                    # fallback: keep raw mp3
        return os.path.getsize(out_path) > 1000


def _run_async(coro_factory):
    """Run an async coroutine from inside a Jupyter/Colab cell (which already
    has a running event loop).  Uses a brand-new event loop on a worker thread,
    so `asyncio.run()` is never called on the running loop."""
    import asyncio
    import threading

    results = {}

    def _target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results["ok"] = loop.run_until_complete(coro_factory())
        except Exception as exc:  # noqa: BLE001
            results["err"] = exc
        finally:
            loop.close()

    t = threading.Thread(target=_target)
    t.start()
    t.join()
    if "err" in results:
        raise results["err"]
    return results.get("ok")


def generate_gtsspoofs(out_dir, per_language, languages=None, seed=7):
    """
    AUXILIARY pure-TTS attack family via gTTS (Google Translate TTS).
    Chosen as the *reliable* minority class that ALWAYS works from Google
    Colab — synchronous, no API key, covers every language in LANGS.
    (edge-tts — Microsoft — throttles Colab datacenter IPs, so it is NOT
    the primary aux generator.)
    """
    from gtts import gTTS
    import io as _io

    languages = languages or list(EDGE_VOICES.keys())
    rng = random.Random(seed)
    rows, made = [], 0
    for lang in languages:
        prompts = SPOOF_PROMPTS[lang]
        texts = rng.sample(prompts, min(per_language, len(prompts)))
        for t in texts:
            out_path = os.path.join(out_dir, f"spoof_gtsspoof_{lang}_{made:04d}.wav")
            try:
                buf = _io.BytesIO()
                gTTS(text=t, lang=GTTS_LANG[lang], tld="com").write_to_fp(buf)
                buf.seek(0)
                import soundfile as sf_mod
                data, sr = sf_mod.read(buf, dtype="float32")
                if data is None or len(data) < 4800:
                    continue
                save_audio(data, sr, out_path)
                rows.append({"audio_path": out_path, "label": "spoof",
                             "language": lang, "attack": "gtts",
                             "clone_of": ""})
                made += 1
            except Exception as exc:  # noqa: BLE001
                logger.debug("gTTS fail %s: %s", lang, exc)
    logger.info(f"gTTS (pure TTS, aux class) spoofs: {made}")
    return pd.DataFrame(rows)


def generate_edge_spoofs(out_dir, per_language, languages=None, seed=7):
    """
    OPTIONAL: Microsoft edge-tts voices as an extra pure-TTS flavour. May be
    rate-limited from Colab datacenter IPs (NoAudioReceived); failures are
    skipped silently, never fatal. gTTS is the primary aux generator.
    """
    languages = languages or list(EDGE_VOICES.keys())
    rng = random.Random(seed)
    rows, made = [], 0
    for lang in languages:
        voices = EDGE_VOICES[lang]
        prompts = SPOOF_PROMPTS[lang]
        per_voice = max(1, per_language // len(voices))
        for v in voices:
            texts = rng.sample(prompts, min(per_voice, len(prompts)))
            for t in texts:
                out_path = os.path.join(out_dir, f"spoof_edgetts_{lang}_{made:04d}.wav")
                try:
                    ok = _run_async(lambda: _edge_synthesize(t, v, out_path))
                    if not ok:
                        continue
                    rows.append({"audio_path": out_path, "label": "spoof",
                                 "language": lang, "attack": "edge_tts",
                                 "clone_of": ""})
                    made += 1
                except Exception as exc:  # noqa: BLE001
                    logger.debug("edge-tts fail %s/%s: %s", lang, v, exc)
    logger.info(f"edge-tts (pure TTS, aux class) spoofs: {made}")
    return pd.DataFrame(rows)


# ── assemble + split ─────────────────────────────────────────────────────────

def build_and_split(bona_df, spoof_dfs, val_frac=0.15, seed=42):
    rng = random.Random(seed)
    spoof_df = pd.concat(spoof_dfs, ignore_index=True) if spoof_dfs else pd.DataFrame()
    df = pd.concat([bona_df, spoof_df], ignore_index=True)
    df = df.sample(frac=1.0, random_state=seed)

    # per-language class balance: cap spoofs to bonafide per language
    keep = []
    for lang, grp in df.groupby("language"):
        nb = int((grp["label"] == "bonafide").sum())
        ns = int((grp["label"] == "spoof").sum())
        if nb == 0 or ns == 0:
            logger.warning(f"[{lang}] only one class ({nb} bona / {ns} spoof) — skipping")
            continue
        take = min(nb, ns)
        keep.append(
            pd.concat([
                grp[grp["label"] == "bonafide"].sample(take, random_state=seed),
                grp[grp["label"] == "spoof"].sample(take, random_state=seed),
            ]))
    if not keep:
        raise ValueError("No language has both classes — check generators.")
    bal = pd.concat(keep, ignore_index=True).sample(frac=1.0, random_state=seed)

    train, val = [], []
    for lang in bal["language"].unique():
        sub = bal[bal["language"] == lang].reset_index(drop=True)
        n_val = int(len(sub) * val_frac)
        idx = rng.sample(range(len(sub)), n_val)
        val.append(sub.iloc[idx])
        train.append(sub.drop(idx))
    train = pd.concat(train).sample(frac=1.0, random_state=seed)
    val = pd.concat(val).sample(frac=1.0, random_state=seed)
    train["split"], val["split"] = "train", "val"

    os.makedirs(DATA_DIR, exist_ok=True)
    t_path, v_path = os.path.join(DATA_DIR, "train.csv"), os.path.join(DATA_DIR, "val.csv")
    train.reset_index(drop=True).to_csv(t_path, index=False)
    val.reset_index(drop=True).to_csv(v_path, index=False)
    logger.info(f"Wrote {t_path} ({len(train)} rows) and {v_path} ({len(val)} rows)")
    return train, val


def main():
    ap = argparse.ArgumentParser(description="VoiceShield SIH cloud dataset builder")
    ap.add_argument("--bonafide-per-lang", type=int, default=250)
    ap.add_argument("--languages", nargs="*",
                    default=["hindi", "english", "kannada", "tamil",
                             "telugu", "marathi", "malayalam"])
    ap.add_argument("--use-commonvoice", action="store_true")
    ap.add_argument("--xtts", action="store_true", help="generate REAL XTTS voice-clone spoofs (en,hi)")
    ap.add_argument("--rvc-model-dir", type=str, default="", help="RVC model+index dir for rvc conversion")
    ap.add_argument("--freevc-wav2vec", type=str, default="", help="FreeVC wav2vec .pt path")
    ap.add_argument("--edge", action="store_true", help="add auxiliary edge-tts (pure TTS) spoofs")
    ap.add_argument("--edge-per-lang", type=int, default=25)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--opendir", type=str, default="")
    ap.add_argument("--hf-repo", type=str, default="", help="Optional: push CSVs to HF dataset repo")
    args = ap.parse_args()
    global DATA_DIR
    if args.opendir:
        DATA_DIR = args.opendir
    audio_dir = os.path.join(DATA_DIR, "audio")
    os.makedirs(audio_dir, exist_ok=True)

    # 1) real voices
    bona = fetch_fleurs(audio_dir, args.bonafide_per_lang, args.languages)
    if args.use_commonvoice:
        bona = pd.concat([bona, fetch_commonvoice(audio_dir, args.bonafide_per_lang, args.languages)])
    logger.info(f"Bonafide pool: {len(bona)}")

    # 2) REAL impersonation spoofs
    spoof_dfs = []
    if args.xtts:
        spoof_dfs.append(generate_xtts_spoofs(bona, audio_dir))
    if args.rvc_model_dir:
        spoof_dfs.append(generate_rvc_spoofs(bona, audio_dir, args.rvc_model_dir, 0))
    if args.freevc_wav2vec:
        spoof_dfs.append(generate_freevc_spoofs(bona, audio_dir, args.freevc_wav2vec))
    if args.edge:
        spoof_dfs.append(generate_edge_spoofs(audio_dir, args.edge_per_lang, args.languages))
    if not spoof_dfs:
        logger.error("No spoof generator selected (--xtts / --rvc-model-dir / --freevc-wav2vec / --edge).")
        return

    train, val = build_and_split(bona, spoof_dfs, args.val_frac)

    if args.hf_repo:
        from datasets import Dataset, DatasetDict
        ds = DatasetDict({"train": Dataset.from_pandas(train),
                          "val": Dataset.from_pandas(val)})
        ds.push_to_hub(args.hf_repo, private=True)
        logger.info(f"Pushed to HF Hub: {args.hf_repo}")


if __name__ == "__main__":
    main()