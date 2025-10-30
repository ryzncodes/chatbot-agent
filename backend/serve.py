"""Railway-friendly launcher that ensures repo root is importable."""

from __future__ import annotations

import os
import sys


def main() -> None:
    """Entry point."""
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(backend_dir)
    candidates = [
        repo_root,
        backend_dir,
        os.getcwd(),
        os.path.join(os.getcwd(), "app"),
        os.path.join(repo_root, "app"),
    ]

    chosen_root = None
    for candidate in candidates:
        backend_path = os.path.join(candidate, "backend")
        if os.path.isdir(backend_path):
            chosen_root = candidate
            break

    print("[backend/serve] __file__:", __file__)
    print("[backend/serve] cwd:", os.getcwd())
    print("[backend/serve] candidates:", candidates)
    print("[backend/serve] chosen_root:", chosen_root)

    if chosen_root:
        if chosen_root not in sys.path:
            sys.path.insert(0, chosen_root)
        backend_pkg_path = os.path.join(chosen_root, "backend")
        if backend_pkg_path not in sys.path:
            sys.path.insert(0, backend_pkg_path)
        try:
            print("[backend/serve] backend listing:", os.listdir(backend_pkg_path))
        except Exception as exc:  # noqa: BLE001
            print("[backend/serve] failed to list backend:", exc)
    else:
        print("[backend/serve] ERROR: backend package not found")

    print("[backend/serve] sys.path:", sys.path)

    from backend.main import app  # noqa: WPS433 (import position)

    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
