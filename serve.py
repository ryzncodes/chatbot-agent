"""Railway-friendly backend launcher with explicit sys.path setup."""

from __future__ import annotations

import os
import sys

if __name__ == "__main__":
    # Ensure the repository root (this file's directory) is first on sys.path so the
    # `backend` package can be imported even when the working directory differs.
    repo_root = os.path.dirname(os.path.abspath(__file__))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    backend_dir = os.path.join(repo_root, "backend")
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    print("[serve] __file__:", __file__)
    print("[serve] cwd:", os.getcwd())
    print("[serve] sys.path:", sys.path)
    try:
        print("[serve] repo listing:", os.listdir(repo_root))
    except Exception as exc:  # noqa: BLE001
        print("[serve] failed to list repo:", exc)

    # Import after mutating sys.path so the backend package resolves correctly.
    from backend.main import app

    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
