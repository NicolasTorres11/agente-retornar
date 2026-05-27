#!/usr/bin/env python3
"""Send a Meta-shaped, signed test webhook to the running local API."""

import hashlib
import hmac
import json
import sys
import time
from argparse import ArgumentParser
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.settings import AppSettings  # noqa: E402


def main() -> int:
    parser = ArgumentParser()
    parser.add_argument("message", help="Texto que enviara el usuario simulado")
    parser.add_argument("--wa-id", default="573003333333")
    parser.add_argument("--url", default="http://127.0.0.1:8000/webhook")
    args = parser.parse_args()
    settings = AppSettings()
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"profile": {"name": "Usuario Webhook"}}],
                            "messages": [
                                {
                                    "from": args.wa_id,
                                    "id": f"wamid.local.{time.time_ns()}",
                                    "timestamp": str(int(time.time())),
                                    "type": "text",
                                    "text": {"body": args.message},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(
        settings.whatsapp_app_secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    response = httpx.post(
        args.url,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": f"sha256={signature}",
        },
        timeout=10,
    )
    print(response.status_code, response.text)
    return 0 if response.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
