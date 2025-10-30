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
        "/app",
        "/workspace",
        "/",
    ]

    backend_path = None
    inspected: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in inspected or not os.path.isdir(candidate):
            continue
        inspected.add(candidate)

        direct = os.path.join(candidate, "backend")
        if os.path.isdir(direct) and os.path.isfile(os.path.join(direct, "main.py")):
            backend_path = direct
            break

        try:
            for entry in os.listdir(candidate):
                nested = os.path.join(candidate, entry)
                if os.path.isdir(nested):
                    direct = os.path.join(nested, "backend")
                    if os.path.isdir(direct) and os.path.isfile(os.path.join(direct, "main.py")):
                        backend_path = direct
                        break
        except Exception as exc:  # noqa: BLE001
            print(f"[backend/serve] failed to inspect {candidate}: {exc}")
        if backend_path:
            break

    chosen_root = os.path.dirname(backend_path) if backend_path else None

    print("[backend/serve] __file__:", __file__)
    print("[backend/serve] cwd:", os.getcwd())
    print("[backend/serve] candidates:", candidates)
    print("[backend/serve] chosen_root:", chosen_root)
    print("[backend/serve] backend_path:", backend_path)

    if backend_path:
        if chosen_root and chosen_root not in sys.path:
            sys.path.insert(0, chosen_root)
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
        try:
            print("[backend/serve] backend listing:", os.listdir(backend_path))
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
