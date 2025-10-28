"""Scrape ZUS outlet listings into a JSON file.

Run this script on a machine with internet access; the sandbox blocks outbound
requests. It uses Selenium (headless Chrome) to render the listing page because
the outlet cards are injected via JavaScript.

Example usage:

    python scrape_zus_outlets.py --output ../docs/samples/outlets.sample.json

Then feed the JSON into `sync_outlets.py` to refresh the SQLite store:

    python sync_outlets.py --input-file ../docs/samples/outlets.sample.json --drop-existing
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


BASE_URL = "https://zuscoffee.com/category/store/kuala-lumpur-selangor/"


@dataclass
class Outlet:
    name: str
    address: str
    city: str
    state: str
    postcode: str
    latitude: float | None
    longitude: float | None
    opening_hours: str
    services: list[str]
    map_url: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape ZUS outlet listings")
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help="Outlet listing URL (defaults to Kuala Lumpur & Selangor page).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outlets.json"),
        help="Destination JSON file for scraped outlets.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=0,
        help="Maximum paginated pages to crawl (0 = crawl all)",
    )
    return parser.parse_args()


def fetch_rendered_html(url: str, wait_seconds: int = 5) -> BeautifulSoup:
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1280,720")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    try:
        driver.get(url)
        driver.implicitly_wait(wait_seconds)
        page_source = driver.page_source
    finally:
        driver.quit()

    return BeautifulSoup(page_source, "html.parser")


def extract_outlets(soup: BeautifulSoup) -> Iterable[Outlet]:
    # Elementor renders each outlet inside an <article>
    for article in soup.select("article.elementor-post"):
        name_node = article.select_one(".elementor-heading-title")
        if not name_node:
            continue
        name = name_node.get_text(strip=True)
        if not name:
            continue

        address_lines: list[str] = []
        hours = ""
        services: list[str] = []

        content_widget = article.select_one(".elementor-widget-theme-post-content")
        if content_widget:
            for paragraph in content_widget.select("p"):
                text = paragraph.get_text(" ", strip=True)
                if text:
                    address_lines.append(text)

        for meta in article.select(".elementor-icon-list-text"):
            text = meta.get_text(" ", strip=True)
            if not text:
                continue
            lowered = text.lower()
            if any(term in lowered for term in ("am", "pm", "hour", "open", "close")):
                hours = text
            elif any(term in lowered for term in ("dine", "pickup", "delivery", "drive")):
                services.append(text)
            else:
                address_lines.append(text)

        address_lines = [line for line in address_lines if line.strip()]
        address = address_lines[0] if address_lines else ""
        city = state = postcode = ""

        if len(address_lines) > 1:
            city_state = address_lines[1]
            parts = [part.strip() for part in city_state.replace(",", " ").split() if part.strip()]
            if parts and parts[-1].isdigit():
                postcode = parts[-1]
                parts = parts[:-1]
            if parts:
                state = parts[-1]
                city = " ".join(parts[:-1]) if len(parts) > 1 else state

        map_link = ""
        button = article.select_one("a.premium-button")
        if button and button.has_attr("href"):
            map_link = button["href"].strip()

        yield Outlet(
            name=name,
            address=address,
            city=city,
            state=state,
            postcode=postcode,
            latitude=None,
            longitude=None,
            opening_hours=hours,
            services=services,
            map_url=map_link,
        )


def main() -> None:
    args = parse_args()
    current_url = args.base_url
    visited: set[str] = set()
    collected: list[Outlet] = []
    page_counter = 0

    while current_url and current_url not in visited:
        if args.max_pages and page_counter >= args.max_pages:
            break

        try:
            soup = fetch_rendered_html(current_url)
        except Exception as exc:  # noqa: BLE001
            print(f"Error rendering {current_url}: {exc}", file=sys.stderr)
            break

        visited.add(current_url)
        page_counter += 1
        collected.extend(extract_outlets(soup))

        next_link = soup.select_one("nav.elementor-pagination a.next")
        if next_link and next_link.get("href"):
            current_url = next_link["href"].strip()
        else:
            break

    if not collected:
        print("No outlets scraped. The page structure may have changed — update selectors in scrape_zus_outlets.py.", file=sys.stderr)
        sys.exit(1)

    deduped: dict[tuple[str, str], Outlet] = {}
    for outlet in collected:
        key = (outlet.name, outlet.address)
        deduped[key] = outlet
    outlets = list(deduped.values())

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump([asdict(outlet) for outlet in outlets], handle, ensure_ascii=False, indent=2)

    print(f"Scraped {len(outlets)} outlets → {args.output}")


if __name__ == "__main__":
    main()
