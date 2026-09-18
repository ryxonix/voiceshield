# 🛡️ VoiceShield AI

**Zero-trust, real-time audio deepfake detection and mitigation platform optimized for the Indian telecom context.**

> All external services are **100% free** — no credit card required. Optimized for `.edu.in` student accounts.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      React Dashboard (Vite)                     │
│  Waveform │ Risk Gauge │ XAI Panel │ Child Shield │ Alerts     │
└────────────────────────────┬────────────────────────────────────┘
                             │ WebSocket (scores only, no audio)
┌────────────────────────────┴────────────────────────────────────┐
│                    FastAPI Backend (Python)                      │
│                                                                  │
│  ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌──────────────┐  │
│  │Ring Buffer│→│Feature Ext.│→│AASIST ONNX │→│ Risk Fusion  │  │
│  │300ms/100ms│  │Jitter,    │  │INT8 ~85K   │  │0.7×M+0.3×XAI│  │
│  │  hop      │  │Shimmer,   │  │params      │  │             │  │
│  │           │  │Phase, f0  │  │<50ms CPU   │  │+ Watermark  │  │
│  └──────────┘  └───────────┘  └───────────┘  └──────┬───────┘  │
│                                                       │          │
│  ┌────────────────────────────────────────────────────┴───────┐  │
│  │              Role-Aware Mitigation Engine                  │  │
│  │  Adult ≥0.85 → Risk Banner + Alerts                       │  │
│  │  Child ≥0.70 → Mute + Shield Overlay + Alerts             │  │
│  └────────────────────────┬───────────────────────────────────┘  │
│                           │                                      │
│  ┌────────────────────────┴───────────────────────────────────┐  │
│  │         Multi-Channel Alert Dispatcher (ALL FREE)          │  │
│  │  Telegram │ Gmail SMTP │ ntfy.sh │ Fast2SMS │ Webhook      │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────┐  ┌──────────────────────────────────┐  │
│  │ I4C Forensic PDF     │  │ DPDP Act Compliance             │  │
│  │ (ReportLab, IST)     │  │ Ephemeral RAM, Zero Disk        │  │
│  └──────────────────────┘  └──────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## ✨ Features

- **AASIST-L Backbone** (~85K params) — Spectro-temporal graph attention for artifact detection
- **Telecom-Hardened** — G.711, AMR-NB/WB, PLC, bandwidth truncation augmentations
- **Sub-78ms Latency** — INT8 quantized ONNX inference on CPU
- **Explainable AI** — Jitter, Shimmer, Phase Continuity, Pitch Stability
- **Enterprise Watermark** — VoLTE-band (7.0–7.5 kHz) pilot tone verification
- **Child Shield Protocol** — Lowered threshold (0.70), auto-mute, protective overlay
- **I4C-Ready PDF Reports** — IST timestamps, legal next steps, forensic evidence format
- **DPDP Act Compliant** — Ephemeral RAM processing, zero disk storage, scalar-only telemetry
- **100% Free Stack** — Telegram, Gmail, ntfy.sh, Fast2SMS, all open-source

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **ffmpeg** (optional, for AMR codec augmentation during training)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# Install dependencies (all free/open-source)
pip install -r requirements.txt

# Copy and configure environment
copy .env.example .env
# Edit .env with your free API keys (see below)

# Export initial ONNX model (randomly initialized)
python -m app.models.export_onnx

# Start the server
python -m app.main
# or: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
# Opens at http://localhost:5173
```

### Free API Setup (All Optional)

| Service | Setup Steps | Time |
|---|---|---|
| **Telegram** | Open Telegram → Message @BotFather → `/newbot` → Copy token | 1 min |
| **Gmail SMTP** | Google Account → Security → 2FA → App Passwords → Generate | 2 min |
| **ntfy.sh** | No setup! Just pick a topic name. Install app on phone for notifications | 0 min |
| **Fast2SMS** | Sign up at fast2sms.com → Dashboard → API Key (free credits included) | 3 min |

## 📁 Project Structure

```
voiceshield/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Pydantic settings
│   │   ├── models/              # AASIST-L model
│   │   │   ├── aasist.py        # PyTorch architecture
│   │   │   ├── export_onnx.py   # ONNX export + INT8
│   │   │   └── inference.py     # ONNX Runtime wrapper
│   │   ├── engine/              # Detection engine
│   │   │   ├── ring_buffer.py   # Streaming ring buffer
│   │   │   ├── features.py      # Prosodic XAI extraction
│   │   │   ├── watermark.py     # Watermark verifier
│   │   │   ├── fusion.py        # Risk score fusion
│   │   │   └── session.py       # Session state manager
│   │   ├── streaming/
│   │   │   └── websocket.py     # WebSocket endpoint
│   │   ├── mitigation/
│   │   │   ├── router.py        # Role-aware mitigation
│   │   │   ├── child_shield.py  # Child Shield protocol
│   │   │   └── alerts.py        # Multi-channel alerts
│   │   ├── forensics/
│   │   │   └── pdf_report.py    # I4C PDF generator
│   │   └── compliance/
│   │       └── dpdp.py          # DPDP Act compliance
│   ├── training/                # Model training pipeline
│   │   ├── augmentations.py     # Telecom codec augmentations
│   │   ├── dataset.py           # ASVspoof dataset loader
│   │   ├── train.py             # Training loop
│   │   └── evaluate.py          # EER/t-DCF evaluation
│   ├── tests/                   # Unit tests
│   ├── models/                  # ONNX model files
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/          # React components
│   │   ├── hooks/               # Custom hooks
│   │   ├── App.jsx
│   │   └── index.css            # Design system
│   └── package.json
└── README.md
```

## 🔒 Privacy & Compliance

This platform is designed for **DPDP Act (2023)** compliance:

- ✅ **Ephemeral Processing**: Audio buffers exist strictly in RAM, overwritten every 100ms
- ✅ **Zero Disk Storage**: Raw audio is never written to disk or transmitted to cloud
- ✅ **Minimized Telemetry**: Only mathematical sub-scores and scalar scores are transmitted
- ✅ **Secure Cleanup**: All session buffers are cryptographically wiped on disconnect
- ✅ **Audit Trail**: Only non-PII scalar data is logged (scores, timestamps, actions)

## 📊 Latency Budget (per 100ms window step)

| Stage | Budget | Description |
|---|---|---|
| WebSocket Ingest | ≤ 5 ms | Binary PCM frame reception |
| Ring Buffer | ≤ 2 ms | Sliding window accumulation |
| Feature Extraction | ≤ 20 ms | Jitter, Shimmer, Phase, f0 |
| AASIST ONNX (INT8) | ≤ 35 ms | Model inference on CPU |
| Watermark Check | ≤ 5 ms | FFT pilot tone scan |
| Risk Fusion | ≤ 1 ms | Score combination |
| Mitigation Dispatch | ≤ 10 ms | Alert routing |
| **Total** | **≤ 78 ms** | |

## 📜 License

MIT License — Free for academic and commercial use.

## 🙏 Acknowledgments

- AASIST architecture: Jung et al., "AASIST: Audio Anti-Spoofing using Integrated Spectro-Temporal Graph Attention Networks" (ICASSP 2022)
- ASVspoof Challenge for benchmark datasets
- Indian Cyber Crime Coordination Centre (I4C) for forensic reporting standards
