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
    ntfy_topic: str = "voiceshield-alerts"
    ntfy_server: str = "https://ntfy.sh"

    # ── Alerts — Fast2SMS (free tier, Indian SMS gateway, optional) ────
    fast2sms_api_key: str = ""
    fast2sms_to_number: str = ""     # Indian mobile number

    # ── Alerts — Webhook (free, self-hosted) ───────────────────────────
    webhook_url: str = ""

    # ── Server ─────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = ["http://localhost:5173"]

    # ── Fusion Weights ─────────────────────────────────────────────────
    fusion_model_weight: float = 0.7
    fusion_xai_weight: float = 0.3

    # ── Database & External Services ───────────────────────────────────
    database_url: str = ""
    resend_api_key: str = ""
    sentry_dsn: str = ""

    hf_token: str = ""

    blockchain_difficulty: int = 4   # PoW leading-zero requirement for report anchors

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Singleton instance
settings = Settings()
