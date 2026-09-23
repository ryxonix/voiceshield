# 🛡️ VoiceShield AI

**Zero-trust, real-time audio deepfake detection and mitigation platform for the Indian telecom context.**

VoiceShield AI listens to live voice calls (or analyzes uploaded audio) and tells you in real time whether the speaker is a **real human** or a **synthetic/deepfake voice** (AI voice clone). It is built for use by telecom providers, banks, contact centers, and parents (Child Shield) — everything runs on a **free, open-licensed stack** (attribution licenses retained; full inventory in [`backend/SOURCES_AND_TECHNOLOGY.md`](backend/SOURCES_AND_TECHNOLOGY.md)).

> 🔴 **SIH-ready** — all training data is from open licenses (FLEURS CC-BY-4.0, Common Voice CC-BY-4.0 — CC0 for v13 and earlier, self-generated TTS + **real voice-clone impersonation** via XTTS-v2/RVC/FreeVC). See [`backend/SOURCES_AND_TECHNOLOGY.md`](backend/SOURCES_AND_TECHNOLOGY.md) for full data sources, licenses, and compliance.

---

## 🧠 What it does (in one picture)

```
Real Person OR AI Clone? ──▶ listen live / upload file
        │
        ▼
┌────────────────────────────────────────────┐
│  Detection Pipeline (backend/app/engine)    │
│  • Acoustic DL models:                       │
│      - Dhwani (Wav2Vec2 XLS-R + AASIST)      │   ← trained on Indian languages
│      - AASIST-L official pretrained          │   ← ensemble
│      - local AASIST-L (retrained, fallback)  │
│  • XAI prosody layer:                        │
│      jitter / shimmer / phase continuity     │
│  • Cross-session speaker consistency         │
│  • Enterprise watermark (VoLTE-band pilot)   │
└────────────────────┬───────────────────────┘
                     ▼
   Risk Score (0–1)  ─▶  verdict + risk band
                     ▼
   Real-time alerts:  Telegram ・ Gmail ・ ntfy.sh
                      Fast2SMS ・ Webhook
                     ▼
Incident log  ─▶  I4C-ready forensic PDF
                      └── anchored on a proof-of-work
                          PoW block + NBF-Fabric (Vishvasya)
                          external anchor (hash + IPFS CID)
```

**Key ideas**

- **Multi-layer detection, not one model.** Raw audio is scored by ensemble acoustic models AND by explainable prosodic features (jitter/shimmer/phase continuity). Both are combined: `score = 0.7 × model_prob + 0.3 × xai_risk`.
- **Real-time by design.** Windows stream over WebSocket; model runs per window; only scalar scores cross the wire (no raw audio leaves the user's device/network — DPDP-safe).
- **Free alerts everywhere.** Telegram, Gmail SMTP, ntfy.sh, Fast2SMS, and webhooks.
- **Tamper-evident reports.** Every forensic PDF is hashed and anchored into a local proof-of-work blockchain ledger, then mirrored to a **Hyperledger Fabric (MeitY NBF-Lite)** external anchor with an **AES-256-GCM** ciphertext copy pinned on IPFS (raw forensic content never leaves operator custody — DPDP-safe).

---

## ✨ Feature list

| Area | What's included |
|---|---|
| Detection | Dhwani (multilingual Indian deepfake model) + AASIST-L official ensemble, INT8 ONNX inference on CPU |
| Explainability | Jitter %, Shimmer %, Phase Continuity, Pitch Stability, noise-floor dropouts |
| Real-time | Live call analysis over WebSocket, 3 s windows / 1 s hop (300 ms/100 ms fallback). A **latency profile** governs the live hot loop: `latency_profile=realtime` (default) scores each window with the trained AASIST-L official + XAI prosody (`VOICESHIELD_LATENCY_BUDGET_MS`-gated, measured ~1.5-1.6 s/window on reference CPU); `latency_profile=ensemble` runs the full Dhwani ensemble live (seconds/window) |
| Risk | Role-aware thresholds — Adult ≥ 0.85 critical, Child ≥ 0.70 critical (`ADULT_THRESHOLD` / `CHILD_THRESHOLD` in `.env`) |
| Alerting | Telegram, Gmail SMTP, ntfy.sh, Fast2SMS, webhook — all optional |
| Escalation | **Suspected** fraud → optional DoT conduct hand-off (Sanchar Saathi / Chakshu / DIP) via `CHAKSHU_DIP_WEBHOOK_URL`; **confirmed** fraud → I4C/1930 flow in the forensic PDF |
| Context | Optional **call-context enrichment** (opt-in, `CONTEXTUAL_ENRICHMENT=true`): known-contact, caller reputation (escalation count), call-origin and transaction value adjust the risk before thresholds — fail-open when no context is provided |
| Verification | **Configurable mitigation workflows** (`backend/workflows.json`, JSON — no code deploy): per-role × risk-band actions + channels (pre-transaction call-back, MFA, supervisor escalation) with `POST /api/incidents/{iid}/escalate` feeding back caller reputation |
| SDK | Official **Python SDK** (`backend/sdk/voiceshield_sdk`, sync + async) on an API contract defined in `backend/sdk/voiceshield.proto` (proto3) — REST + live WebSocket call sessions |
| On-device | **Edge inference worker** (`deploy/edge/vs_edge.py`) — CLI-only, no GPU/cloud dependency, proves the on-device inference option |
| Child Shield | Lower threshold, auto-mute, protective overlay |
| Forensics | I4C-ready PDF reports (IST timestamps, legal next steps) |
| Integrity | SHA-256 + Merkle-root anchored to a PoW blockchain ledger |
| NBF anchor | **MANDATORY (fail-closed).** Every block is ALSO cryptographically anchored on a **MeitY National Blockchain Framework (Hyperledger Fabric)** ledger with IPFS-pinned AES-256-GCM ciphertext. A forensic report is committed to the local ledger only **after** a real on-chain anchor succeeded (`BLOCKCHAIN_EXTERNAL_ANCHOR=true` + `BLOCKCHAIN_ANCHOR_REQUIRED=true` by default). Any gateway/provider failure raises `BlockAnchorError` and the report is refused — no unvalidated `demo`/`pending` report can be handed off as anchored. Explicitly disabling both flags restores the offline DemoAnchor shadow for laptop demos only |
| Speaker ID | Enrollment + cross-session voice-print consistency (one-way, DPDP-safe) |
| Privacy | Ephemeral RAM processing, zero disk for raw audio, scalar-only telemetry |
| i18n | Dashboard UI in English / हिन्दी / ಕನ್ನಡ (context-aware translations) |
| Languages | Detection tuned for Hindi, English, Kannada (+ Tamil/Telugu/Malayalam via Dhwani) |

---

## 🚀 Quick start (5 minutes)

### Prerequisites

- **Python 3.10+** and **Node.js 18+**
- **ffmpeg** (optional — only needed for AMR codec augmentation during training)

### 1. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # Linux / Mac

pip install -r requirements.txt
```

### 2. Create the environment file and add your keys

```bash
copy .env.example .env           # Windows
# cp .env.example .env           # Linux / Mac
```

> 📄 **Where do API keys go?** → **`backend/.env`** (this exact file). It is read by `backend/app/config.py` on startup, and it is already git-ignored so secrets are never committed.

The `.env` has clearly-marked sections. Here is exactly what goes where:

| What | Variable in `backend/.env` | Where to get it (all FREE) |
|---|---|---|
| Telegram alerts | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | https://t.me/BotFather |
| Email alerts | `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_EMAIL_TO` | Gmail App Password (2FA → Security → App Passwords) |
| Push alerts | `NTFY_TOPIC` | https://ntfy.sh (no signup) |
| SMS (India) | `FAST2SMS_API_KEY`, `FAST2SMS_TO_NUMBER` | https://www.fast2sms.com |
| Webhook | `WEBHOOK_URL` | any endpoint you control |
| Email API (alt) | `RESEND_API_KEY` | https://resend.com |
| Error tracking | `SENTRY_DSN` | https://sentry.io |
| Training data | `HF_TOKEN` | https://huggingface.co/settings/tokens (needed only for private gated repos; FLEURS is public) |
| Telemetry store | `DATABASE_URL` | reserved for optional Neon PostgreSQL — detection telemetry persists to local SQLite (`backend/voiceshield.db`) regardless |

**Blockchain API keys** → the same file, section `⛓ BLOCKCHAIN REPORT LEDGER`:
- The report ledger is **local and needs NO external key** (`BLOCKCHAIN_DIFFICULTY` is just the PoW difficulty, default 4).
- `BLOCKCHAIN_RPC_URL`, `BLOCKCHAIN_EXPLORER_API_KEY`, `BLOCKCHAIN_ANCHOR_ADDRESS` are **optional** anchors if you later pin block hashes to a public chain.
- **NBF-Lite external anchor — MANDATORY by default** (fail-closed): `BLOCKCHAIN_EXTERNAL_ANCHOR=true` (default) selects the real Hyperledger Fabric + IPFS provider through the gateway in [`deploy/nbf-fabric/`](deploy/nbf-fabric/) — see the [NBF anchor section](#-nbf-anchor-network-meity-vishvasya). `BLOCKCHAIN_ANCHOR_REQUIRED=true` (default) means a forensic report is only written to the local ledger **after** the on-chain anchor succeeded: any gateway/provider failure raises `BlockAnchorError` and the report endpoint refuses (503), and verification of an unanchored report reports it as NOT blockchain-anchored. Configure `NBF_GATEWAY_URL=http://<host>:4000` + the `NBF_*` settings. **Offline dev/demo only** — set `BLOCKCHAIN_EXTERNAL_ANCHOR=false` **and** `BLOCKCHAIN_ANCHOR_REQUIRED=false` to use the local `DemoAnchor` shadow (status `demo`, never `anchored`) so the repo works on a laptop with no Fabric node.
- Exactly one variable per line, restart the backend after editing.

### 3. Start the backend

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# API docs at  http://localhost:8000/docs
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
# Dashboard at  http://localhost:5173
```

### 5. One-command start (Windows)

Double-click **`start_all.bat`** (backend :8000 + frontend :5173).

---

## 🔌 REST API (all endpoints)

| Method | Route | What it does |
|---|---|---|
| POST | `/api/analyze` | Analyze an uploaded audio file (full windowed sweep) |
| POST | `/api/detect` | Quick detection on a single audio payload |
| WS | `/ws/stream/{call_id}` | Live streaming detection during a call |
| GET | `/api/sessions` | List sessions |
| GET | `/api/sessions/{sid}` | Session detail |
| GET | `/api/sessions/{sid}/windows` | Per-window telemetry |
| GET | `/api/incidents` | List incidents |
| GET | `/api/incidents/{iid}` | Incident detail |
| POST | `/api/incidents/{iid}/ack` | Acknowledge an incident |
| GET | `/api/incidents/{iid}/report` | Incident forensic PDF |
| GET | `/api/report/{call_id}` | Forensic PDF by call id |
| GET | `/api/blockchain` | Ledger status + all blocks |
| GET | `/api/blockchain/{index}` | Single block |
| GET | `/api/blockchain/verify/call/{call_id}` | Full tamper-evidence check |
| GET | `/api/blockchain/verify/block/{index}` | PoW + hash integrity check |
| GET | `/api/blockchain/onchain` | NBF anchor summary (count + per-block link) |
| GET | `/api/blockchain/onchain/{call_id}` | External anchor status/verification for one call |
| POST | `/api/blockchain/retry/{call_id}` | Re-attempt a `pending` NBF-Fabric/IPFS anchor |
| POST | `/api/speakers/register` | Enroll a speaker voice-print |
| POST | `/api/incidents/{iid}/escalate` | Confirm fraud → escalate + bump caller reputation for future calls |
| GET | `/api/workflows` | Current mitigation workflow rules (adult/child × risk band) |
| GET | `/health`, `/info` | Health / model status |

> `/api/analyze` also accepts optional context fields (multipart form: `caller`, `origin`, `txn_value`, `txn_category`, `known_contact`); the live WebSocket accepts the same as query params. See [`backend/sdk/SDK_README.md`](backend/sdk/SDK_README.md) for the SDK + proto contract.

---

## 📁 Project structure

```
voiceshield/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point (all REST endpoints)
│   │   ├── config.py            # Pydantic settings ↔ backend/.env
│   │   ├── grpc/                # gRPC servicer, proto pb2, server (port 50051)
│   │   ├── models/              # AASIST-L architecture + ONNX inference + export
│   │   ├── engine/              # dhwani, aasist_official, prosody, fusion,
│   │   │                        #   ring_buffer, watermark, speaker, risk,
│   │   │                        #   pipeline
│   │   ├── context/             # call-context enrichment (opt-in)
│   │   ├── streaming/           # WebSocket live-call endpoint
│   │   ├── mitigation/          # Role-aware alerts + configurable workflows
│   │   │                        #   (workflows.py + ../workflows.json), escalate
│   │   ├── forensics/           # I4C-ready PDF reports
│   │   ├── blockchain/          # PoW report ledger (local) + external NBF anchor
│   │   │   │                    #   external_anchor.py (AES-256-GCM, IPFS, gateway)
│   │   ├── compliance/          # DPDP Act posture helpers
│   │   └── store.py             # In-memory / Neon persistence
│   ├── sdk/                     # voiceshield_sdk (sync/async) + voiceshield.proto
│   │   │                        #   + grpc.py client (SDK ↔ app/grpc servicer)
│   ├── workflows.json           # editable mitigation workflow rules (bank/enterprise/gov)
│   ├── training/                # augmentations, dataset, train, evaluate,
│   │   │                        #   fetch_indic (FLEURS + TTS spoof), merge_protocols
│   ├── models/                  # ONNX + .onnx.data (aasist_l, dhwani — git-ignored, regenerate via export_onnx)
│   ├── hf_models/aasist/        # official AASIST-L pretrained repo (MIT)
│   ├── data/                    # training + evaluation audio (git-ignored)
│   ├── checkpoints/             # trained weights + training_log.txt
│   ├── .env.example             # ← copy to .env
│   ├── .env                     # ← ADD YOUR API KEYS HERE
│   ├── SOURCES_AND_TECHNOLOGY.md  # data licenses + tech inventory (SIH)
│   └── requirements.txt
├── deploy/
│   └── edge/                    # vs_edge.py — on-device inference worker (CLI)
├── frontend/
│   ├── src/
│   │   ├── pages/               # Dashboard, Incidents, Reports
│   │   ├── components/          # RiskGauge, Radar, SessionCard, ShieldBanner, ui
│   │   ├── i18n.tsx             # en / hi / kn translations
│   │   └── ...
└── start_all.bat                # starts backend + frontend
```

---

## 🎓 Training the model (SIH-compliant)

Training uses **only open-license data**:

- **Bonafide (real human voices)** — Google FLEURS (CC-BY-4.0) for Hindi / English / Kannada (+ Common Voice CC-BY-4.0 in the cloud pipeline).
- **Spoof — REAL A.I. voice impersonation** — the cloud pipeline clones the *actual* bonafide speakers with **Coqui XTTS-v2** (CPML-1.0, research/non-commercial hackathon use) so the "attacker" speaks in the victim's cloned voice. **RVC / FreeVC** (MIT) add conversion-style clones. This targets the actual SIH problem (voice impersonation), not just robocall TTS. *⚠️ XTTS is non-commercial-only; a commercial production retrain should regenerate the spoof pool with MIT cloners (RVC/FreeVC/Chatterbox).*
- **Auxiliary pure-TTS class** — edge-tts / gTTS (minority, ~9 Indian languages).
- **Augmentations** — G.711, AMR-NB/WB, packet-loss, bandwidth, and noise that simulate Indian telecom networks.

### Option A — Cloud (recommended, free GPU, big corpus)

See **[`cloud/`](cloud/README.md)** — ready-to-run Google Colab + Kaggle notebooks:

```text
colab_01_build_dataset.ipynb   # real voices + REAL XTTS/RVC/FreeVC clones → train/val CSVs
colab_02_train_wav2vec2.ipynb  # wav2vec2-base audio classifier (fits free T4)
colab_03_train_xlsr.ipynb      # XLSR-300m for best Indic cross-lingual accuracy
kaggle_train_wav2vec2.py       # Kaggle equivalent
```

### Option B — On-device (CPU, small set, AASIST-L fallback)

```bash
cd backend
# 1. (optional) fetch more data
python -m training.fetch_indic --language hindi   --bonafide 200 --spoof 200 --out data/indic
python -m training.fetch_indic --language english --bonafide 200 --spoof 200 --out data/indic
python -m training.fetch_indic --language kannada --bonafide 200 --spoof 200 --out data/indic

# 2. build the expanded SIH dataset (real speech + cloned/TTS spoofs)
python -m training.build_sih_dataset --out data/indic --bonafide 200 --spoof 150
python -m training.merge_protocols --data_dir data/indic --output data/indic/merged

# 3. train AASIST-L
python -m training.train --train_dir data/indic --train_protocol data/indic/merged_train.txt \
                         --val_dir data/indic --val_protocol data/indic/merged_val.txt \
                         --save_dir checkpoints --epochs 30

# 4. export to ONNX + INT8
python -m app.models.export_onnx checkpoints/best_model.pth
```

> ⚠️ The retrained local AASIST-L is the **fallback** detector. The primary production path uses the **Dhwani** and **official AASIST-L** pretrained models (loaded automatically when present).
>
> 📦 Trained weights (`checkpoints/*.pth`, `models/aasist_l.onnx`) are git-ignored artifacts. On a fresh clone, regenerate the ONNX fallback with `python -m app.models.export_onnx checkpoints/best_model.pth`; until then inference returns a neutral 0.5.

---

> ⚠️ **Suspected vs confirmed fraud (two flows):** when the risk score crosses the
> threshold, flagged-call **metadata** can be routed to the DoT side (Chakshu /
> Sanchar Saathi / Digital Intelligence Platform) as **suspected** fraud for
> network-level action (`CHAKSHU_DIP_WEBHOOK_URL`). If the user has actually
> lost money / is a cyber-crime victim, the forensic PDF directs them to the
> **confirmed** post-fraud reporting path — **1930 helpline / cybercrime.gov.in /
> RBI Sachet** (`https://sachet.rbi.org.in`). Chakshu/DIP are citizen-facing
> portals (no public API) — the webhook is *your* documented integration point.

---

## 🔒 Privacy & compliance (DPDP Act 2023)

- ✅ Ephemeral processing — audio buffers live in RAM, overwritten every window
- ✅ Zero disk storage — raw audio is never written to disk by the live path
- ✅ Minimized telemetry — only scalar sub-scores cross the wire/WebSocket
- ✅ One-way speaker embeddings — audio can never be reconstructed
- ✅ Audit trail — non-PII scalar data only

---

## 📊 Latency budget (per window) — measured, two profiles

The hot loop is `app.engine.pipeline.analyze_window` — the exact callable the WebSocket live driver, the gRPC servicer, and `/api/analyze` run per window. It self-reports its `latency_ms`, and `tests/test_latency_gate.py` enforces the **real-time** budget fail-hard on the real hot loop (median of ≥20 post-warmup runs; `VOICESHIELD_LATENCY_BUDGET_MS` is the only way to raise it, and it is printed when used).

| Profile | Models per window | Measured (3 s window, reference CPU) | Gate |
|---|---|---|---|
| **realtime** *(default)* | trained AASIST-L official + XAI prosody (legacy ONNX only as last resort) | XAI ~0.77 s, model ~0.78 s → **total ~1.5-1.6 s median** | `latency_budget_ms=2000` (default) fail-hard |
| **ensemble** *(opt-in streaming; always for `/api/analyze` + gRPC Analyze)* | Dhwani + AASIST-L official (+ XLS-R in file analyze) | Dhwani ~1.9 s, ensemble ~4.1 s, +XLS-R ~5.7 s (cold load ~72 s) | No streaming contract — bounded batch, sized by the SDK RPC timeout (default 120 s) |

The original README table (ingest ≤7 / prosody ≤20 / model ≤35 / fusion ≤16 = **≤78 ms total**) was retired because it is physically unreachable on CPU: `librosa.pyin`-based prosody alone measures ~0.77 s and the trained AASIST-L official ~0.78 s. This section now documents the real numbers instead of a fabricated budget. Windows are 3 s / 1 s hop by default (300 ms / 100 ms fallback when no 3 s model is present). `latency_profile` is set in `backend/.env` (`LATENCY_PROFILE`) or `VOICESHIELD_`-prefixed env; the forensic `/api/analyze` surface always uses the full ensemble regardless of profile.

---

## ⛓ NBF anchor network (MeitY Vishvasya)

Every locally-mined report block is **also** committed to a permissioned **Hyperledger Fabric** ledger through an NBF-Lite-compatible REST gateway, with the report PDF stored on **IPFS as ciphertext**.

```
Forensic PDF ──▶ AES-256-GCM ──▶ IPFS /store ──▶ CID
                                      │
Local PoW block ──▶ NBF gateway ──▶ Fabric chaincode AnchorReport
                  (block_hash, merkle_root, file_sha256,
                   ipfs_cid, enc_alg, key_fp)
```

- **Private by design**: only hashes / CID / key fingerprint go on the ledger; the raw PDF stays encrypted under an operator-held master key (`reports/keys/org_master.key`). Ciphertext is pinned to IPFS so the full record is recoverable and tamper-evident without exposing voice content.
- **Fail-closed (MANDATORY by default)**: `BLOCKCHAIN_EXTERNAL_ANCHOR=true` + `BLOCKCHAIN_ANCHOR_REQUIRED=true` mean a forensic report is committed to the local PoW ledger **only after** the on-chain anchor succeeded. If the Fabric network / gateway is unreachable, `anchor_report` raises `BlockAnchorError`, the report endpoints return 503 ("not blockchain-anchored"), the block is NOT inserted, and `verify_report` reports the call as not anchored. No unanchored evidence can be handed off as forensic. The `DemoAnchor` shadow and 'pending'/retryable degrade are available **only** when the operator explicitly disables both flags for offline dev/demo (`BLOCKCHAIN_EXTERNAL_ANCHOR=false` + `BLOCKCHAIN_ANCHOR_REQUIRED=false`); even then the demo status is reported truthfully (`demo`, never `anchored`). Production I4C / judiciary hand-off runs with the mandatory posture on.
- **Deploy** (free tier): see [`deploy/nbf-fabric/`](deploy/nbf-fabric/) — `docker compose up -d` on Oracle Cloud **ARM A1 free tier** (IPFS + Fabric 2.2 peer/orderer (cryptogen identities, no CA) + trimmed `nbf-samplerest` gateway + `voiceshield-report.go` chaincode) or **WSL2 Ubuntu** on a laptop. Zero cloud spend either way.
- **Ministry alignment**: MeitY's National Blockchain Framework (Vishvasya, CDAC/MeitY) is the same substrate NBF-Lite kits teach; anchors at NIC DCs (Bhubaneswar/Pune/Hyderabad) have already authenticated 34 Cr+ documents, and the same framework is being used for telecom blockchain (SMS/Spam enforcement across 1.13 L entities with RBI/SEBI/NIC/C-DAC).
- **Live-verified**: anchored end-to-end on 2026-09-19 (Fabric `AnchorReport` `tx-id tx-test-1`, IPFS CID `QmZimdoSUNhXCrt…48kBa`, `GET /api/blockchain/onchain/e2e-NBF-LIVE-01` → `verified:true`, chain `VoiceShieldAIV1` height 14, 78 tests passing) — see [`docs/nbf-live-demo.md`](docs/nbf-live-demo.md).

---

## 📜 License

The VoiceShield AI code is **MIT**. Third-party components used and their licenses are documented in [`backend/SOURCES_AND_TECHNOLOGY.md`](backend/SOURCES_AND_TECHNOLOGY.md).

## 🙏 Acknowledgments

- AASIST: Jung et al., *Audio Anti-Spoofing using Integrated Spectro-Temporal Graph Attention Networks* (ICASSP 2022)
- Dhwani: Ayush2635, *Multilingual Deepfake Audio Detection* (Wav2Vec2 XLS-R + AASIST)
- FLEURS: Google, CC-BY-4.0
- Indian Cyber Crime Coordination Centre (I4C) forensic reporting standards
- **Dept. of Telecommunications — Sanchar Saathi / Chakshu / Digital Intelligence Platform (DIP)**: downstream "suspected fraud" escalation reference (citizen-facing; we integrate via our own documented webhook, no public API)
- **RBI Sachet** (`https://sachet.rbi.org.in`): reporting of suspected unauthorised financial entities, referenced in the forensic PDF
- **IndiaAI Mission (MeitY)**: compute/dataset-grant program for public-interest AI — referenced as a training-capacity pathway (no API)