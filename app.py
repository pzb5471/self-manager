"""Vercel-compatible FastAPI entrypoint.

Vercel's Python runtime auto-detects root-level files named ``app.py``. Keep
this module as a thin shim so the detected app is the real FastAPI app.
"""

from __future__ import annotations

from main import app, create_app

__all__ = ["app", "create_app"]
