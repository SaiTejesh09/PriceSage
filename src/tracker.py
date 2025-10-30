from __future__ import annotations

import logging
from typing import List, Optional

from amazonscraper import AmazonScraper
from models import AppConfig, PriceChange, ProductConfig, ScrapeResult, UserAccount
from notifier import EmailNotifier
from storage import PriceStorage

LOGGER = logging.getLogger(__name__)


class PriceTracker:
    def __init__(
        self,
        user: UserAccount,
        config: AppConfig,
        scraper: AmazonScraper,
        storage: PriceStorage,
        notifier: EmailNotifier,
    ) -> None:
        self.user = user
        self.config = config
        self.scraper = scraper
        self.storage = storage
        self.notifier = notifier

    def run_once(self) -> List[ScrapeResult]:
        results: List[ScrapeResult] = []
        products = self.storage.list_products(self.user.id)
        if not products:
            LOGGER.warning("No products configured for user %s.", self.user.email)
            return results

        self.config.products = products
        for product in products:
            try:
                result = self.scraper.fetch_product(product.name, product.url)
                results.append(result)
            except Exception as exc:
                LOGGER.exception("Failed to fetch %s: %s", product.name, exc)
                continue

            change = self.storage.record_scrape(product, result)
            if change and self._should_notify(product, change):
                LOGGER.info(
                    "Price change detected for %s: %s",
                    product.name,
                    self._format_change(change),
                )
                try:
                    self.notifier.send_price_change(change)
                except Exception as exc:
                    LOGGER.exception("Failed to send alert for %s: %s", product.name, exc)

        return results

    def _should_notify(self, product: ProductConfig, change: PriceChange) -> bool:
        if change.change is None:
            return False

        if change.change > 0 and not product.alert_on_increase:
            return False
        if change.change < 0 and not product.alert_on_decrease:
            return False

        cfg = self.config.notifications
        if cfg.only_price_drop and change.change > 0:
            return False

        if (
            cfg.price_change_threshold > 0
            and abs(change.change) < cfg.price_change_threshold
        ):
            return False

        return True

    def _format_change(self, change: PriceChange) -> str:
        direction = "DOWN" if change.change < 0 else "UP"
        return (
            f"{direction}: {self._format_price(change.old_price, change.currency)} -> "
            f"{self._format_price(change.new_price, change.currency)}"
        )

    def _format_price(self, value: Optional[float], currency: Optional[str]) -> str:
        if value is None:
            return "unknown"
        if currency:
            return f"{currency} {value:,.2f}"
        return f"{value:,.2f}"
