"""Launch script that resolves the backend package before starting Uvicorn."""

from __future__ import annotations

import importlib
import logging
import os
import sys
from pathlib import Path
from typing import Iterable

import uvicorn

logger = logging.getLogger("zus.launcher")


def _candidate_roots() -> Iterable[Path]:
    current_file = Path(__file__).resolve()
    repo_root = current_file.parent.parent
    cwd = Path.cwd()

    seen: set[Path] = set()
    for path in [
        repo_root,
        repo_root / "app",
        current_file.parent,
        cwd,
        cwd / "app",
        Path("/app"),
        Path("/workspace"),
    ]:
        if path not in seen:
            seen.add(path)
            yield path


def _find_backend() -> Path | None:
    for root in _candidate_roots():
        backend_dir = root / "backend"
        if (backend_dir / "main.py").is_file():
            return backend_dir

        # Check one level deep for monorepo layouts.
        try:
            for child in root.iterdir():
                nested = child / "backend"
                if nested.is_dir() and (nested / "main.py").is_file():
                    return nested
        except FileNotFoundError:
            continue
        except Exception as exc:  # noqa: BLE001
            logger.debug("Skipping %s: %s", root, exc)
    return None


def _bootstrap_paths(backend_dir: Path) -> None:
    repo_root = backend_dir.parent
    for path in (repo_root, backend_dir):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def main() -> None:
    backend_dir = _find_backend()
    if backend_dir is None:
        logger.error("Unable to locate backend package")
        raise RuntimeError("backend package not found")

    _bootstrap_paths(backend_dir)
    logger.debug("Backend directory resolved to %s", backend_dir)

    # Attempt to seed data into mounted volume before app import,
    # so readiness passes as soon as the server starts.
    try:
        from backend.init_data import seed_on_startup  # noqa: WPS433 (import position)

        seed_on_startup()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Data seeding step skipped: %s", exc)

    app_module = importlib.import_module("backend.main")
    app = app_module.app  # type: ignore[attr-defined]

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
