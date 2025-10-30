from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from models import PriceChange, PriceRecord, ProductConfig, ScrapeResult, UserAccount


class PriceStorage:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.db_path)
        self._connection.row_factory = sqlite3.Row
        self._init_schema()

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection

    def close(self) -> None:
        self._connection.close()

    def _init_schema(self) -> None:
        with self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    notify_email TEXT NOT NULL,
                    smtp_server TEXT NOT NULL,
                    smtp_port INTEGER NOT NULL,
                    smtp_username TEXT NOT NULL,
                    smtp_password TEXT,
                    smtp_use_tls INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    target_price REAL,
                    alert_on_increase INTEGER NOT NULL DEFAULT 1,
                    alert_on_decrease INTEGER NOT NULL DEFAULT 1,
                    last_price REAL,
                    currency TEXT,
                    last_scraped TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, url),
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY,
                    product_id INTEGER NOT NULL,
                    price REAL,
                    currency TEXT,
                    availability TEXT,
                    title TEXT,
                    raw_price TEXT,
                    scraped_at TEXT NOT NULL,
                    FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
                )
                """
            )
        self._ensure_column("products", "user_id", "INTEGER NOT NULL DEFAULT 1")
        self._ensure_column("products", "alert_on_increase", "INTEGER NOT NULL DEFAULT 1")
        self._ensure_column("products", "alert_on_decrease", "INTEGER NOT NULL DEFAULT 1")
        self._ensure_column("products", "target_price", "REAL")

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        info = self.connection.execute(f"PRAGMA table_info({table})").fetchall()
        names = {row["name"] for row in info}
        if column not in names:
            with self.connection:
                self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    # ------------------------------------------------------------------ #
    # User management

    def create_user(
        self,
        email: str,
        password_hash: str,
        notify_email: str,
        smtp_server: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: Optional[str],
        smtp_use_tls: bool,
    ) -> UserAccount:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO users (
                    email, password_hash, notify_email,
                    smtp_server, smtp_port, smtp_username,
                    smtp_password, smtp_use_tls
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    email,
                    password_hash,
                    notify_email,
                    smtp_server,
                    smtp_port,
                    smtp_username,
                    smtp_password,
                    1 if smtp_use_tls else 0,
                ),
            )
        return self.get_user_by_email(email)

    def update_user_smtp(
        self,
        user_id: int,
        notify_email: str,
        smtp_server: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: Optional[str],
        smtp_use_tls: bool,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE users
                SET notify_email = ?,
                    smtp_server = ?,
                    smtp_port = ?,
                    smtp_username = ?,
                    smtp_password = ?,
                    smtp_use_tls = ?
                WHERE id = ?
                """,
                (
                    notify_email,
                    smtp_server,
                    smtp_port,
                    smtp_username,
                    smtp_password,
                    1 if smtp_use_tls else 0,
                    user_id,
                ),
            )

    def list_users(self) -> List[UserAccount]:
        cursor = self.connection.execute("SELECT * FROM users ORDER BY created_at")
        return [self._row_to_user(row) for row in cursor.fetchall()]

    def get_user_by_email(self, email: str) -> Optional[UserAccount]:
        cursor = self.connection.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        return self._row_to_user(row) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[UserAccount]:
        cursor = self.connection.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return self._row_to_user(row) if row else None

    def get_password_hash(self, email: str) -> Optional[str]:
        cursor = self.connection.execute(
            "SELECT password_hash FROM users WHERE email = ?", (email,)
        )
        row = cursor.fetchone()
        return row["password_hash"] if row else None

    def _row_to_user(self, row: sqlite3.Row) -> UserAccount:
        return UserAccount(
            id=row["id"],
            email=row["email"],
            notify_email=row["notify_email"],
            smtp_server=row["smtp_server"],
            smtp_port=row["smtp_port"],
            smtp_username=row["smtp_username"],
            smtp_password=row["smtp_password"],
            smtp_use_tls=bool(row["smtp_use_tls"]),
        )

    # ------------------------------------------------------------------ #
    # Product management

    def add_product(
        self,
        user_id: int,
        name: str,
        url: str,
        target_price: Optional[float],
        alert_on_increase: bool,
        alert_on_decrease: bool,
    ) -> ProductConfig:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO products (
                    user_id, name, url, target_price,
                    alert_on_increase, alert_on_decrease
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, url) DO UPDATE SET
                    name = excluded.name,
                    target_price = excluded.target_price,
                    alert_on_increase = excluded.alert_on_increase,
                    alert_on_decrease = excluded.alert_on_decrease
                """,
                (
                    user_id,
                    name,
                    url,
                    target_price,
                    1 if alert_on_increase else 0,
                    1 if alert_on_decrease else 0,
                ),
            )
        return self.get_product_by_url(user_id, url)

    def get_product_by_url(self, user_id: int, url: str) -> Optional[ProductConfig]:
        cursor = self.connection.execute(
            """
            SELECT * FROM products
            WHERE user_id = ? AND url = ?
            """,
            (user_id, url),
        )
        row = cursor.fetchone()
        return self._row_to_product(row) if row else None

    def list_products(self, user_id: int) -> List[ProductConfig]:
        cursor = self.connection.execute(
            "SELECT * FROM products WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
        return [self._row_to_product(row) for row in cursor.fetchall()]

    def _row_to_product(self, row: sqlite3.Row) -> ProductConfig:
        return ProductConfig(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            url=row["url"],
            target_price=row["target_price"],
            alert_on_increase=bool(row["alert_on_increase"]),
            alert_on_decrease=bool(row["alert_on_decrease"]),
        )

    # ------------------------------------------------------------------ #
    # Price tracking

    def record_scrape(self, product: ProductConfig, result: ScrapeResult) -> Optional[PriceChange]:
        previous = self.get_latest_price(product.id)

        with self.connection:
            self.connection.execute(
                """
                INSERT INTO price_history (
                    product_id, price, currency, availability,
                    title, raw_price, scraped_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product.id,
                    result.price,
                    result.currency,
                    result.availability,
                    result.title,
                    result.raw_price,
                    result.fetched_at.isoformat(timespec="seconds"),
                ),
            )
            self.connection.execute(
                """
                UPDATE products
                SET last_price = ?,
                    currency = ?,
                    last_scraped = ?
                WHERE id = ?
                """,
                (
                    result.price,
                    result.currency,
                    result.fetched_at.isoformat(timespec="seconds"),
                    product.id,
                ),
            )

        return self._calculate_change(product, previous, result)

    def _calculate_change(
        self,
        product: ProductConfig,
        previous: Optional[PriceRecord],
        result: ScrapeResult,
    ) -> Optional[PriceChange]:
        if previous is None:
            return None
        if result.price is None or previous.price is None:
            return None
        if result.price == previous.price:
            return None

        return PriceChange(
            product_name=product.name,
            product_url=product.url,
            old_price=previous.price,
            new_price=result.price,
            change=result.price - previous.price,
            currency=result.currency or previous.currency,
            fetched_at=result.fetched_at,
        )

    def get_latest_price(self, product_id: Optional[int]) -> Optional[PriceRecord]:
        if product_id is None:
            return None
        cursor = self.connection.execute(
            """
            SELECT
                ph.id,
                ph.price,
                ph.currency,
                ph.scraped_at,
                ph.availability,
                p.name,
                p.url
            FROM price_history ph
            JOIN products p ON p.id = ph.product_id
            WHERE ph.product_id = ?
            ORDER BY ph.scraped_at DESC
            LIMIT 1
            """,
            (product_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return PriceRecord(
            id=row["id"],
            product_name=row["name"],
            product_url=row["url"],
            price=row["price"],
            currency=row["currency"],
            fetched_at=datetime.fromisoformat(row["scraped_at"]),
            availability=row["availability"],
        )

    def list_history(self, product_id: int, limit: int = 20) -> Iterable[PriceRecord]:
        cursor = self.connection.execute(
            """
            SELECT
                ph.id,
                ph.price,
                ph.currency,
                ph.scraped_at,
                ph.availability,
                p.name,
                p.url
            FROM price_history ph
            JOIN products p ON p.id = ph.product_id
            WHERE ph.product_id = ?
            ORDER BY ph.scraped_at DESC
            LIMIT ?
            """,
            (product_id, limit),
        )
        for row in cursor.fetchall():
            yield PriceRecord(
                id=row["id"],
                product_name=row["name"],
                product_url=row["url"],
                price=row["price"],
                currency=row["currency"],
                fetched_at=datetime.fromisoformat(row["scraped_at"]),
                availability=row["availability"],
            )

    def changes_since(self, minutes: int, user_id: Optional[int] = None) -> Iterable[PriceChange]:
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        params: List[object] = [cutoff.isoformat(timespec="seconds")]
        user_filter = ""
        if user_id is not None:
            user_filter = "AND p.user_id = ?"
            params.append(user_id)

        cursor = self.connection.execute(
            f"""
            WITH latest AS (
                SELECT
                    ph.id,
                    ph.product_id,
                    ph.price,
                    ph.currency,
                    ph.scraped_at,
                    LAG(ph.price) OVER (
                        PARTITION BY ph.product_id
                        ORDER BY ph.scraped_at
                    ) AS prev_price
                FROM price_history ph
            )
            SELECT
                p.name,
                p.url,
                latest.prev_price,
                latest.price,
                latest.currency,
                latest.scraped_at
            FROM latest
            JOIN products p ON p.id = latest.product_id
            WHERE latest.scraped_at >= ?
              AND latest.prev_price IS NOT NULL
              AND latest.prev_price != latest.price
              {user_filter}
            """,
            params,
        )

        for row in cursor.fetchall():
            yield PriceChange(
                product_name=row["name"],
                product_url=row["url"],
                old_price=row["prev_price"],
                new_price=row["price"],
                change=(
                    row["price"] - row["prev_price"]
                    if row["price"] is not None and row["prev_price"] is not None
                    else None
                ),
                currency=row["currency"],
                fetched_at=datetime.fromisoformat(row["scraped_at"]),
            )

    def price_summary(self) -> List[Dict[str, Optional[float]]]:
        cursor = self.connection.execute(
            """
            SELECT
                p.user_id AS user_id,
                u.email AS user_email,
                p.name AS product_name,
                p.url AS product_url,
                p.last_price AS last_price,
                p.currency AS currency,
                p.last_scraped AS last_scraped,
                MIN(ph.price) AS min_price,
                MAX(ph.price) AS max_price,
                AVG(ph.price) AS avg_price,
                COUNT(ph.id) AS samples
            FROM products p
            LEFT JOIN price_history ph ON ph.product_id = p.id
            JOIN users u ON u.id = p.user_id
            GROUP BY p.id
            """
        )
        summary: List[Dict[str, Optional[float]]] = []
        for row in cursor.fetchall():
            summary.append(
                {
                    "user_id": row["user_id"],
                    "user_email": row["user_email"],
                    "product_name": row["product_name"],
                    "product_url": row["product_url"],
                    "last_price": row["last_price"],
                    "currency": row["currency"],
                    "last_scraped": row["last_scraped"],
                    "min_price": row["min_price"],
                    "max_price": row["max_price"],
                    "avg_price": row["avg_price"],
                    "samples": row["samples"],
                }
            )
        return summary
