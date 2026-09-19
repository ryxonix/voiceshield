
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
