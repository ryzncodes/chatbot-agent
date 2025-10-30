"""Railway-friendly backend launcher with explicit sys.path setup."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable


def find_backend_path(candidates: Iterable[str]) -> str | None:
    """Locate the backend package directory within provided candidates."""

    inspected: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in inspected or not os.path.isdir(candidate):
            continue
        inspected.add(candidate)

        direct = os.path.join(candidate, "backend")
        if os.path.isdir(direct) and os.path.isfile(os.path.join(direct, "main.py")):
            return direct

        try:
            for entry in os.listdir(candidate):
                nested = os.path.join(candidate, entry)
                if os.path.isdir(nested):
                    direct = os.path.join(nested, "backend")
                    if os.path.isdir(direct) and os.path.isfile(os.path.join(direct, "main.py")):
                        return direct
        except Exception as exc:  # noqa: BLE001
            print(f"[serve] failed to inspect {candidate}: {exc}")
    return None


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        script_dir,
        os.getcwd(),
        os.path.join(script_dir, "app"),
        os.path.join(os.getcwd(), "app"),
        os.path.dirname(script_dir),
        "/app",
        "/workspace",
        "/",
    ]

    backend_path = find_backend_path(candidates)
    backend_root = os.path.dirname(backend_path) if backend_path else None

    print("[serve] __file__:", __file__)
    print("[serve] cwd:", os.getcwd())
    print("[serve] candidates:", candidates)
    print("[serve] chosen backend_root:", backend_root)
    print("[serve] chosen backend_path:", backend_path)

    if backend_path:
        if backend_root and backend_root not in sys.path:
            sys.path.insert(0, backend_root)
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
        try:
            print("[serve] backend listing:", os.listdir(backend_path))
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
