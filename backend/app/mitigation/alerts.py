"""
VoiceShield AI — Async Multi-Channel Alert Dispatcher
All alert channels are 100% FREE — no paid services.

Channels:
    1. Telegram Bot API (free forever)
    2. Gmail SMTP via aiosmtplib (free for .edu.in students)
    3. ntfy.sh push notifications (free, open-source, no signup)
    4. Fast2SMS (free tier for Indian numbers, optional)
    5. Webhook (free, self-hosted)
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAYS = [1.0, 2.0, 4.0]  # Exponential backoff


async def dispatch_alerts(
    call_id: str,
    score: float,
    role: str,
    action_type: str,
) -> None:
    """
    Dispatch alerts to all configured channels concurrently.
    Non-blocking — called via asyncio.create_task() from the mitigation router.
    Failures are logged but never raised.

    Args:
        call_id: Call session identifier.
        score: Fused synthetic score.
        role: Session role ('adult' or 'child').
        action_type: Mitigation action type ('child_shield' or 'adult_alert').
    """
    timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    priority = "urgent" if role == "child" else "high"

    message = (
        f"🛡️ VoiceShield AI Alert\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Call ID: {call_id}\n"
        f"Score: {score:.4f}\n"
        f"Role: {role.upper()}\n"
        f"Action: {action_type}\n"
        f"Time: {timestamp}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    # Fire all configured channels concurrently
    tasks = []

    if settings.telegram_bot_token:
        tasks.append(send_telegram(
            settings.telegram_bot_token,
            settings.telegram_chat_id,
            message,
        ))

    if settings.smtp_user:
        tasks.append(send_email(
            subject=f"🛡️ VoiceShield Alert — {action_type.upper()} — Score {score:.2f}",
            body=_format_email_html(call_id, score, role, action_type, timestamp),
        ))

    if settings.ntfy_topic:
        tasks.append(send_ntfy(
            settings.ntfy_server,
            settings.ntfy_topic,
            message,
            priority=priority,
        ))

    if settings.fast2sms_api_key:
        sms_msg = f"VoiceShield Alert: {action_type} | Score: {score:.2f} | Call: {call_id}"
        tasks.append(send_fast2sms(
            settings.fast2sms_api_key,
            settings.fast2sms_to_number,
            sms_msg,
        ))

    if settings.webhook_url:
        tasks.append(send_webhook(
            settings.webhook_url,
            {
                "call_id": call_id,
                "score": score,
                "role": role,
                "action": action_type,
                "timestamp": timestamp,
            },
        ))

    # ── DoT Sanchar Saathi / Chakshu / DIP escalation (suspected fraud) ───
    # Optional downstream hand-off: posts flagged-call metadata to an
    # operator-side receiver that routes it into Chakshu / the Digital
    # Intelligence Platform (DIP) for network-level action. Distinct from the
    # post-fraud I4C/1930 flow embedded in the forensic PDF. Skipped unless
    # CHAKSHU_DIP_WEBHOOK_URL is configured.
    if settings.chakshu_dip_webhook_url:
        tasks.append(send_webhook(
            settings.chakshu_dip_webhook_url,
            {
                "channel": "chakshu_dip",
                "flow": "suspected_fraud",
                "call_id": call_id,
                "score": score,
                "role": role,
                "action": action_type,
                "timestamp": timestamp,
                "escalation": "Route flagged-call metadata to DoT DIP / Chakshu "
                              "(Sanchar Saathi) for network-level action.",
            },
        ))

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Alert channel {i} failed: {result}")
    else:
        logger.debug("No alert channels configured — skipping dispatch")


# ── Telegram Bot API (FREE FOREVER) ──────────────────────────────────────

async def send_telegram(bot_token: str, chat_id: str, message: str) -> None:
    """Send alert via Telegram Bot API. Free, no rate limits for small bots."""
    if not bot_token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
    }

    await _send_with_retry("Telegram", url, json_payload=payload)


# ── Email via Gmail SMTP (FREE for .edu.in students) ─────────────────────

async def send_email(subject: str, body: str) -> None:
    """Send alert email via Gmail SMTP using aiosmtplib. Free with App Password."""
    if not settings.smtp_user or not settings.alert_email_to:
        return

    try:
        import aiosmtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart("alternative")
        msg["From"] = settings.smtp_user
        msg["To"] = settings.alert_email_to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        for attempt in range(MAX_RETRIES):
            try:
                await aiosmtplib.send(
                    msg,
                    hostname=settings.smtp_host,
                    port=settings.smtp_port,
                    start_tls=True,
                    username=settings.smtp_user,
                    password=settings.smtp_password,
                )
                logger.info(f"Email alert sent to {settings.alert_email_to}")
                return
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                else:
                    logger.error(f"Email alert failed after {MAX_RETRIES} retries: {e}")

    except ImportError:
        logger.warning("aiosmtplib not installed — skipping email alert")


# ── ntfy.sh Push Notifications (FREE, NO SIGNUP) ─────────────────────────

async def send_ntfy(
    server: str, topic: str, message: str, priority: str = "high"
) -> None:
    """
    Send push notification via ntfy.sh. Completely free, no signup.
    Install the ntfy app on your phone to receive instant notifications.
    """
    if not topic:
        return

    url = f"{server}/{topic}"
    headers = {
        "Title": "VoiceShield AI Alert",
        "Priority": priority,
        "Tags": "shield,warning",
    }

    await _send_with_retry("ntfy.sh", url, data=message, headers=headers)


# ── Fast2SMS (FREE TIER — Indian SMS Gateway) ────────────────────────────

async def send_fast2sms(api_key: str, to_number: str, message: str) -> None:
    """
    Send SMS via Fast2SMS. Free tier with credits on signup.
    Indian mobile numbers only.
    """
    if not api_key or not to_number:
        return

    url = "https://www.fast2sms.com/dev/bulkV2"
    headers = {"authorization": api_key}
    payload = {
        "route": "q",
        "message": message,
        "flash": 0,
        "numbers": to_number,
    }

    await _send_with_retry("Fast2SMS", url, json_payload=payload, headers=headers)


# ── Webhook (FREE — any endpoint you control) ────────────────────────────

async def send_webhook(url: str, payload: dict) -> None:
    """Send alert to a configurable webhook endpoint."""
    if not url:
        return

    await _send_with_retry("Webhook", url, json_payload=payload)


# ── Retry Helper ──────────────────────────────────────────────────────────

async def _send_with_retry(
    channel: str,
    url: str,
    json_payload: dict = None,
    data: str = None,
    headers: dict = None,
) -> None:
    """
    Send HTTP request with exponential backoff retry.
    Never raises — logs errors and returns silently.
    """
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if json_payload:
                    resp = await client.post(url, json=json_payload, headers=headers)
                elif data:
                    resp = await client.post(url, content=data, headers=headers)
                else:
                    resp = await client.post(url, headers=headers)

                if resp.status_code < 400:
                    logger.info(f"{channel} alert sent successfully (HTTP {resp.status_code})")
                    return
                else:
                    logger.warning(f"{channel} returned HTTP {resp.status_code}: {resp.text[:200]}")

        except Exception as e:
            logger.warning(f"{channel} attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")

        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(RETRY_DELAYS[attempt])

    logger.error(f"{channel} alert failed after {MAX_RETRIES} retries")


# ── Email HTML Template ──────────────────────────────────────────────────

def _format_email_html(
    call_id: str, score: float, role: str, action: str, timestamp: str
) -> str:
    """Generate a styled HTML email body for alerts."""
    color = "#ff3366" if role == "child" else "#ffaa00"
    return f"""
    <html>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; background: #0a0e27; color: #fff; padding: 20px;">
        <div style="max-width: 500px; margin: 0 auto; background: rgba(255,255,255,0.05); border: 1px solid {color}; border-radius: 12px; padding: 24px;">
            <h2 style="color: {color}; margin: 0 0 16px;">🛡️ VoiceShield AI Alert</h2>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px; color: #888;">Call ID</td><td style="padding: 8px; color: #fff; font-weight: bold;">{call_id}</td></tr>
                <tr><td style="padding: 8px; color: #888;">Score</td><td style="padding: 8px; color: {color}; font-weight: bold; font-size: 18px;">{score:.4f}</td></tr>
                <tr><td style="padding: 8px; color: #888;">Role</td><td style="padding: 8px; color: #fff;">{role.upper()}</td></tr>
                <tr><td style="padding: 8px; color: #888;">Action</td><td style="padding: 8px; color: #fff;">{action}</td></tr>
                <tr><td style="padding: 8px; color: #888;">Time (IST)</td><td style="padding: 8px; color: #fff;">{timestamp}</td></tr>
            </table>
            <hr style="border-color: rgba(255,255,255,0.1); margin: 16px 0;">
            <p style="color: #888; font-size: 12px;">
                If you believe this is a deepfake attack, file a complaint at
                <a href="https://cybercrime.gov.in" style="color: #00d4ff;">cybercrime.gov.in</a>
                or call the I4C Helpline: <strong>1930</strong>
            </p>
        </div>
    </body>
    </html>
    """
