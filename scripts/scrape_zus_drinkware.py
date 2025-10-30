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
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable, List

import requests
from bs4 import BeautifulSoup

DEFAULT_COLLECTION = "drinkware"
BASE_DOMAIN = "https://shop.zuscoffee.com"
USER_AGENT = "Mozilla/5.0 (compatible; ZUSBot/1.0; +https://zuscoffee.com)"


@dataclass
class Product:
    id: int | str
    name: str
    handle: str
    description: str
    vendor: str | None
    product_type: str | None
    tags: list[str] = field(default_factory=list)
    options: list[dict[str, Any]] = field(default_factory=list)
    variants: list[dict[str, Any]] = field(default_factory=list)
    primary_image: str | None = None
    images: list[dict[str, Any]] = field(default_factory=list)
    price: str | None = None
    product_url: str | None = None


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
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Maximum number of paginated collection pages to crawl.",
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
    description = (data.get("description") or "").strip()
    offers = data.get("offers", {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    price = str(offers.get("price", "")).strip() or None
    url = data.get("url", "").strip() or None

    tags: list[str] = []
    if "keywords" in data:
        if isinstance(data["keywords"], list):
            tags = [str(tag).strip() for tag in data["keywords"] if str(tag).strip()]
        else:
            tags = [tag.strip() for tag in str(data["keywords"]).split(",") if tag.strip()]

    return Product(
        id=str(data.get("@id", "")) or name,
        name=name,
        handle="",
        description=description,
        vendor=None,
        product_type=None,
        tags=tags or ["drinkware"],
        price=price,
        product_url=url,
    )


def product_from_shopify_json(data: dict) -> Product:
    name = str(data.get("title", "")).strip()
    handle = str(data.get("handle", "")).strip()
    description = BeautifulSoup(data.get("body_html", ""), "html.parser").get_text(" ", strip=True)
    tags = [tag.strip() for tag in str(data.get("tags", "")).split(",") if tag.strip()]

    options: list[dict[str, Any]] = []
    for option in data.get("options", []) or []:
        if isinstance(option, dict):
            options.append(
                {
                    "name": option.get("name"),
                    "position": option.get("position"),
                    "values": option.get("values", []),
                }
            )

    variants: list[dict[str, Any]] = []
    min_price: str | None = None
    for variant in data.get("variants", []) or []:
        if not isinstance(variant, dict):
            continue
        variant_price = str(variant.get("price", "")).strip() or None
        if variant_price:
            try:
                if min_price is None or float(variant_price) < float(min_price):
                    min_price = variant_price
            except ValueError:
                pass
        variants.append(
            {
                "id": variant.get("id"),
                "sku": variant.get("sku"),
                "title": variant.get("title"),
                "price": variant_price,
                "compare_at_price": variant.get("compare_at_price"),
                "available": variant.get("available"),
                "option_values": [
                    variant.get("option1"),
                    variant.get("option2"),
                    variant.get("option3"),
                ],
                "weight_grams": variant.get("grams"),
            }
        )

    images: list[dict[str, Any]] = []
    primary_image = None
    for image in data.get("images", []) or []:
        if not isinstance(image, dict):
            continue
        record = {
            "src": image.get("src"),
            "alt": image.get("alt"),
            "position": image.get("position"),
        }
        images.append(record)
        if primary_image is None:
            primary_image = record.get("src")

    return Product(
        id=data.get("id", handle or name),
        name=name,
        handle=handle,
        description=description,
        vendor=data.get("vendor"),
        product_type=data.get("product_type"),
        tags=tags or ["drinkware"],
        options=options,
        variants=variants,
        primary_image=primary_image,
        images=images,
        price=min_price,
        product_url=f"{BASE_DOMAIN}/products/{handle}" if handle else None,
    )


def main() -> None:
    args = parse_args()
    all_products: list[Product] = []

    for page in range(1, (args.max_pages or 1_000) + 1):
        try:
            json_products = fetch_json_page(args.collection, page)
        except requests.RequestException as exc:
            print(f"Error fetching JSON page {page}: {exc}", file=sys.stderr)
            break

        if not json_products:
            break

        all_products.extend(product_from_shopify_json(prod) for prod in json_products)

        if len(json_products) < 20:
            break

    if not all_products:
        for page in range(1, (args.max_pages or 5) + 1):
            url = (
                f"{BASE_DOMAIN}/collections/{args.collection}?page={page}"
                if page > 1
                else f"{BASE_DOMAIN}/collections/{args.collection}"
            )
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
