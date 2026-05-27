#!/usr/bin/env python3
"""Run the local FastAPI app without requiring an import-time .env."""

import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.api import create_app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(create_app(), host="127.0.0.1", port=8000)
