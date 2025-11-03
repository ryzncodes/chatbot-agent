"""Enrich outlets JSON with city/state/postcode parsed from address and
optionally opening hours + services via Google Places.

Usage examples:

    # Only infer city/state/postcode from address
    python scripts/enrich_outlets_details.py --input db/raw/outlets.json --overwrite

    # Also fetch opening hours and services using Google Places
    export GOOGLE_MAPS_API_KEY=your_api_key
    python scripts/enrich_outlets_details.py --input db/raw/outlets.json --overwrite --use-places

Notes:
- Requires `requests` (already in scripts/requirements.txt).
- Be mindful of Google Places API quotas and billing; pass `--delay 0.5` to
  add a small pause between calls.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


USER_AGENT = "Mozilla/5.0 (compatible; ZUSBot/1.0; +https://zuscoffee.com)"


# Canonical state names with common synonyms for matching/normalization
STATE_SYNONYMS: dict[str, list[str]] = {
    "Johor": ["johor", "johor bahru"],
    "Kedah": ["kedah"],
    "Kelantan": ["kelantan"],
    "Malacca": ["malacca", "melaka"],
    "Negeri Sembilan": ["negeri sembilan"],
    "Pahang": ["pahang"],
    "Penang": ["penang", "pulau pinang"],
    "Perak": ["perak"],
    "Perlis": ["perlis"],
    "Sabah": ["sabah"],
    "Sarawak": ["sarawak"],
    "Selangor": ["selangor", "selangor darul ehsan"],
    "Terengganu": ["terengganu"],
    "Kuala Lumpur": [
        "kuala lumpur",
        "wilayah persekutuan kuala lumpur",
        "wp kuala lumpur",
        "w.p. kuala lumpur",
        "federal territory of kuala lumpur",
    ],
    "Putrajaya": ["putrajaya", "wilayah persekutuan putrajaya"],
    "Labuan": ["labuan", "wilayah persekutuan labuan"],
}


POSTCODE_RE = re.compile(r"\b(\d{5})\b")
PLACE_ID_IN_URL_RE = re.compile(r"(?:place_id:|query_place_id=)([A-Za-z0-9_-]{10,})")


@dataclass
class AddressParts:
    city: Optional[str]
    state: Optional[str]
    postcode: Optional[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich outlets JSON with address parts and optional Places data.")
    parser.add_argument("--input", type=Path, required=True, help="Path to outlets JSON file")
    parser.add_argument("--output", type=Path, help="Output path (defaults to input path)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite input file in-place")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay between external requests (seconds)")
    parser.add_argument(
        "--use-places",
        action="store_true",
        help="Enable Google Places enrichment for opening_hours/services (requires GOOGLE_MAPS_API_KEY)",
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Only fill fields that are currently empty (do not overwrite populated fields)",
    )
    parser.add_argument(
        "--places-region",
        type=str,
        default="MY",
        help="Region code for Places API queries (default: MY)",
    )
    return parser.parse_args()


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _canonical_state(raw: str | None) -> Optional[str]:
    if not raw:
        return None
    lowered = raw.lower()
    for canonical, synonyms in STATE_SYNONYMS.items():
        for name in synonyms:
            if name in lowered:
                return canonical
    return None


def _extract_city_after_postcode(address: str) -> Optional[str]:
    # Looks for: "12345 City Name, State" and returns "City Name"
    match = re.search(r"\b\d{5}\b\s*([^,]+)", address)
    if match:
        candidate = match.group(1).strip(" .")
        # Some addresses include trailing country names or extra descriptors, keep it simple
        if candidate:
            return candidate
    return None


def _extract_city_before_state(address: str, state: str) -> Optional[str]:
    # Looks for: "City Name, {state}" and returns "City Name"
    pattern = re.compile(rf"([^,]+)\s*,\s*{re.escape(state)}", flags=re.IGNORECASE)
    match = pattern.search(address)
    if match:
        candidate = match.group(1).strip(" .")
        if candidate and not POSTCODE_RE.search(candidate):
            return candidate
    return None


def parse_address_parts(address: str) -> AddressParts:
    if not address:
        return AddressParts(city=None, state=None, postcode=None)

    addr = _normalize_whitespace(address.replace("Malaysia", "").replace("MY", ""))
    # Postcode: last 5-digit token wins
    postcodes = POSTCODE_RE.findall(addr)
    postcode = postcodes[-1] if postcodes else None

    # State: try to canonicalize based on known synonyms
    state = _canonical_state(addr)

    # City: prefer the word(s) after postcode before next comma; else the token before state
    city = _extract_city_after_postcode(addr)
    if not city and state:
        city = _extract_city_before_state(addr, state) or city

    # Tidy common punctuation and casing
    if city:
        city = _normalize_whitespace(city.replace("WP", "").replace("W.P.", "")).strip(", ")

    return AddressParts(city=city or None, state=state or None, postcode=postcode or None)


def resolve_map_url(short_url: str) -> Optional[str]:
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


def extract_place_id_from_url(url: str) -> Optional[str]:
    match = PLACE_ID_IN_URL_RE.search(url)
    if match:
        return match.group(1)
    return None


def places_find_place(
    api_key: str,
    name: str,
    location_bias: Optional[Tuple[float, float]] = None,
    region: str = "MY",
) -> Optional[str]:
    params = {
        "input": name,
        "inputtype": "textquery",
        "fields": "place_id,name,formatted_address",
        "key": api_key,
        "region": region,
    }
    if location_bias and all(location_bias):
        lat, lng = location_bias
        params["locationbias"] = f"point:{lat},{lng}"

    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/findplacefromtext/json",
            params=params,
            timeout=20,
        )
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] FindPlace failed: {exc}", file=sys.stderr)
        return None

    candidates = data.get("candidates", [])
    if not candidates:
        return None
    return candidates[0].get("place_id")


def places_get_details(api_key: str, place_id: str) -> Optional[dict]:
    fields = [
        "opening_hours",
        "current_opening_hours",
        "delivery",
        "dine_in",
        "takeout",
        "types",
        "url",
        "website",
    ]
    params = {
        "place_id": place_id,
        "fields": ",".join(fields),
        "key": api_key,
    }
    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/details/json",
            params=params,
            timeout=20,
        )
        data = resp.json()
        if data.get("status") != "OK":
            print(
                f"[warn] Place details not OK for {place_id}: {data.get('status')} {data.get('error_message', '')}",
                file=sys.stderr,
            )
            return None
        return data.get("result")
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] Place details failed for {place_id}: {exc}", file=sys.stderr)
        return None


def summarize_opening_hours(result: dict) -> Optional[str]:
    hours = None
    src = None
    if isinstance(result.get("current_opening_hours"), dict):
        hours = result["current_opening_hours"].get("weekday_text")
        src = "current_opening_hours"
    if not hours and isinstance(result.get("opening_hours"), dict):
        hours = result["opening_hours"].get("weekday_text")
        src = src or "opening_hours"

    if not hours:
        return None

    # Try to compress if all days share the same time window
    times: list[str] = []
    for line in hours:
        if ":" in line:
            times.append(line.split(":", 1)[1].strip())
    if times and all(t == times[0] for t in times):
        return f"Daily {times[0]}"

    # Fallback to a compact join of Mon–Sun text
    compact = "; ".join(hours)
    # Avoid overly long strings
    return compact[:300] + ("…" if len(compact) > 300 else "")


def extract_services(result: dict) -> list[str]:
    services: list[str] = []
    # Map Google booleans to our normalized service keywords used in search
    if result.get("dine_in") is True:
        services.append("dine-in")
    if result.get("takeout") is True or result.get("curbside_pickup") is True:
        services.append("pickup")
    if result.get("delivery") is True:
        services.append("delivery")

    # Try to infer drive-through from types or opening_hours tags
    types = result.get("types") or []
    if isinstance(types, list) and any("drive" in t for t in types):
        services.append("drive")

    # Deduplicate while preserving order
    seen = set()
    deduped: list[str] = []
    for s in services:
        if s not in seen:
            seen.add(s)
            deduped.append(s)
    return deduped


def update_record(
    rec: dict,
    only_missing: bool,
    places_enabled: bool,
    api_key: Optional[str],
    region: str,
    delay: float,
) -> tuple[dict, bool]:
    changed = False

    # Parse address-derived fields
    addr = str(rec.get("address") or "")
    parts = parse_address_parts(addr)

    if parts.city and (not rec.get("city") or not only_missing):
        if rec.get("city") != parts.city:
            rec["city"] = parts.city
            changed = True
    if parts.state and (not rec.get("state") or not only_missing):
        if rec.get("state") != parts.state:
            rec["state"] = parts.state
            changed = True
    if parts.postcode and (not rec.get("postcode") or not only_missing):
        if rec.get("postcode") != parts.postcode:
            rec["postcode"] = parts.postcode
            changed = True

    # Optionally fetch opening hours + services via Places
    needs_hours = not rec.get("opening_hours")
    needs_services = not rec.get("services")

    if places_enabled and api_key and (needs_hours or needs_services):
        place_id = None
        # Best effort: try to extract from final map URL
        map_url = rec.get("map_url")
        if map_url:
            final_url = resolve_map_url(map_url)
            if final_url:
                place_id = extract_place_id_from_url(final_url)

        if not place_id:
            # Fallback to Find Place by text, with location bias when available
            name = str(rec.get("name") or "").strip()
            lat = rec.get("latitude")
            lng = rec.get("longitude")
            location_bias = (lat, lng) if isinstance(lat, (int, float)) and isinstance(lng, (int, float)) else None
            query = name
            # Add postcode or city to help disambiguate
            if rec.get("postcode"):
                query = f"{name} {rec['postcode']}"
            elif rec.get("city"):
                query = f"{name} {rec['city']}"
            place_id = places_find_place(api_key=api_key, name=query, location_bias=location_bias, region=region)

        if place_id:
            details = places_get_details(api_key=api_key, place_id=place_id)
            if details:
                if needs_hours:
                    summary = summarize_opening_hours(details)
                    if summary:
                        rec["opening_hours"] = summary
                        changed = True
                if needs_services:
                    services = extract_services(details)
                    if services:
                        rec["services"] = services
                        changed = True
            time.sleep(max(0, delay))

    return rec, changed


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

    use_places = bool(args.use_places)
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY") if use_places else None
    if use_places and not api_key:
        print("[warn] --use-places specified but GOOGLE_MAPS_API_KEY is not set; skipping Places enrichment.", file=sys.stderr)
        use_places = False

    enriched: list[dict[str, Any]] = []
    updated_count = 0

    for idx, outlet in enumerate(data, start=1):
        if not isinstance(outlet, dict):
            enriched.append(outlet)
            continue

        updated, changed = update_record(
            rec=outlet,
            only_missing=args.only_missing,
            places_enabled=use_places,
            api_key=api_key,
            region=args.places_region,
            delay=args.delay,
        )
        if changed:
            updated_count += 1
            name = updated.get("name", "Unknown")
            city = updated.get("city") or "?"
            state = updated.get("state") or "?"
            pc = updated.get("postcode") or "?"
            print(f"[{idx}] {name} — {city}, {state} {pc}")

        enriched.append(updated)

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(enriched, handle, ensure_ascii=False, indent=2)

    print(f"Done. Updated {updated_count} outlet(s). Written to {output_path}")


if __name__ == "__main__":
    main()

