#!/usr/bin/env python3
"""Build the web frontend, copy artifacts to openfox/static/web, then remove web/dist."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = REPO_ROOT / "web"
NODE_MODULES = WEB_DIR / "node_modules"
DIST_DIR = WEB_DIR / "dist"
STATIC_WEB = REPO_ROOT / "openfox" / "static" / "web"


def main() -> None:
    if shutil.which("pnpm") is None:
        print("error: pnpm not found; install from https://pnpm.io/installation", file=sys.stderr)
        sys.exit(1)

    if not WEB_DIR.is_dir():
        print(f"error: web directory not found: {WEB_DIR}", file=sys.stderr)
        sys.exit(1)

    if not NODE_MODULES.is_dir():
        print("node_modules missing; running pnpm install …")
        subprocess.run(["pnpm", "install"], cwd=WEB_DIR, check=True)

    if DIST_DIR.exists():
        print(f"removing existing build dir {DIST_DIR}")
        shutil.rmtree(DIST_DIR)

    print("building web …")
    env = {**os.environ, "VITE_APP_BASE": "/web"}
    subprocess.run(["pnpm", "run", "build"], cwd=WEB_DIR, check=True, env=env)

    if not DIST_DIR.is_dir():
        print(f"error: build output missing: {DIST_DIR}", file=sys.stderr)
        sys.exit(1)

    if STATIC_WEB.exists():
        print(f"removing stale output {STATIC_WEB}")
        shutil.rmtree(STATIC_WEB)

    STATIC_WEB.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(DIST_DIR, STATIC_WEB)
    print(f"copied to {STATIC_WEB}")

    print(f"removing intermediate build {DIST_DIR}")
    shutil.rmtree(DIST_DIR)


if __name__ == "__main__":
    main()
