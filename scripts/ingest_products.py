"""Ingest ZUS drinkware catalogue into a FAISS index using TF-IDF embeddings."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import faiss  # type: ignore
import numpy as np


DEFAULT_RAW_PATH = Path("../db/raw/products.json")
DEFAULT_OUTPUT_DIR = Path("../db/faiss")
METADATA_FILENAME = "products_metadata.json"
INDEX_FILENAME = "products.index"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest drinkware catalogue into FAISS index")
    parser.add_argument(
        "--input-file",
        type=Path,
        default=DEFAULT_RAW_PATH,
        help="Path to local JSON file containing drinkware catalogue entries.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where the FAISS index and metadata will be stored.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse input but skip writing FAISS files (useful for validation).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of neighbours to precompute for evaluation (unused but kept for compatibility).",
    )
    return parser.parse_args()


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def load_catalogue(path: Path) -> list[dict]:
    if not path or not path.exists():
        raise FileNotFoundError(
            f"Catalogue file not found at {path}. Supply --input-file pointing to a local JSON export."
        )

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        raise ValueError("Expected top-level JSON array of product records")

    return data


def build_embeddings(products: list[dict]) -> tuple[np.ndarray, list[str], np.ndarray]:
    vocabulary_counter: Counter[str] = Counter()
    tokenized_products: list[list[str]] = []

    for product in products:
        text_segments = [
            str(product.get("name", "")),
            str(product.get("description", "")),
            str(product.get("product_type", "")),
            str(product.get("vendor", "")),
            " ".join(product.get("tags", []) if isinstance(product.get("tags"), list) else []),
        ]

        option_tokens: list[str] = []
        for option in product.get("options", []) or []:
            if isinstance(option, dict):
                option_tokens.append(str(option.get("name", "")))
                option_tokens.extend(str(value) for value in option.get("values", []) if value)

        variant_tokens: list[str] = []
        for variant in product.get("variants", []) or []:
            if not isinstance(variant, dict):
                continue
            variant_tokens.append(str(variant.get("title", "")))
            price = variant.get("price")
            if price:
                variant_tokens.append(str(price))

        text_segments.extend([
            " ".join(option_tokens),
            " ".join(variant_tokens),
        ])
        tokens = tokenize(" ".join(text_segments))
        if not tokens:
            tokens = tokenize(str(product.get("name", "")))
        tokenized_products.append(tokens)
        vocabulary_counter.update(set(tokens))

    vocabulary = sorted(vocabulary_counter.keys())
    token_to_index = {token: idx for idx, token in enumerate(vocabulary)}

    # Compute document frequency
    doc_freq: defaultdict[str, int] = defaultdict(int)
    for tokens in tokenized_products:
        unique_tokens = set(tokens)
        for token in unique_tokens:
            doc_freq[token] += 1

    total_docs = len(products)
    idf = np.zeros(len(vocabulary), dtype=np.float32)
    for token, idx in token_to_index.items():
        idf[idx] = math.log((1 + total_docs) / (1 + doc_freq[token])) + 1.0

    embeddings = np.zeros((total_docs, len(vocabulary)), dtype=np.float32)
    for doc_idx, tokens in enumerate(tokenized_products):
        if not tokens:
            continue
        token_counts = Counter(tokens)
        for token, count in token_counts.items():
            token_idx = token_to_index.get(token)
            if token_idx is None:
                continue
            tf = count / len(tokens)
            embeddings[doc_idx, token_idx] = tf * idf[token_idx]

    faiss.normalize_L2(embeddings)
    return embeddings, vocabulary, idf


def write_index(embeddings: np.ndarray, output_path: Path) -> None:
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    faiss.write_index(index, str(output_path))


def write_metadata(products: list[dict], vocabulary: list[str], idf: np.ndarray, output_path: Path) -> None:
    payload = {
        "products": products,
        "vocabulary": vocabulary,
        "idf": idf.tolist(),
    }
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def main() -> None:
    args = parse_args()
    catalogue = load_catalogue(args.input_file)

    print(f"Loaded {len(catalogue)} drinkware products from {args.input_file}")
    embeddings, vocabulary, idf = build_embeddings(catalogue)
    print(f"Vocabulary size: {len(vocabulary)}")

    if args.dry_run:
        print("Dry-run enabled; skipping FAISS write")
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)
    index_path = args.output_dir / INDEX_FILENAME
    metadata_path = args.output_dir / METADATA_FILENAME

    write_index(embeddings, index_path)
    write_metadata(catalogue, vocabulary, idf, metadata_path)

    print(f"Wrote index to {index_path}")
    print(f"Wrote metadata to {metadata_path}")


if __name__ == "__main__":
    main()
