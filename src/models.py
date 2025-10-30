from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass(slots=True)
class ProductConfig:
    id: Optional[int]
    user_id: Optional[int]
    name: str
    url: str
    target_price: Optional[float] = None
    alert_on_increase: bool = True
    alert_on_decrease: bool = True


@dataclass(slots=True)
class EmailConfig:
    enabled: bool = False
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    username: str = ""
    password: Optional[str] = None
    password_env_var: str = "PRICE_SAGE_SMTP_PASSWORD"
    from_address: Optional[str] = None
    to_addresses: List[str] = field(default_factory=list)
    use_tls: bool = True


@dataclass(slots=True)
class SchedulerConfig:
    runs_per_day: int = 6
    times: List[str] = field(default_factory=list)
    timezone: str = "UTC"
    immediate_run: bool = True


@dataclass(slots=True)
class NotificationConfig:
    price_change_threshold: float = 0.0
    only_price_drop: bool = False


@dataclass(slots=True)
class StorageConfig:
    database_path: str = "data/prices.db"


@dataclass(slots=True)
class ScrapeResult:
    product_name: str
    product_url: str
    price: Optional[float]
    currency: Optional[str]
    title: Optional[str]
    availability: Optional[str]
    fetched_at: datetime
    raw_price: Optional[str] = None


@dataclass(slots=True)
class PriceRecord:
    id: int
    product_name: str
    product_url: str
    price: Optional[float]
    currency: Optional[str]
    fetched_at: datetime
    availability: Optional[str] = None


@dataclass(slots=True)
class PriceChange:
    product_name: str
    product_url: str
    old_price: Optional[float]
    new_price: Optional[float]
    change: Optional[float]
    currency: Optional[str]
    fetched_at: datetime


@dataclass(slots=True)
class AppConfig:
    email: EmailConfig
    scheduler: SchedulerConfig
    notifications: NotificationConfig
    storage: StorageConfig
    products: List[ProductConfig] = field(default_factory=list)
    user: Optional["UserAccount"] = None


@dataclass(slots=True)
class UserAccount:
    id: int
    email: str
    notify_email: str
    smtp_server: str
    smtp_port: int
    smtp_username: str
    smtp_password: Optional[str]
    smtp_use_tls: bool = True
