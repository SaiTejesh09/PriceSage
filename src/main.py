from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from amazonscraper import AmazonScraper
from auth import authenticate_user, ensure_smtp_settings, prompt_yes_no
from config_loader import load_config
from models import AppConfig, EmailConfig, PriceChange, ProductConfig, UserAccount
from notifier import EmailNotifier
from storage import PriceStorage
from tracker import PriceTracker

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo  # type: ignore


LOGGER = logging.getLogger(__name__)


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PriceSage - Amazon price tracker",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.json"),
        help="Path to configuration file (default: config.json)",
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run a single scraping cycle and exit.",
    )
    parser.add_argument(
        "--report-minutes",
        type=int,
        default=0,
        help="Show price changes recorded within the last N minutes and exit (requires login).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO).",
    )
    return parser.parse_args(argv)


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )


def resolve_database_path(config_path: Path, app_config: AppConfig) -> Path:
    db_path = Path(app_config.storage.database_path)
    if not db_path.is_absolute():
        db_path = (config_path.parent / db_path).resolve()
    return db_path


def ensure_products(storage: PriceStorage, user: UserAccount) -> List[ProductConfig]:
    products = storage.list_products(user.id)
    if not products:
        print("\nNo products tracked yet. Let's add at least one Amazon product URL.")
        _prompt_add_products(storage, user)
        products = storage.list_products(user.id)
    else:
        print(f"\nCurrently tracking {len(products)} product(s).")
        if prompt_yes_no("Do you want to add more products?", default=False):
            _prompt_add_products(storage, user)
            products = storage.list_products(user.id)
    if not products:
        raise RuntimeError("At least one product is required to start tracking.")
    return products


def _prompt_add_products(storage: PriceStorage, user: UserAccount) -> None:
    while True:
        name = input("Product nickname (leave blank to finish): ").strip()
        if not name:
            break
        url = input("Amazon product URL: ").strip()
        if not url:
            print("URL is required. Try again.")
            continue
        target_raw = input("Target price (optional): ").strip()
        target_price: Optional[float] = None
        if target_raw:
            try:
                target_price = float(target_raw)
            except ValueError:
                print("Could not parse target price; storing without it.")
        alert_on_increase = prompt_yes_no("Alert when price increases?", default=True)
        alert_on_decrease = prompt_yes_no("Alert when price decreases?", default=True)

        product = storage.add_product(
            user_id=user.id,
            name=name,
            url=url,
            target_price=target_price,
            alert_on_increase=alert_on_increase,
            alert_on_decrease=alert_on_decrease,
        )
        print(f"Saved product '{product.name}' ({product.url}).")


def build_runtime_config(
    base_config: AppConfig,
    user: UserAccount,
    products: List[ProductConfig],
) -> AppConfig:
    email_cfg = EmailConfig(
        enabled=True,
        smtp_server=user.smtp_server,
        smtp_port=user.smtp_port,
        username=user.smtp_username,
        password=user.smtp_password,
        from_address=user.smtp_username or user.notify_email,
        to_addresses=[user.notify_email],
        use_tls=user.smtp_use_tls,
    )
    base_config.products = products
    base_config.email = email_cfg
    base_config.user = user
    return base_config


def build_tracker(
    config: AppConfig,
    storage: PriceStorage,
) -> PriceTracker:
    if config.user is None:
        raise ValueError("User information missing from configuration.")
    scraper = AmazonScraper()
    notifier = EmailNotifier(config.email)
    return PriceTracker(config.user, config, scraper, storage, notifier)


def print_report(storage: PriceStorage, minutes: int, user: UserAccount) -> None:
    changes = list(storage.changes_since(minutes, user_id=user.id))
    if not changes:
        print("No price changes recorded in the selected window.")
        return
    for change in changes:
        print(format_change(change))


def format_change(change: PriceChange) -> str:
    direction = "DOWN" if change.change and change.change < 0 else "UP"
    price_old = (
        f"{change.currency} {change.old_price:,.2f}"
        if change.currency and change.old_price is not None
        else f"{change.old_price:,.2f}" if change.old_price is not None else "unknown"
    )
    price_new = (
        f"{change.currency} {change.new_price:,.2f}"
        if change.currency and change.new_price is not None
        else f"{change.new_price:,.2f}" if change.new_price is not None else "unknown"
    )
    return (
        f"[{change.fetched_at.isoformat(sep=' ')}] {change.product_name} {direction} "
        f"{price_old} -> {price_new} ({change.product_url})"
    )


def schedule_jobs(app_config: AppConfig, tracker: PriceTracker) -> None:
    scheduler = BlockingScheduler(timezone=ZoneInfo(app_config.scheduler.timezone))

    def job_wrapper() -> None:
        LOGGER.info("Starting scheduled scrape at %s", datetime.utcnow().isoformat())
        tracker.run_once()

    times = app_config.scheduler.times
    if times:
        for item in times:
            hour, minute = _parse_time(item)
            LOGGER.info("Scheduling scrape at %02d:%02d", hour, minute)
            scheduler.add_job(
                job_wrapper,
                trigger=CronTrigger(hour=hour, minute=minute),
                max_instances=1,
            )
    else:
        interval_minutes = max(
            1, int(24 * 60 / max(1, app_config.scheduler.runs_per_day))
        )
        LOGGER.info(
            "Scheduling scrape every %d minutes (~%d runs/day)",
            interval_minutes,
            int(24 * 60 / interval_minutes),
        )
        scheduler.add_job(
            job_wrapper,
            trigger=IntervalTrigger(minutes=interval_minutes),
            max_instances=1,
        )

    if app_config.scheduler.immediate_run:
        LOGGER.info("Immediate run requested; executing once before scheduler starts.")
        tracker.run_once()

    try:
        LOGGER.info("Starting scheduler. Press Ctrl+C to exit.")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        LOGGER.info("Scheduler stopped by user.")


def _parse_time(value: str) -> tuple[int, int]:
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format: {value!r}")
    hour = int(parts[0])
    minute = int(parts[1])
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise ValueError(f"Invalid time: {value!r}")
    return hour, minute


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(list(argv) if argv is not None else sys.argv[1:])
    setup_logging(args.log_level)

    config_path = args.config.resolve()
    try:
        base_config = load_config(config_path)
    except Exception as exc:
        LOGGER.error("Failed to load configuration: %s", exc)
        return 1

    storage = PriceStorage(resolve_database_path(config_path, base_config))
    try:
        user = authenticate_user(storage)
        user = ensure_smtp_settings(storage, user)
        products = ensure_products(storage, user)
        runtime_config = build_runtime_config(base_config, user, products)

        tracker = build_tracker(runtime_config, storage)

        if args.report_minutes:
            print_report(storage, args.report_minutes, user)
            return 0

        if args.run_once:
            tracker.run_once()
            return 0

        schedule_jobs(runtime_config, tracker)
        return 0
    finally:
        storage.close()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
