"""
VoiceShield AI — Application Configuration
Pydantic Settings loaded from environment variables / .env file.
All external services are 100% free or free-tier for .edu.in students.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Central configuration for the VoiceShield AI platform."""

    # ── Model ──────────────────────────────────────────────────────────
    onnx_model_path: str = "models/aasist_l.onnx"
    onnx_threads: int = 2

    @property
    def onnx_model_resolved(self) -> str:
        """Resolve relative model paths against the backend root, so the app
        works regardless of the current working directory."""
        import os
        path = self.onnx_model_path
        if not path or os.path.isabs(path):
            return path
        backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.normpath(os.path.join(backend_root, path))

    # ── Detection Thresholds ───────────────────────────────────────────
    adult_threshold: float = 0.85
    child_threshold: float = 0.70

    # ── Audio Pipeline ─────────────────────────────────────────────────
    sample_rate: int = 16000
    window_samples: int = 4800       # 300 ms @ 16 kHz
    hop_samples: int = 1600          # 100 ms hop → 66% overlap
    latency_budget_ms: float = 78.0  # Max per-window latency
    silence_rms_threshold: float = 0.012  # window RMS below this = no speech → bonafide
    min_speech_fraction: float = 0.25     # min share of 100 ms frames w/ speech → else bonafide

    # ── Watermark ──────────────────────────────────────────────────────
    watermark_fft_size: int = 4096
    watermark_band_low: float = 7000.0   # Hz
    watermark_band_high: float = 7500.0  # Hz
    watermark_snr_threshold: float = 12.0  # × noise floor

    # ── Alerts — Telegram (free forever) ───────────────────────────────
    telegram_bot_token: str = ""     # From @BotFather
    telegram_chat_id: str = ""       # Your chat/group ID

    # ── Alerts — Email SMTP (free via Gmail / .edu.in Google Workspace)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""              # your.name@college.edu.in
    smtp_password: str = ""          # Gmail App Password
    alert_email_to: str = ""         # Recipient address

    # ── Alerts — ntfy.sh (free, open-source, no signup) ────────────────
    # Opt-in: set a unique topic to enable push notifications. Default empty
    # so no traffic is sent to shared topics until configured.
    ntfy_topic: str = ""
    ntfy_server: str = "https://ntfy.sh"

    # ── Alerts — Fast2SMS (free tier, Indian SMS gateway, optional) ────
    fast2sms_api_key: str = ""
    fast2sms_to_number: str = ""     # Indian mobile number

    # ── Alerts — Webhook (free, self-hosted) ───────────────────────────
    webhook_url: str = ""

    # ── Escalation — DoT Sanchar Saathi / Chakshu / DIP (suspected fraud) ──
    # Optional downstream hand-off point. When set, an alert that crosses the
    # detection threshold is ALSO posted here as "suspected fraud" metadata so
    # an operator/telecom can route it to the Digital Intelligence Platform
    # (DIP) for network-level action. This complements (not replaces) the
    # post-fraud I4C/1930 flow already embedded in the forensic PDF.
    # NOTE: Chakshu/DIP are citizen-facing DoT portals (no public API); this
    # is a documented integration point on YOUR side that feeds them.
    chakshu_dip_webhook_url: str = ""

    # ── Blockchain Ledger ──────────────────────────────────────────────
    # The report ledger is a local proof-of-work hash chain — NO external
    # API key is required to run it. The fields below are OPTIONAL anchors
    # if you later want to pin a block hash to a public chain (e.g. for the
    # I4C / judiciary hand-off path).
    blockchain_difficulty: int = 4   # PoW leading-zero requirement
    blockchain_rpc_url: str = ""     # optional public-chain RPC anchor
    blockchain_explorer_api_key: str = ""  # optional explorer API key
    blockchain_anchor_address: str = ""    # optional on-chain anchor addr
    # NBF-Lite / MeitY National Blockchain Framework external anchor (optional).
    # When blockchain_external_anchor=True, every locally-minied report block is
    # additionally committed to a Hyperledger Fabric ledger (via a REST gateway)
    # and its encrypted PDF pushed to IPFS. Fail-open: if the gateway is
    # unreachable the local PoW chain remains authoritative and the anchor is
    # marked 'pending' (retryable).
    blockchain_external_anchor: bool = False
    nbf_gateway_url: str = ""          # e.g. http://<fabric-gateway-host>:4000
    nbf_channel: str = "mychannel"
    nbf_cc: str = "voiceshield-report"
    nbf_user: str = "User1"
    nbf_msp: str = "Org1MSP"
    nbf_cfgpath: str = ""
    # How /retrieve payloads are decoded to the anchor ciphertext. NBFLite's
    # sample gateway pins the base64 *text* under the CID while our trimmed
    # gateway pins the decoded raw bytes (different CID, different fetch shape).
    #   auto        -> self-detect per fetch (raw first, then base64-text)
    #   raw         -> our gateway (decoded bytes; body data is the cipher b64)
    #   base64text  -> NBFLite sample gateway (body data is base64 of the text)
    nbf_ipfs_mode: str = "auto"
    ipfs_store_url: str = ""           # defaults to {gateway}/store
    report_keys_dir: str = ""          # org-custody key manifests / master key

    # ── Server ─────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = ["http://localhost:5173"]

    # ── Fusion Weights ─────────────────────────────────────────────────
    fusion_model_weight: float = 0.7
    fusion_xai_weight: float = 0.3

    # ── Contextual Enrichment (opt-in, SIH26104 "contextual enrichment") ──
    # Adds conservative, transparent modifiers (caller origin, known-contact,
    # transaction value, historical fraud flags) on top of the acoustic score.
    # Default OFF so detection behavior is unchanged without config; fail-open:
    # no context supplied -> acoustic score untouched.
    contextual_enrichment: bool = False
    context_unknown_origin_penalty: float = 0.05
    context_unknown_contact_penalty: float = 0.05
    context_known_contact_boost: float = 0.05
    context_high_value_penalty: float = 0.05
    context_high_value_threshold: float = 100000.0   # INR
    context_prior_flag_penalty: float = 0.03         # per flag, capped at 3

    # ── Configurable Mitigation Workflows ─────────────────────────────
    # JSON rules file mapping role+risk-band to automated actions/channels.
    # Banks/enterprises/gov can edit it without a code deploy.
    workflows_path: str = "workflows.json"

    # ── Database & External Services ───────────────────────────────────
    database_url: str = ""
    resend_api_key: str = ""
    sentry_dsn: str = ""

    hf_token: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Singleton instance
settings = Settings()
