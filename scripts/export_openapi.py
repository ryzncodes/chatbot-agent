#!/usr/bin/env python
"""Export FastAPI OpenAPI schema to backend/openapi.yaml."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
import types

import yaml


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    backend_dir = repo_root / "backend"
    output_path = backend_dir / "openapi.yaml"

    _install_faiss_stub()

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from backend.main import app  # noqa: WPS433

    schema = app.openapi()
    output_path.write_text(yaml.dump(schema, sort_keys=False), encoding="utf-8")
    print(f"Wrote {output_path.relative_to(repo_root)}")


def _install_faiss_stub() -> None:
    """Register a lightweight FAISS stub to avoid native import crashes."""

    if "faiss" in sys.modules:
        return

    module = types.ModuleType("faiss")

    class _DummyIndex:
        def search(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("FAISS disabled for OpenAPI export")

    def _unsupported(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("FAISS disabled for OpenAPI export")

    module.Index = _DummyIndex  # type: ignore[attr-defined]
    module.IndexFlatIP = _DummyIndex  # type: ignore[attr-defined]
    module.normalize_L2 = lambda *a, **k: None  # type: ignore[attr-defined]
    module.read_index = _unsupported  # type: ignore[attr-defined]
    module.write_index = _unsupported  # type: ignore[attr-defined]

    sys.modules["faiss"] = module


if __name__ == "__main__":
    main()
