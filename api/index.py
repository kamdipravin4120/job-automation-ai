"""
Vercel ASGI entry point.

Vercel looks for `app` (an ASGI callable) in this file.
`create_app()` is called once per cold start; the result is reused for
the lifetime of the warm instance (Fluid Compute).

WebSocket note: the pubsub_bridge background task that runs under
uvicorn's event loop is NOT started here.  Vercel serverless functions
do not support long-lived background tasks.  WebSocket connections
still work (Vercel supports WSS on Pro), but push events from Celery
workers via Redis pubsub will NOT be delivered — the bridge task is
intentionally disabled in this entry point.  See VERCEL_DEPLOYMENT in
the environment to distinguish runtimes if you later want to reconnect
the bridge via an external pubsub service (e.g. Upstash Pub/Sub REST).
"""
from __future__ import annotations

import os

# Tell the app factory we are running on Vercel so it can skip the
# background pubsub bridge task.
os.environ.setdefault("VERCEL_DEPLOYMENT", "1")

from src.api.app import create_app  # noqa: E402

app = create_app()
