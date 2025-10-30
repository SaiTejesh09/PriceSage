from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from models import ScrapeResult

LOGGER = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.amazon.in/",
}

PRICE_PATTERNS = [
    {"id": "priceblock_dealprice"},
    {"id": "priceblock_saleprice"},
    {"id": "priceblock_ourprice"},
    {"css": "span.a-price span.a-offscreen"},
    {"css": "span.a-price-whole"},
]

CURRENCY_MAP = {
    "₹": "INR",
    "Rs": "INR",
    "$": "USD",
    "£": "GBP",
    "€": "EUR",
}

PRICE_REGEX = re.compile(r"(\d[\d,.]*)")


class AmazonScraper:
    def __init__(
        self,
        headers: Optional[dict] = None,
        connect_timeout: float = 10.0,
        read_timeout: float = 30.0,
    ) -> None:
        self.session = self._build_session(headers or DEFAULT_HEADERS)
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout

    def _build_session(self, headers: dict) -> requests.Session:
        session = requests.Session()
        session.headers.update(headers)
        retry = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["GET", "HEAD"]),
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def fetch_product(self, name: str, url: str) -> ScrapeResult:
        LOGGER.info("Fetching %s", name)
        try:
            response = self.session.get(
                url, timeout=(self._connect_timeout, self._read_timeout)
            )
        except Exception as exc:
            raise RuntimeError(f"Request failed for {name}: {exc}") from exc

        if response.status_code != 200:
            raise RuntimeError(
                f"Unexpected status {response.status_code} for {name}: {url}"
            )

        soup = BeautifulSoup(response.content, "html.parser")
        title = self._extract_title(soup)
        availability = self._extract_availability(soup)
        price_text = self._extract_price_text(soup)
        price = self._parse_price(price_text)
        currency = self._detect_currency(price_text, soup)

        return ScrapeResult(
            product_name=name,
            product_url=url,
            price=price,
            currency=currency,
            title=title,
            availability=availability,
            fetched_at=datetime.utcnow(),
            raw_price=price_text,
        )

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        node = soup.select_one("#productTitle")
        if node:
            return node.get_text(strip=True)
        node = soup.select_one("span#title")
        return node.get_text(strip=True) if node else None

    def _extract_price_text(self, soup: BeautifulSoup) -> Optional[str]:
        for pattern in PRICE_PATTERNS:
            if "id" in pattern:
                node = soup.find(id=pattern["id"])
            else:
                node = soup.select_one(pattern["css"])
            if node and node.get_text(strip=True):
                return node.get_text(strip=True)
        return None

    def _parse_price(self, price_text: Optional[str]) -> Optional[float]:
        if not price_text:
            return None
        cleaned = price_text.replace("\xa0", " ")
        match = PRICE_REGEX.search(cleaned)
        if not match:
            return None
        candidate = match.group(1).replace(",", "")
        try:
            return float(candidate)
        except ValueError:
            LOGGER.debug("Unable to convert price '%s'", candidate)
            return None

    def _detect_currency(
        self, price_text: Optional[str], soup: BeautifulSoup
    ) -> Optional[str]:
        if price_text:
            for symbol, code in CURRENCY_MAP.items():
                if symbol in price_text:
                    return code
        symbol_node = soup.select_one("span.a-price-symbol")
        if symbol_node:
            symbol = symbol_node.get_text(strip=True)
            for key, code in CURRENCY_MAP.items():
                if key in symbol:
                    return code
        return None

    def _extract_availability(self, soup: BeautifulSoup) -> Optional[str]:
        node = soup.select_one("#availability span")
        if node and node.get_text(strip=True):
            return node.get_text(strip=True)
        return None
