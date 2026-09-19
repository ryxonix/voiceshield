# VoiceShield AI · Cloud Training Kit (Colab & Kaggle, SIH-compliant)

Train the real-time voice-deepfake / voice-impersonation model on **free GPU
cloud resources** (Google Colab, Kaggle) using **lots of SIH-compliant data** —
real Indian-language human voices plus **REAL A.I. voice impersonation**
(cloned voices of the very same speakers).

> Read `backend/SOURCES_AND_TECHNOLOGY.md` for the full source/licence table.

---

## Why "REAL voice impersonation", not just TTS?

The SIH problem statement is **real-time A.I. voice detection** and **voice
impersonation**. A model trained only on plain text‑to‑speech (robocall)
voices never sees the real attack: a fraudster *cloning a victim's voice* on a
live call. So this kit generates spoofs by actually cloning the same humans
that appear as "bonafide" in the training set:

| Spoof generator    | What it does                                                            | License      | Languages             |
|--------------------|-------------------------------------------------------------------------|--------------|-----------------------|
| **Coqui XTTS-v2**  | zero-shot voice clone of the bonafide speaker, speaking attacker text  | CPML-1.0*    | en, hi (+15 more)     |
| **RVC**            | coqui-free voice conversion into a cloned target voice                 | MIT          | any                   |
| **FreeVC / FreeVC24** | zero-shot voice conversion                                            | MIT          | any                   |
| **edge-tts**       | plain Microsoft neural TTS (minority auxiliary attack class)           | free, no key* | 9 Indian languages    |

`*` edge-tts / gTTS are community-maintained wrappers around vendor TTS **web
endpoints** (unofficial, no API contract) — used only for evaluation/demo
sample generation; the generated audio is ours and never shipped.

`*` CPML = Coqui Public Model Licence v1 — free for research / non-commercial
use (a hackathon entry qualifies). We ship the **generated audio**, not the
model weights, so no redistribution restriction applies. ⚠️ CPML is
**non-commercial only** — a commercial/production retrain should regenerate
the spoof pool with MIT cloners (RVC / FreeVC / Chatterbox) instead.

## What the notebooks do

| Notebook | Purpose |
|----------|---------|
| `colab_01_build_dataset.ipynb` | FLEURS (CC-BY-4.0) + optional Common Voice (CC-BY-4.0) real speech; **XTTS-v2 cloning** spoofs; minority edge-tts class; balanced train/val CSVs; push to HF Hub / save to Drive |
| `colab_02_train_wav2vec2.ipynb` | HuggingFace `Trainer`: audio-classification fine-tune of `wav2vec2-base-960h` (fast, fits free T4) |
| `colab_03_train_xlsr.ipynb` | same recipe with `facebook/wav2vec2-xls-r-300m` for best cross-lingual Indic accuracy |
| `kaggle_train_wav2vec2.py` | Kaggle-dataset equivalent of notebook 02 |

The code all lives in one module: `backend/training/cloud_dataset.py`
(`fetch_fleurs`, `fetch_commonvoice`, `generate_xtts_spoofs`,
`generate_rvc_spoofs`, `generate_freevc_spoofs`, `generate_edge_spoofs`,
`build_and_split`). Notebooks pull it from this repo by URL.

## How to run (copy-paste flow)

### A. Google Colab

1. **`colab_01_build_dataset.ipynb`** → Run all (Runtime ▶ Run all).
   - Needs: a free Colab account. T4 GPU auto-selected for the XTTS step.
   - Optional: mount Drive (keeps the `train.csv` / `val.csv` / audio for
     notebooks 02–03) and add `HF_TOKEN` in the secrets panel to push the
     dataset to the Hub (`VAIVE/voiceshield-sih`).
2. **`colab_02_train_wav2vec2.ipynb`** → Run all.
   - Reads `MyDrive/voiceshield_cloud/{train,val}.csv` (or the HF dataset).
   - Saves the fine-tuned model to Drive and optionally pushes it to the Hub.
3. **`colab_03_train_xlsr.ipynb`** → same, with the bigger XLS-R model.
4. Download the saved model, drop it into `backend/models/<name>/`, and point
   `backend/app/config.py` (`AI_MODEL_PATH`) at it (or load directly from the
   HF Hub at runtime).

### B. Kaggle

1. From `colab_01`, push the dataset to the Hub (private is fine), or download
   `train.csv` / `val.csv` + audio and upload them as a Kaggle Dataset named
   `voiceshield-sih`.
2. New Notebook → **Import** `kaggle_train_wav2vec2.py` → in the top-right
   **Add Input** → pick `voiceshield-sih`.
3. Run with **GPU‑T4 x 2** accelerator. Model lands in
   `/kaggle/working/vs_model`.

## Scaling for a big SIH-grade corpus

- Increase `per_language` in notebook 01 (FLEURS per-split sizes: nhi≈16 k,
  en≈10 k, others 1–8 k) — free Colab will get slower, that's why we split
  work across notebooks.
- To add more real voices cheaply: enable
  `fetch_commonvoice(..., per_language=…)` in notebook 01 (CC-BY-4.0, big).
- To add more real clones: `per_speaker` controls how many XTTS clones per
  bonafide speaker; RVC needs a `.pth` + index in Drive (see cell comments).

## SIH compliance (why nothing here disqualifies you)

- **FLEURS** — CC-BY-4.0 (attribution license → permitted in SIH, credit in
  `SOURCES_AND_TECHNOLOGY.md`).
- **Common Voice** — CC0 (public domain, no strings attached) in earlier
  releases; CC-BY-4.0 from v14.
- **XTTS/RVC/FreeVC clones & edge-tts audio** — generated by us, using open,
  non-commercial-permissible models; we ship generated audio only.
- **ASVspoof** is explicitly **excluded** (research-licence, cannot be
  redistributed/used for a hackathon entry).
- No phone-scraped or personal data. No licensed-benchmark audio copies.

## After training (deploy path)

1. Export the classifier to ONNX (or load the HF checkpoint in
   `backend/app/engine/` — see the existing Dhwani/AASIST ensemble).
2. Re-run `backend/training/evaluate.py` on the new checkpoint.
3. Re-export the fallback AASIST ONNX if you replace the ILM:
   `python -m app.models.export_onnx checkpoints/best_model.pth`.
4. Keep the ensemble: Dhwani (XLS-R + AASIST official) stays the primary
   detector; the fine-tuned wav2vec2 is the SIH-specific classifier you can
   showcase alongside it.