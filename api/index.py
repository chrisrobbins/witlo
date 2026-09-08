"""Vercel serverless entrypoint.

Vercel's Python runtime serves the module-level `app` (an ASGI application) for
every request routed here by `vercel.json`. The FastAPI app lives in `backend/`,
so that directory goes on the path before it is imported.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.main import app  # noqa: E402

__all__ = ["app"]
