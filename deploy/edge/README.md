# VoiceShield AI — On-device / Edge worker

Thin standalone runner that executes the **same** ONNX + DSP detection pipeline
on a local box (NUC / RPi-class / PoE gateway) without a web server, database,
or network. This fulfils the "on-device or edge inference" option in SIH26104's
privacy module: annotate/flag audio near the source, store **scalars only**, and
optionally forward them to the central platform later.

## Install (on the edge box)

```bash
pip install numpy librosa soundfile onnxruntime   # minimal set
# (torch is optional — used only for export/retraining, not inference)
```

No code changes: the worker imports the shared `backend/app` pipeline modules
via `sys.path`.

## Run

```bash
python deploy/edge/vs_edge.py --input call.wav --role adult
python deploy/edge/vs_edge.py --input a.wav cloned.wav --role adult --json
```

Output (human): one line per file with peak score, risk band, recommendation.
With `--json`: full window table — a **feature-only log** (no audio retained).

## Honest scope

- This is an **edge inference worker**, not a mobile app. It proves the on-device
  path with the exact model artifact the server uses (`aasist_l.onnx`, INT8,
  ~35 ms/window on a 2-core CPU).
- Window sizing auto-matches the server: 3 s / 1 s hop when the Dhwani model is
  present, 300 ms / 100 ms hop for the bare AASIST-L fallback.
- Real-time capture (mic) is intentionally out of scope — feed from a recorder or
  a stream consumer; the pipeline itself is real-time capable end to end.