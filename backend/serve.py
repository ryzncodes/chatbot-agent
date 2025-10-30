"""Railway-friendly launcher that ensures repo root is importable."""

from __future__ import annotations

import os
import sys


def main() -> None:
    """Entry point."""
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(backend_dir)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    print("[backend/serve] __file__:", __file__)
    print("[backend/serve] cwd:", os.getcwd())
    print("[backend/serve] sys.path:", sys.path)
    try:
        print("[backend/serve] repo listing:", os.listdir(repo_root))
    except Exception as exc:  # noqa: BLE001
        print("[backend/serve] failed to list repo:", exc)

    from backend.main import app  # noqa: WPS433 (import position)

    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
