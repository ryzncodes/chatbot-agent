"""Scrape ZUS drinkware catalogue into a JSON file.

Run this script **outside** the sandbox (on a machine with internet access)
because the hosted environment blocks outbound network traffic.

Example usage:

    python scrape_zus_drinkware.py --output ../db/raw/products.json

Dependencies (install locally):

    pip install -r requirements.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup


DEFAULT_BASE_URL = "https://shop.zuscoffee.com/collections/drinkware"
USER_AGENT = "Mozilla/5.0 (compatible; ZUSBot/1.0; +https://zuscoffee.com)"


@dataclass
class Product:
    sku: str
    name: str
    price: str
    description: str
    size: str
    tags: list[str]
    product_url: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape ZUS drinkware catalogue")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Drinkware collection URL (defaults to the official shop).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("products.json"),
        help="Destination JSON file for scraped catalogue.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Maximum number of paginated collection pages to crawl.",
    )
    return parser.parse_args()


def fetch_page(url: str) -> BeautifulSoup:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def extract_products(soup: BeautifulSoup) -> Iterable[Product]:
    # Many Shopify stores embed product metadata in ld+json scripts
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or "{}")
        except json.JSONDecodeError:
            continue

        if isinstance(payload, dict) and payload.get("@type") == "Product":
            yield product_from_ldjson(payload)
        elif isinstance(payload, list):
            for entry in payload:
                if isinstance(entry, dict) and entry.get("@type") == "Product":
                    yield product_from_ldjson(entry)


def product_from_ldjson(data: dict) -> Product:
    name = data.get("name", "").strip()
    sku = (data.get("sku") or data.get("mpn") or "").strip()
    description = (data.get("description") or "").strip()
    offers = data.get("offers", {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    price = str(offers.get("price", "")).strip()
    url = data.get("url", "").strip()

    size = ""
    if data.get("size"):
        size = str(data["size"]).strip()

    tags: list[str] = []
    if "keywords" in data:
        if isinstance(data["keywords"], list):
            tags = [str(tag).strip() for tag in data["keywords"] if str(tag).strip()]
        else:
            tags = [tag.strip() for tag in str(data["keywords"]).split(",") if tag.strip()]

    return Product(
        sku=sku,
        name=name,
        price=price,
        description=description,
        size=size,
        tags=tags or ["drinkware"],
        product_url=url,
    )


def main() -> None:
    args = parse_args()
    all_products: list[Product] = []

    for page in range(1, args.max_pages + 1):
        url = args.base_url if page == 1 else f"{args.base_url}?page={page}"
        try:
            soup = fetch_page(url)
        except requests.RequestException as exc:
            print(f"Error fetching {url}: {exc}", file=sys.stderr)
            break

        page_products = list(extract_products(soup))
        if not page_products:
            break

        all_products.extend(page_products)
        # Stop paginating if fewer than 5 products found (likely end of catalogue)
        if len(page_products) < 5:
            break

    if not all_products:
        print("No products scraped. Check the selectors or base URL.", file=sys.stderr)
        sys.exit(1)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump([asdict(product) for product in all_products], handle, ensure_ascii=False, indent=2)

    print(f"Scraped {len(all_products)} products → {args.output}")


if __name__ == "__main__":
    main()
