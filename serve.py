"""Railway-friendly backend launcher with explicit sys.path setup."""

from __future__ import annotations

import os
import sys

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        script_dir,
        os.getcwd(),
        os.path.join(script_dir, "app"),
        os.path.join(os.getcwd(), "app"),
        os.path.dirname(script_dir),
    ]

    backend_root = None
    for candidate in candidates:
        backend_path = os.path.join(candidate, "backend")
        if os.path.isdir(backend_path):
            backend_root = candidate
            break

    print("[serve] __file__:", __file__)
    print("[serve] cwd:", os.getcwd())
    print("[serve] candidates:", candidates)
    print("[serve] chosen backend_root:", backend_root)

    if backend_root:
        if backend_root not in sys.path:
            sys.path.insert(0, backend_root)
        backend_pkg_path = os.path.join(backend_root, "backend")
        if backend_pkg_path not in sys.path:
            sys.path.insert(0, backend_pkg_path)
        try:
            print("[serve] backend listing:", os.listdir(backend_pkg_path))
        except Exception as exc:  # noqa: BLE001
            print("[serve] failed to list backend:", exc)
    else:
        print("[serve] ERROR: Could not locate backend package")

    print("[serve] sys.path:", sys.path)

    # Import after mutating sys.path so the backend package resolves correctly.
    from backend.main import app

    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
