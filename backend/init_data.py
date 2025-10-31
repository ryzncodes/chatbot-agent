"""One-time data seeding for FAISS index and outlets DB.

If `/app/db` (the mounted volume) is empty, copy seed files bundled in the
image under `/app/db-seed`. This keeps runtime simple and allows easy
replacement later by updating the volume contents.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from backend.core.config import get_settings

logger = logging.getLogger("zus.init")


def _copy_if_missing(src: Path, dst: Path) -> None:
    try:
        if dst.exists():
            return
        if not src.exists():
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        logger.info("Seeded %s -> %s", src, dst)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to seed %s to %s: %s", src, dst, exc)


def seed_on_startup() -> None:
    """Copy initial data from `/app/db-seed` into `/app/db` if missing."""

    settings = get_settings()

    seed_dir = Path("/app/db-seed")
    if not seed_dir.exists():
        logger.debug("No seed directory present; skipping data seeding")
        return

    # Outlets DB
    outlets_src = seed_dir / "outlets.db"
    outlets_dst = Path(settings.outlets_db_path)
    _copy_if_missing(outlets_src, outlets_dst)

    # FAISS index and metadata
    index_src = seed_dir / "faiss" / "products.index"
    index_dst = Path(settings.faiss_index_path)
    _copy_if_missing(index_src, index_dst)

    meta_src = seed_dir / "faiss" / "products_metadata.json"
    meta_dst = Path(settings.products_metadata_path)
    _copy_if_missing(meta_src, meta_dst)

