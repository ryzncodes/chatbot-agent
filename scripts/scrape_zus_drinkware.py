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
from typing import Iterable, List

import requests
from bs4 import BeautifulSoup


DEFAULT_COLLECTION = "drinkware"
BASE_DOMAIN = "https://shop.zuscoffee.com"
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
        "--collection",
        default=DEFAULT_COLLECTION,
        help="Collection handle (defaults to 'drinkware').",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("products.json"),
        help="Destination JSON file for scraped catalogue.",
    )
    return parser.parse_args()


def fetch_json_page(collection: str, page: int) -> List[dict] | None:
    url = f"{BASE_DOMAIN}/collections/{collection}/products.json?page={page}"
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    payload = response.json()
    products = payload.get("products") if isinstance(payload, dict) else None
    if not isinstance(products, list):
        return None
    return products


def fetch_html(url: str) -> BeautifulSoup:
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


def product_from_shopify_json(data: dict) -> Product:
    name = str(data.get("title", "")).strip()
    sku = str(data.get("variants", [{}])[0].get("sku", "") if data.get("variants") else "").strip()
    description = BeautifulSoup(data.get("body_html", ""), "html.parser").get_text(" ", strip=True)
    tags = [tag.strip() for tag in str(data.get("tags", "")).split(",") if tag.strip()]
    price = ""
    if data.get("variants"):
        price = str(data["variants"][0].get("price", "")).strip()

    options = data.get("options") or []
    size = ""
    for option in options:
        if isinstance(option, dict) and option.get("name", "").lower() == "size":
            values = option.get("values", [])
            if values:
                size = str(values[0]).strip()
                break

    url = data.get("handle")
    product_url = f"{BASE_DOMAIN}/products/{url}" if url else ""

    return Product(
        sku=sku,
        name=name,
        price=price,
        description=description,
        size=size,
        tags=tags or ["drinkware"],
        product_url=product_url,
    )


def main() -> None:
    args = parse_args()
    all_products: list[Product] = []

    # Try Shopify JSON API first
    for page in range(1, 20):
        try:
            json_products = fetch_json_page(args.collection, page)
        except requests.RequestException as exc:
            print(f"Error fetching JSON page {page}: {exc}", file=sys.stderr)
            break

        if not json_products:
            break

        for product in json_products:
            all_products.append(product_from_shopify_json(product))

        if len(json_products) < 20:
            break

    # Fallback to HTML scraping if JSON API returned nothing (e.g., disabled)
    if not all_products:
        for page in range(1, 6):
            url = f"{BASE_DOMAIN}/collections/{args.collection}?page={page}" if page > 1 else f"{BASE_DOMAIN}/collections/{args.collection}"
            try:
                soup = fetch_html(url)
            except requests.RequestException as exc:
                print(f"Error fetching {url}: {exc}", file=sys.stderr)
                break

            page_products = list(extract_products(soup))
            if not page_products:
                break

            all_products.extend(page_products)
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
