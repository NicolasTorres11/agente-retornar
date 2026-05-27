#!/usr/bin/env python3
"""Initialize the local encrypted SQLite database."""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.adapters.sqlite import SQLiteConversationRepository  # noqa: E402
from src.settings import AppSettings  # noqa: E402


async def main() -> None:
    settings = AppSettings()
    repository = SQLiteConversationRepository(settings.db_path, settings.field_encryption_key)
    await repository.initialize()
    print(f"Base SQLite inicializada: {settings.db_path}")


if __name__ == "__main__":
    asyncio.run(main())
