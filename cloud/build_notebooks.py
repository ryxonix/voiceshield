"""Generate .ipynb notebooks for Google Colab + Kaggle (SIH cloud-training kit).

Run:  python build_notebooks.py
Emits (into this cloud/ dir):
    colab_01_build_dataset.ipynb      (data + REAL XTTS/RVC/FreeVC cloning)
    colab_02_train_wav2vec2.ipynb     (train wav2vec2-base audio classifier)
    colab_03_train_xlsr.ipynb         (train XLSR-300m)
    kaggle_train_wav2vec2.py          (Kaggle script version)
"""
import json
import re
import textwrap
from pathlib import Path

OUT = Path(__file__).parent


# ─────────────────────────────────────────────────────────────────────────────
NOTEBOOK_01 = r'''
# 01 · VoiceShield SIH — Build a large SIH-compliant dataset (REAL voice cloning)

> What this notebook does:
>  1. Downloads real Indian-language human speech — **FLEURS (CC-BY-4.0)**,
>     optionally **Mozilla Common Voice (CC-BY-4.0; CC0 ≤ v13)** for
>     hi/en/kn/ta/te/ml/etc.
>  2. Generates **REAL A.I. voice impersonation**: the *same human speakers*
>     are voice-cloned with **Coqui XTTS-v2** (open, CPML-1.0) that repeat
>     attacker-style phrases. Optional **RVC** / **FreeVC** conversion.
>  3. Adds plain-TTS (edge-tts) as a *minority* auxiliary attack class.
>  4. Writes balanced train/val CSVs + optionally pushes to the HuggingFace Hub.
>
> Why: SIH problem statement = real-time A.I. voice + voice-impersonation
> detection. A model trained only on plain TTS misses the real attack:
> a cloned voice of the actual speaker. Cloud cloning = real impersonation.

## 1 · GPU + setup

```python
!nvidia-smi --query-gpu=name,memory.total --format=csv
```

```python
!pip install -q datasets[audio] soundfile librosa gtts torchaudio
# Coqui XTTS-v2 voice cloning (REAL impersonation). The original "TTS" package
# is unmaintained and has NO Python>=3.12 wheels; use the maintained fork
# "coqui-tts" (same API: `from TTS.api import TTS`).
!pip install -q coqui-tts
# Optional extras (uncomment to enable):
# !pip install -q edge-tts nest_asyncio     # extra aux TTS flavour (may be rate-limited)
# !pip install -q rvc-python                # optional RVC conversion
```

```python
import os, numpy as np, pandas as pd

# Drive is OPTIONAL. If mounting fails (auth popup not accepted), we fall back
# to Colab local disk and you can still push the dataset to HF Hub.
DRIVE_OK = False
try:
    from google.colab import drive
    drive.mount("/content/drive")
    DRIVE_OK = os.path.isdir("/content/drive/MyDrive")
except Exception as exc:  # noqa: BLE001
    print("Drive mount failed — continuing on local disk:", exc)

ROOT = "/content/drive/MyDrive/voiceshield_cloud" if DRIVE_OK else "/content/vs_data"
AUDIO_DIR = os.path.join(ROOT, "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)
print("DRIVE_OK =", DRIVE_OK)
print("ROOT     =", ROOT)
```

```python
# Optional: HF token (Write rights) to push the dataset to HuggingFace Hub.
# In Colab: pick 🔑 "Secrets" in the left sidebar → Add new secret → name "HF_TOKEN".
HF_TOKEN = ""
try:
    from google.colab import userdata
    HF_TOKEN = userdata.get("HF_TOKEN", "")
except Exception as exc:  # noqa: BLE001
    print("No Colab secret HF_TOKEN (optional):", exc)
os.environ["HF_TOKEN"] = HF_TOKEN
os.environ.setdefault("COQUI_TOS_AGREED", "1")  # silent auto-accept XTTS licence
print("HF_TOKEN loaded:", bool(HF_TOKEN))
```

## 2 · Canonical dataset builder

```python
# Embedded copy of backend/training/cloud_dataset.py — no GitHub needed.
import base64
CLOUD_DATASET_B64 = "{{CLOUD_DATASET_B64}}"
open("/content/cloud_dataset.py", "wb").write(base64.b64decode(CLOUD_DATASET_B64))
```

```python
import importlib.util
spec = importlib.util.spec_from_file_location("cloud_dataset", "/content/cloud_dataset.py")
cd   = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cd)
print("cloud_dataset loaded:", hasattr(cd, "fetch_fleurs"))
```

## 3 · REAL human speech (bonafide)

```python
LANGS = ["hindi", "english", "kannada", "tamil", "telugu", "marathi", "malayalam"]

# CC-BY-4.0 real Indian-language speech
bona = cd.fetch_fleurs(AUDIO_DIR, per_language=250, languages=LANGS)
print("FLEURS bonafide:", len(bona))
# Optional: CC0 extra real voices
# bona2 = cd.fetch_commonvoice(AUDIO_DIR, per_language=150, languages=LANGS)
# bona  = pd.concat([bona, bona2], ignore_index=True)
print("bonafide per lang:\n", bona.language.value_counts())
```

## 4 · REAL A.I. voice impersonation (clone the actual speakers)

```python
# XTTS-v2 clones EVERY bona-fide hindi/english speaker → speaks attacker text
# in their cloned voice. This is the "voice impersonation" the SIH problem asks about.
spoof_xtts = cd.generate_xtts_spoofs(bona, AUDIO_DIR, per_speaker=3)
print("XTTS voice-clone spoofs:", len(spoof_xtts))
```

```python
# Optional: RVC conversion clones (MIT) — put rvc-model.pth + index in Drive
# spoof_rvc = cd.generate_rvc_spoofs(bona, AUDIO_DIR,
#     "/content/drive/MyDrive/rvc_model", target_voice_id=0, per_speaker=2)

# Optional: FreeVC zero-shot conversion (MIT)
# spoof_fvc = cd.generate_freevc_spoofs(bona, AUDIO_DIR,
#                                       "/content/drive/MyDrive/freevc/pretrained_v2")
```

## 5 · Auxiliary pure-TTS attack class (minority)

```python
# gTTS (Google Translate TTS) — synchronous, reliable from Colab, covers every
# Indian language. Edge-tts (Microsoft) is optional and may fail from datacenter IPs.
spoof_gtts = cd.generate_gtsspoofs(AUDIO_DIR, per_language=30, languages=LANGS)
print("gTTS aux spoofs:", len(spoof_gtts))

# Uncomment to add edge-tts flavour (may produce 0 on Colab if Microsoft throttles)
# spoof_edge = cd.generate_edge_spoofs(AUDIO_DIR, per_language=30, languages=LANGS)
# spoof_tts  = pd.concat([spoof_gtts, spoof_edge], ignore_index=True) if len(spoof_edge) else spoof_gtts
spoof_tts = spoof_gtts
```

## 6 · Balanced split + archive

```python
# `build_and_split` writes train.csv/val.csv to the module DATA_DIR; point it at ROOT
cd.DATA_DIR = ROOT
train, val = cd.build_and_split(bona, [spoof_xtts, spoof_tts], val_frac=0.15)
print("train:", len(train), " val:", len(val))
print(train.label.value_counts())
print(val.label.value_counts())
```

```python
# Persist to ROOT (Drive if mounted; local disk otherwise). Notebooks 02/03
# reuse these CSVs if DRIVE_OK, or you push to HF Hub in the next cell.
os.makedirs(ROOT, exist_ok=True)
train.to_csv(os.path.join(ROOT, "train.csv"), index=False)
val.to_csv(os.path.join(ROOT, "val.csv"), index=False)
print("Saved CSVs →", ROOT)
print("(audio dir →", AUDIO_DIR, ")")
```

```python
# Optional: push CSV to HF Hub so Kaggle/Colab can reload it by URL.
# Requires the HF_TOKEN secret (Write rights). Private repo so your data stays yours.
if HF_TOKEN and HF_TOKEN.startswith("hf_"):
    from datasets import Dataset, DatasetDict, Audio, ClassLabel, Features, Value

    def to_hf(df):
        feats = Features({"audio": Audio(sampling_rate=16000),
                          "label": ClassLabel(names=["bonafide","spoof"]),
                          "language": Value("string")})
        d = df.copy()
        d["label"] = (d.label == "spoof").astype("int8")
        d = d.rename(columns={"audio_path": "audio"})
        return Dataset.from_pandas(d[["audio","label","language"]], features=feats)

    ds = DatasetDict({"train": to_hf(train), "val": to_hf(val)})
    ds.push_to_hub("VAIVE/voiceshield-sih", private=True)
    print("Pushed dataset → VAIVE/voiceshield-sih  (use in notebooks 02/03 via load_dataset)")
else:
    print("Skipped HF push (no valid HF_TOKEN). If DRIVE_OK=False, keep this Colab session "
          "alive and run notebook 02 in the SAME session, or set the HF_TOKEN secret and rerun.")
```

```python
print("NEXT → open colab_02_train_wav2vec2.ipynb")
```
'''


NOTEBOOK_02 = r'''
# 02 · VoiceShield SIH — Train wav2vec2-base audio classifier (free Colab GPU)

Trains on the dataset from **colab_01** (real FLEURS/CV voices vs REAL XTTS /
RVC / FreeVC cloned voices + aux TTS). Uses the HuggingFace `Trainer`; fits in
a free T4.

## 1 · Setup

```python
!pip install -q datasets[audio] soundfile librosa transformers evaluate accelerate
```

```python
import os, numpy as np, pandas as pd

# Reuse the same optional-Drive + HF-token setup from notebook 01.
DRIVE_OK = False
try:
    from google.colab import drive
    drive.mount("/content/drive")
    DRIVE_OK = os.path.isdir("/content/drive/MyDrive")
except Exception as exc:  # noqa: BLE001
    print("Drive mount failed — continuing:", exc)

HF_TOKEN = ""
try:
    from google.colab import userdata
    HF_TOKEN = userdata.get("HF_TOKEN", "")
except Exception:  # noqa: BLE001
    pass
os.environ["HF_TOKEN"] = HF_TOKEN
```

## 2 · Load dataset (Drive OR HF Hub — whichever notebook 01 produced)

```python
ROOT = "/content/drive/MyDrive/voiceshield_cloud"
if DRIVE_OK and os.path.isfile(f"{ROOT}/train.csv"):
    train = pd.read_csv(f"{ROOT}/train.csv")
    val   = pd.read_csv(f"{ROOT}/val.csv")
    print("Loaded from Drive:", ROOT)
elif HF_TOKEN.startswith("hf_"):
    from datasets import load_dataset
    ds = load_dataset("VAIVE/voiceshield-sih")
    train = ds["train"].to_pandas()
    val   = ds["val"].to_pandas()
    print("Loaded from HF Hub: VAIVE/voiceshield-sih")
else:
    raise SystemExit("No dataset found. Re-run notebook 01 with DRIVE_OK=True (accept the "
                     "Drive popup) or add the HF_TOKEN secret and push the dataset.")
print("train:", len(train), " val:", len(val))
```

## 3 · HuggingFace Dataset + preprocessing (16 kHz)

```python
from datasets import Dataset, Audio, ClassLabel, Features, Value

feats = Features({
    "audio": Audio(sampling_rate=16000),
    "label": ClassLabel(names=["bonafide", "spoof"]),
    "language": Value("string"),
})
def to_ds(df):
    df = df.copy()
    df["label"] = (df.label == "spoof").astype("int8")
    df = df.rename(columns={"audio_path": "audio"})
    return Dataset.from_pandas(df[["audio", "label", "language"]], features=feats)

train_ds, val_ds = to_ds(train), to_ds(val)
```

```python
from transformers import Wav2Vec2Processor, Wav2Vec2ForAudioClassification
import evaluate, numpy as np

ckpt = "facebook/wav2vec2-base-960h"
processor = Wav2Vec2Processor.from_pretrained(ckpt, do_normalize=True)
model = Wav2Vec2ForAudioClassification.from_pretrained(
    ckpt, num_labels=2,
    attention_dropout=0.0, hidden_dropout=0.1,
    label2id={"bonafide":0,"spoof":1}, id2label={0:"bonafide",1:"spoof"},
)
MAX = 16000 * 8   # 8 s window (SIH real-time budget ~3 s)

def load_audio(x):
    """Works with datasets 2.x (dict) and 3.x+torchcodec (AudioDecoder)."""
    a = x["audio"]
    if isinstance(a, dict):
        return np.asarray(a["array"], dtype=np.float32), a.get("sampling_rate", 16000)
    s = a.get_all_samples()
    arr = np.asarray(s.data.cpu() if hasattr(s.data, "cpu") else s.data,
                     dtype=np.float32).squeeze()
    if arr.ndim > 1:
        arr = arr.mean(axis=0)
    return arr, s.sample_rate

def pre(x):
    arr, sr = load_audio(x)
    arr = np.pad(arr, (0, max(0, MAX - len(arr))))[:MAX]
    return processor(arr, sampling_rate=sr).input_values[0]
```

```python
train_ds = train_ds.map(lambda x: {"input_values": pre(x)}, remove_columns=["audio"])
val_ds   = val_ds.map(lambda x: {"input_values": pre(x)}, remove_columns=["audio"])
print("preprocessed:", len(train_ds), len(val_ds))
```

## 4 · Train

```python
from transformers import TrainingArguments, Trainer

args = TrainingArguments(
    output_dir="/content/vs_out",
    per_device_train_batch_size=4,
    per_device_eval_batch_size=4,
    gradient_accumulation_steps=2,
    learning_rate=3e-5,
    warmup_ratio=0.1,
    num_train_epochs=3,
    evaluation_strategy="epoch",
    save_strategy="epoch",
    logging_steps=50,
    report_to=[],
    fp16=True,
    metric_for_best_model="eval_accuracy",
    load_best_model_at_end=True,
)
acc = evaluate.load("accuracy")
trainer = Trainer(model=model, args=args,
                  train_dataset=train_ds, eval_dataset=val_ds,
                  compute_metrics=lambda p: acc.compute(
                      predictions=p.predictions.argmax(-1), references=p.label_ids))
trainer.train()
```

## 5 · Save + push

```python
SAVE = ROOT if DRIVE_OK else "/content/vs_model_wav2vec2"
model.save_pretrained(SAVE)
processor.save_pretrained(SAVE)
print("saved →", SAVE)
```

```python
# Optional push for the backend/replay servers (HF_TOKEN must have Write rights)
if HF_TOKEN.startswith("hf_"):
    model.push_to_hub("VAIVE/voiceshield-wav2vec2")
    processor.push_to_hub("VAIVE/voiceshield-wav2vec2")
print("DONE")
```
'''


NOTEBOOK_03 = r'''
# 03 · VoiceShield SIH — Train XLSR-300m cross-lingual classifier (Colab GPU)

Same recipe as notebook 02 but with `facebook/wav2vec2-xls-r-300m` — better
Indic-language coverage at the cost of being bigger/slower. Excellent for the
final accuracy claim in the SIH demo.

## 1 · Setup + load (same as 02)

```python
!pip install -q datasets[audio] soundfile librosa transformers evaluate accelerate

import os, numpy as np, pandas as pd

DRIVE_OK = False
try:
    from google.colab import drive
    drive.mount("/content/drive")
    DRIVE_OK = os.path.isdir("/content/drive/MyDrive")
except Exception as exc:  # noqa: BLE001
    print("Drive mount failed — continuing:", exc)
HF_TOKEN = ""
try:
    from google.colab import userdata
    HF_TOKEN = userdata.get("HF_TOKEN", "")
except Exception:  # noqa: BLE001
    pass
os.environ["HF_TOKEN"] = HF_TOKEN
```

```python
ROOT = "/content/drive/MyDrive/voiceshield_cloud"
if DRIVE_OK and os.path.isfile(f"{ROOT}/train.csv"):
    train = pd.read_csv(f"{ROOT}/train.csv"); val = pd.read_csv(f"{ROOT}/val.csv")
    print("Loaded from Drive")
elif HF_TOKEN.startswith("hf_"):
    from datasets import load_dataset
    ds = load_dataset("VAIVE/voiceshield-sih")
    train = ds["train"].to_pandas(); val = ds["val"].to_pandas()
    print("Loaded from HF Hub")
else:
    raise SystemExit("No dataset found. Re-run notebook 01 (accept the Drive popup) or "
                     "set HF_TOKEN and push the dataset to the Hub.")
print("train:", len(train), " val:", len(val))
```

```python
from datasets import Dataset, Audio, ClassLabel, Features, Value
feats = Features({"audio": Audio(sampling_rate=16000),
                  "label": ClassLabel(names=["bonafide","spoof"]),
                  "language": Value("string")})
def to_ds(df):
    df = df.copy(); df["label"] = (df.label == "spoof").astype("int8")
    df = df.rename(columns={"audio_path": "audio"})
    return Dataset.from_pandas(df[["audio","label","language"]], features=feats)
train_ds, val_ds = to_ds(train), to_ds(val)
```

## 2 · Model + prep

```python
from transformers import (Wav2Vec2Processor, Wav2Vec2ForAudioClassification,
                          TrainingArguments, Trainer)
import evaluate, numpy as np
ckpt = "facebook/wav2vec2-xls-r-300m"
processor = Wav2Vec2Processor.from_pretrained(ckpt, do_normalize=True)
model = Wav2Vec2ForAudioClassification.from_pretrained(
    ckpt, num_labels=2, attention_dropout=0.1, hidden_dropout=0.1,
    label2id={"bonafide":0,"spoof":1}, id2label={0:"bonafide",1:"spoof"})
MAX = 16000*8
def load_audio(x):
    """Works with datasets 2.x (dict) and 3.x+torchcodec (AudioDecoder)."""
    a = x["audio"]
    if isinstance(a, dict):
        return np.asarray(a["array"], dtype=np.float32), a.get("sampling_rate", 16000)
    s = a.get_all_samples()
    arr = np.asarray(s.data.cpu() if hasattr(s.data, "cpu") else s.data,
                     dtype=np.float32).squeeze()
    if arr.ndim > 1:
        arr = arr.mean(axis=0)
    return arr, s.sample_rate

def pre(x):
    arr, sr = load_audio(x)
    arr = np.pad(arr, (0, max(0, MAX-len(arr))))[:MAX]
    return processor(arr, sampling_rate=sr).input_values[0]
train_ds = train_ds.map(lambda x: {"input_values": pre(x)}, remove_columns=["audio"])
val_ds   = val_ds.map(lambda x: {"input_values": pre(x)}, remove_columns=["audio"])
```

## 3 · Train (smaller batch; XLS-R is heavy)

```python
args = TrainingArguments(
    output_dir="/content/vs_out_xlsr",
    per_device_train_batch_size=2,
    per_device_eval_batch_size=2,
    gradient_accumulation_steps=8,
    learning_rate=2e-5,
    warmup_ratio=0.1,
    num_train_epochs=3,
    evaluation_strategy="epoch",
    save_strategy="epoch",
    logging_steps=50,
    report_to=[],
    fp16=True,
    metric_for_best_model="eval_accuracy",
    load_best_model_at_end=True,
)
acc = evaluate.load("accuracy")
trainer = Trainer(model=model, args=args,
                  train_dataset=train_ds, eval_dataset=val_ds,
                  compute_metrics=lambda p: acc.compute(
                      predictions=p.predictions.argmax(-1), references=p.label_ids))
trainer.train()
```

## 4 · Save + push

```python
SAVE = ROOT if DRIVE_OK else "/content/vs_model_xlsr"
model.save_pretrained(SAVE)
processor.save_pretrained(SAVE)
print("saved →", SAVE)

if HF_TOKEN.startswith("hf_"):
    model.push_to_hub("VAIVE/voiceshield-xlsr")
    processor.push_to_hub("VAIVE/voiceshield-xlsr")
print("DONE")
```
'''


KAGGLE_TRAIN = r'''
# VoiceShield SIH · Train wav2vec2-base (Kaggle GPU)
# Pre-req: upload colab_01's dataset as a Kaggle Dataset "voiceshield-sih"
# (or use kagglehub to pull VAIVE/voiceshield-sih from HF Hub).

import os, numpy as np, pandas as pd

# In Kaggle use the Data panel: add dataset "voiceshield-sih" → input path below
ROOT = "/kaggle/input/voiceshield-sih"
train = pd.read_csv(os.path.join(ROOT, "train.csv"))
val   = pd.read_csv(os.path.join(ROOT, "val.csv"))

from datasets import Dataset, Audio, ClassLabel, Features, Value
feats = Features({
    "audio": Audio(sampling_rate=16000),
    "label": ClassLabel(names=["bonafide", "spoof"]),
    "language": Value("string"),
})
def to_ds(df):
    df = df.copy(); df["label"] = (df.label == "spoof").astype("int8")
    df = df.rename(columns={"audio_path": "audio"})
    return Dataset.from_pandas(df[["audio", "label", "language"]], features=feats)
train_ds, val_ds = to_ds(train), to_ds(val)

from transformers import (Wav2Vec2Processor, Wav2Vec2ForAudioClassification,
                          TrainingArguments, Trainer)
import evaluate
ckpt = "facebook/wav2vec2-base-960h"
processor = Wav2Vec2Processor.from_pretrained(ckpt, do_normalize=True)
model = Wav2Vec2ForAudioClassification.from_pretrained(
    ckpt, num_labels=2, label2id={"bonafide": 0, "spoof": 1},
    id2label={0: "bonafide", 1: "spoof"})
MAX = 16000 * 8
def load_audio(x):
    """Works with datasets 2.x (dict) and 3.x+torchcodec (AudioDecoder)."""
    a = x["audio"]
    if isinstance(a, dict):
        return np.asarray(a["array"], dtype=np.float32), a.get("sampling_rate", 16000)
    s = a.get_all_samples()
    arr = np.asarray(s.data.cpu() if hasattr(s.data, "cpu") else s.data,
                     dtype=np.float32).squeeze()
    if arr.ndim > 1:
        arr = arr.mean(axis=0)
    return arr, s.sample_rate

def pre(x):
    arr, sr = load_audio(x)
    arr = np.pad(arr, (0, max(0, MAX - len(arr))))[:MAX]
    return processor(arr, sampling_rate=sr).input_values[0]
train_ds = train_ds.map(lambda x: {"input_values": pre(x)}, remove_columns=["audio"])
val_ds   = val_ds.map(lambda x: {"input_values": pre(x)}, remove_columns=["audio"])

args = TrainingArguments(
    output_dir="/kaggle/working/vs_out",
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    gradient_accumulation_steps=1,
    learning_rate=3e-5,
    num_train_epochs=3,
    evaluation_strategy="epoch",
    save_strategy="epoch",
    logging_steps=50,
    report_to=[],
    fp16=True,
    metric_for_best_model="eval_accuracy",
    load_best_model_at_end=True,
)
acc = evaluate.load("accuracy")
trainer = Trainer(model=model, args=args, train_dataset=train_ds,
                  eval_dataset=val_ds,
                  compute_metrics=lambda p: acc.compute(
                      predictions=p.predictions.argmax(-1), references=p.label_ids))
trainer.train()
model.save_pretrained("/kaggle/working/vs_model")
processor.save_pretrained("/kaggle/working/vs_model")
print("DONE → /kaggle/working/vs_model")
'''


# ─────────────────────────────────────────────────────────────────────────────
def parse_cells(text):
    """Split markdown `text` (with ```code blocks) into notebook cells."""
    cells = []
    parts = re.split(r"```[a-z]*\n", text)
    for i, part in enumerate(parts):
        part = textwrap.dedent(part).strip("\n")
        if not part.strip():
            continue
        if i % 2 == 1:
            cells.append({"cell_type": "code", "metadata": {},
                          "execution_count": None, "source": part.splitlines(keepends=True),
                          "outputs": []})
        else:
            cells.append({"cell_type": "markdown", "metadata": {},
                          "source": part.splitlines(keepends=True)})
    return cells


def make_ipynb(title, text, name):
    meta = {
        "kernelspec": {"name": "python3", "display_name": "Python 3"},
        "language_info": {"name": "python"},
        "accelerator": "GPU",
        "colab": {"provenance": []},
    }
    cells = [{"cell_type": "markdown", "metadata": {},
              "source": [f"# {title}\n"]}] + parse_cells(text)
    nb = {"nbformat": 4, "nbformat_minor": 0, "metadata": meta, "cells": cells}
    (OUT / name).write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote", name, "·", len(cells), "cells")


def main():
    import base64
    repo = Path(__file__).resolve().parent.parent
    module_b64 = base64.b64encode(
        (repo / "backend" / "training" / "cloud_dataset.py").read_bytes()).decode()

    nb01 = NOTEBOOK_01.replace("{{CLOUD_DATASET_B64}}", module_b64)
    make_ipynb("01 · Build SIH dataset (real voice-clone spoofs)",
               nb01, "colab_01_build_dataset.ipynb")
    make_ipynb("02 · Train wav2vec2-base deepfake classifier",
               NOTEBOOK_02, "colab_02_train_wav2vec2.ipynb")
    make_ipynb("03 · Train XLSR-300m cross-lingual classifier",
               NOTEBOOK_03, "colab_03_train_xlsr.ipynb")
    (OUT / "kaggle_train_wav2vec2.py").write_text(
        textwrap.dedent(KAGGLE_TRAIN), encoding="utf-8")
    print("wrote kaggle_train_wav2vec2.py")


if __name__ == "__main__":
    main()
