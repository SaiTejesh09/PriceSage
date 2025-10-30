from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from models import AppConfig, EmailConfig, NotificationConfig, ProductConfig, SchedulerConfig, StorageConfig


def _load_products(raw_products: List[Dict[str, Any]]) -> List[ProductConfig]:
    products: List[ProductConfig] = []
    for entry in raw_products:
        if "name" not in entry or "url" not in entry:
            raise ValueError("Each product requires at least a 'name' and 'url'.")
        products.append(
            ProductConfig(
                id=entry.get("id"),
                user_id=entry.get("user_id"),
                name=entry["name"],
                url=entry["url"],
                target_price=entry.get("target_price"),
                alert_on_increase=entry.get("alert_on_increase", True),
                alert_on_decrease=entry.get("alert_on_decrease", True),
            )
        )
    return products


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    products = _load_products(raw.get("products", []))

    email_cfg = EmailConfig(
        enabled=raw.get("email", {}).get("enabled", False),
        smtp_server=raw.get("email", {}).get("smtp_server", "smtp.gmail.com"),
        smtp_port=int(raw.get("email", {}).get("smtp_port", 587)),
        username=raw.get("email", {}).get("username", ""),
        password=raw.get("email", {}).get("password"),
        password_env_var=raw.get("email", {}).get(
            "password_env_var", "PRICE_SAGE_SMTP_PASSWORD"
        ),
        from_address=raw.get("email", {}).get("from_address"),
        to_addresses=list(raw.get("email", {}).get("to_addresses", [])),
        use_tls=raw.get("email", {}).get("use_tls", True),
    )

    scheduler_cfg = SchedulerConfig(
        runs_per_day=int(raw.get("scheduler", {}).get("runs_per_day", 6)),
        times=list(raw.get("scheduler", {}).get("times", [])),
        timezone=raw.get("scheduler", {}).get("timezone", "UTC"),
        immediate_run=raw.get("scheduler", {}).get("immediate_run", True),
    )

    notifications_cfg = NotificationConfig(
        price_change_threshold=float(
            raw.get("notifications", {}).get("price_change_threshold", 0.0)
        ),
        only_price_drop=raw.get("notifications", {}).get("only_price_drop", False),
    )

    storage_cfg = StorageConfig(
        database_path=raw.get("storage", {}).get("database_path", "data/prices.db")
    )

    return AppConfig(
        products=products,
        email=email_cfg,
        scheduler=scheduler_cfg,
        notifications=notifications_cfg,
        storage=storage_cfg,
    )
