from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

from models import EmailConfig, PriceChange


class EmailNotifier:
    def __init__(self, config: EmailConfig):
        self.config = config

    def _resolve_sender(self) -> str:
        if self.config.from_address:
            return self.config.from_address
        if self.config.username:
            return self.config.username
        return "price-tracker@example.com"

    def _format_price(self, value: Optional[float], currency: Optional[str]) -> str:
        if value is None:
            return "unknown"
        if currency:
            return f"{currency} {value:,.2f}"
        return f"{value:,.2f}"

    def _format_change(self, change: PriceChange) -> str:
        direction = "DOWN" if change.change and change.change < 0 else "UP"
        return (
            f"{direction}: "
            f"{self._format_price(change.old_price, change.currency)} -> "
            f"{self._format_price(change.new_price, change.currency)}"
        )

    def send_price_change(self, change: PriceChange) -> None:
        if not self.config.enabled or not self.config.to_addresses:
            return

        password = self.config.password or os.getenv(self.config.password_env_var)
        if self.config.username and not password:
            raise RuntimeError(
                "Missing SMTP password. Provide it during setup or via the "
                f"{self.config.password_env_var} environment variable."
            )

        msg = EmailMessage()
        msg["Subject"] = (
            f"Price update for {change.product_name}: "
            f"{self._format_price(change.new_price, change.currency)}"
        )
        msg["From"] = self._resolve_sender()
        msg["To"] = ", ".join(self.config.to_addresses)

        body = [
            f"Product: {change.product_name}",
            f"URL: {change.product_url}",
            f"Fetched at: {change.fetched_at.isoformat(sep=' ')} UTC",
            "",
            self._format_change(change),
        ]
        msg.set_content("\n".join(body))

        context = ssl.create_default_context()
        with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port, timeout=30) as server:
            if self.config.use_tls:
                server.starttls(context=context)
            if self.config.username:
                server.login(self.config.username, password or "")
            server.send_message(msg)
