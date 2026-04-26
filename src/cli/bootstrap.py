from __future__ import annotations

import json
import secrets
import time


def run(*, redis_url: str | None = None, print_qr: bool = True) -> str:
    import redis as syncredis

    from src.settings import get_settings

    settings = get_settings()
    if redis_url is None:
        redis_url = settings.celery_broker_url

    secret_bytes = secrets.token_bytes(32)
    secret_hex = secret_bytes.hex()
    ttl = settings.bootstrap_secret_ttl_seconds

    r = syncredis.from_url(redis_url)
    r.setex(
        f"bootstrap:{secret_hex}",
        ttl,
        json.dumps({"issued_at": int(time.time())}),
    )
    r.close()

    if print_qr:
        try:
            import qrcode

            qr = qrcode.QRCode()
            qr.add_data(secret_hex)
            qr.make(fit=True)
            qr.print_ascii(invert=True)
        except Exception:
            pass
        print(f"\nBootstrap secret: {secret_hex}")
        print(f"(expires in {ttl}s — scan QR or copy secret to device)")

    return secret_hex
