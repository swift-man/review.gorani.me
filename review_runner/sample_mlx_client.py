#!/usr/bin/env python3
"""Example MLX adapter.

Replace this module with your actual MLX invocation. It receives the prepared prompt JSON
on stdin and must print a JSON object matching the response schema described in review_pr.py.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    payload = json.load(sys.stdin)
    files = payload.get("files", [])

    response = {
        "summary": f"Sample MLX adapter ran against {len(files)} file(s).",
        "event": "COMMENT",
        "comments": [],
    }
    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
