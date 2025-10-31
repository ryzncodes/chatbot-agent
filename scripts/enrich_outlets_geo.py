"""Resolve Google Maps short links and enrich outlet JSON with coordinates.

Run this script on a machine with internet access (the sandbox blocks outbound
requests). It reads an outlets JSON file, follows the `map_url` short links, and
attempts to extract latitude/longitude from the final redirected URL.

Usage:

    python enrich_outlets_geo.py --input ../docs/samples/outlets.sample.json \
        --output ../docs/samples/outlets.enriched.json

To update the existing file in-place, omit `--output` and use `--overwrite`.

Dependencies: `pip install requests` (already listed in scripts/requirements.txt).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests


USER_AGENT = "Mozilla/5.0 (compatible; ZUSBot/1.0; +https://zuscoffee.com)"
COORD_PATTERNS = [
    re.compile(r"@([+-]?\d+\.\d+),([+-]?\d+\.\d+)"),  # .../@3.115,-101.623,17z
    re.compile(r"!3d([+-]?\d+\.\d+)!4d([+-]?\d+\.\d+)"),  # ...!3d3.115!4d-101.623...
    re.compile(r"(?:center|ll)=([+-]?\d+\.\d+),([+-]?\d+\.\d+)"),  # center=lat,lng
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich outlets JSON with lat/lng from map URLs")
    parser.add_argument("--input", type=Path, required=True, help="Path to outlets JSON file")
    parser.add_argument("--output", type=Path, help="Output path (defaults to input path)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite input file in-place")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between requests (seconds)")
    return parser.parse_args()


def extract_coords(url: str) -> tuple[float | None, float | None]:
    for pattern in COORD_PATTERNS:
        match = pattern.search(url)
        if match:
            lat, lng = match.groups()
            try:
                return float(lat), float(lng)
            except ValueError:
                continue
    return None, None


def resolve_map_url(short_url: str) -> str | None:
    try:
        response = requests.get(
            short_url,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
            timeout=15,
        )
        response.raise_for_status()
        return response.url
    except requests.RequestException as exc:  # noqa: BLE001
        print(f"[warn] Failed to resolve {short_url}: {exc}", file=sys.stderr)
        return None


def main() -> None:
    args = parse_args()
    output_path = args.output or (args.input if args.overwrite else None)

    if output_path is None:
        print("Provide --output or --overwrite to specify where to write the enriched file.", file=sys.stderr)
        sys.exit(1)

    with args.input.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        print("Expected outlets JSON to be a list of objects.", file=sys.stderr)
        sys.exit(1)

    enriched: list[dict[str, Any]] = []
    updated_count = 0

    for idx, outlet in enumerate(data, start=1):
        if not isinstance(outlet, dict):
            enriched.append(outlet)
            continue

        lat = outlet.get("latitude")
        lng = outlet.get("longitude")
        map_url = outlet.get("map_url")

        if map_url and (lat in (None, "", 0) or lng in (None, "", 0)):
            final_url = resolve_map_url(map_url)
            if final_url:
                new_lat, new_lng = extract_coords(final_url)
                if new_lat is not None and new_lng is not None:
                    outlet["latitude"] = new_lat
                    outlet["longitude"] = new_lng
                    updated_count += 1
                    print(f"[{idx}] {outlet.get('name', 'Unknown')} → ({new_lat}, {new_lng})")
                else:
                    print(f"[{idx}] No coordinates found for {map_url}", file=sys.stderr)
            else:
                print(f"[{idx}] Failed to resolve {map_url}", file=sys.stderr)

            time.sleep(max(0, args.delay))

        enriched.append(outlet)

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(enriched, handle, ensure_ascii=False, indent=2)

    print(f"Done. Updated {updated_count} outlet(s). Written to {output_path}")


if __name__ == "__main__":
    main()
