# backend/app/services/mailer.py
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional
from ..config import get_settings


class Mailer:
    def __init__(self):
        s = get_settings()
        # read SMTP settings from .env / env vars
        self.smtp_host = s.smtp_host
        self.smtp_port = int(s.smtp_port)
        self.smtp_user = s.smtp_user
        self.smtp_pass = s.smtp_pass
        self.smtp_from = s.smtp_from
        self.default_to = s.smtp_to
        self.use_ssl = bool(s.smtp_use_ssl)   # e.g. port 465
        self.use_tls = bool(s.smtp_use_tls)   # e.g. port 587

    def _send(self, msg: EmailMessage):
        if self.use_ssl:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=ctx) as s:
                if self.smtp_user:
                    s.login(self.smtp_user, self.smtp_pass)
                s.send_message(msg)
        else:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as s:
                if self.use_tls:
                    s.starttls(context=ssl.create_default_context())
                if self.smtp_user:
                    s.login(self.smtp_user, self.smtp_pass)
                s.send_message(msg)

    def send_plain(self, to_addr: Optional[str], subject: str, text: str):
        """Generic plain-text email (used by /debug/email)."""
        to_addr = to_addr or self.default_to
        if not to_addr:
            raise ValueError("No recipient: set SMTP_TO in env or pass 'to'")

        msg = EmailMessage()
        msg["From"] = self.smtp_from
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg.set_content(text)

        self._send(msg)

    def send_alert_created(
            self,
            device_id: str,
            device_name: str,
            power_w: float,
            threshold_w: float,
            duration_s: int,
            alert_id: int,
            to_addr: Optional[str] = None,
    ):
        """Nice wrapper for alert emails."""
        subject = f"[SPO] Idle alert #{alert_id} on {device_name or device_id}"
        body = (
            f"An idle alert was created.\n\n"
            f"Device: {device_name or device_id}\n"
            f"Device ID: {device_id}\n"
            f"Power now: {power_w:.2f} W\n"
            f"Threshold: {threshold_w:.2f} W\n"
            f"Duration: {duration_s} s\n"
            f"Alert ID: {alert_id}\n"
        )
        self.send_plain(to_addr, subject, body)
