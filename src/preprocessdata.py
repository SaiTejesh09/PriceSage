from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Mapping

from storage import PriceStorage


def export_summary(database_path: Path, output_path: Path) -> None:
    storage = PriceStorage(database_path)
    try:
        rows = storage.price_summary()
    finally:
        storage.close()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "user_id",
                "user_email",
                "product_name",
                "product_url",
                "currency",
                "last_price",
                "last_scraped",
                "min_price",
                "max_price",
                "avg_price",
                "samples",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(_format_row(row))

    print(f"Summary exported to {output_path}")


def _format_row(row: Mapping[str, object]) -> Mapping[str, object]:
    formatted = {}
    for key, value in row.items():
        if isinstance(value, float):
            formatted[key] = f"{value:.2f}"
        else:
            formatted[key] = value
    return formatted


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    database = base.parent / "data" / "prices.db"
    output = base / "reports" / "price_summary.csv"
    export_summary(database, output)
