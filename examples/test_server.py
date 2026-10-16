#!/usr/bin/env python3
"""Grip SDK Interactive Test Server.

Runs the official Grip AI Search server and ChatGPT-style dark mode web UI
powered by the Grip SDK client.

https://grip.theshoaib.me/
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Ensure local monorepo packages are discoverable
_ROOT = Path(__file__).resolve().parent.parent
for _p in [
    _ROOT / "packages" / "sdk" / "src",
    _ROOT / "packages" / "core" / "src",
    _ROOT / "packages" / "engine" / "src",
    _ROOT,
]:
    _p_str = str(_p)
    if _p.exists() and _p_str not in sys.path:
        sys.path.insert(0, _p_str)

import grip
from app.server import create_app
from google_ai_search.config import get_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("grip_test_server")

config = get_config()
port = int(os.getenv("PORT", "8080"))
config.port = port

# Support remote GRIP_API_URL or embedded local client
backend_url = os.getenv("GRIP_API_URL")
client = grip.Grip(base_url=backend_url) if backend_url else None

app = create_app(config=config, client=client)

if __name__ == "__main__":
    print(f"🚀 Grip SDK Interactive Test Server running at http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
