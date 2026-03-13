#!/usr/bin/env python3
"""Compatibility wrapper for the real MLX review adapter."""

from __future__ import annotations

from review_runner.mlx_review_client import main


if __name__ == "__main__":
    raise SystemExit(main())
