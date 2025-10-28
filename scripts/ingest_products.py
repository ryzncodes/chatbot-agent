"""Ingest ZUS drinkware catalogue into a FAISS index.

This script is a placeholder scaffold. Provide a local JSON feed using
`--input-file` until network access is available. The final implementation
should fetch drinkware data, compute embeddings, and write to
`db/faiss/products.index`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest drinkware catalogue into FAISS index")
    parser.add_argument(
        "--input-file",
        type=Path,
        help="Path to local JSON file containing drinkware catalogue entries.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("../db/faiss"),
        help="Directory where the FAISS index and metadata will be stored.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse input but skip writing FAISS files (useful for validation).",
    )
    return parser.parse_args()


def load_catalogue(path: Path) -> list[dict]:
    if not path or not path.exists():
        raise FileNotFoundError("Provide --input-file pointing to a local drinkware JSON export")

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        raise ValueError("Expected top-level JSON array of product records")

    return data


def main() -> None:
    args = parse_args()
    catalogue = load_catalogue(args.input_file)

    print(f"Loaded {len(catalogue)} drinkware products")

    if args.dry_run:
        print("Dry-run enabled; skipping FAISS index creation")
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = args.output_dir / "products_metadata.json"

    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(catalogue, handle, ensure_ascii=False, indent=2)

    # Placeholder for FAISS index creation. Actual implementation should compute embeddings
    # and build an index saved to args.output_dir / "products.index".
    placeholder_index = args.output_dir / "products.index"
    placeholder_index.write_bytes(b"FAISS_INDEX_PLACEHOLDER")
    print(f"Wrote placeholder FAISS index to {placeholder_index}")


if __name__ == "__main__":
    main()
