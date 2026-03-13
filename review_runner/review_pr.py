#!/usr/bin/env python3
"""CLI entrypoint for reviewing one pull request from a GitHub event payload."""

from __future__ import annotations

import os
import sys
import json

from review_runner.review_service import DEFAULT_API_URL, review_pull_request

def parse_event() -> tuple[str, int]:
    event_path = os.environ["GITHUB_EVENT_PATH"]
    repository = os.environ.get("GITHUB_REPOSITORY")
    with open(event_path, "r", encoding="utf-8") as fh:
        event = json.load(fh)

    repository = repository or event["repository"]["full_name"]
    pull_number = int(event["pull_request"]["number"])
    return repository, pull_number


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required")

    repository, pull_number = parse_event()
    result = review_pull_request(
        repository=repository,
        pull_number=pull_number,
        token=token,
        api_url=os.environ.get("GITHUB_API_URL", DEFAULT_API_URL),
        dry_run=os.environ.get("DRY_RUN") == "1",
    )
    if os.environ.get("DRY_RUN") == "1":
        print(json.dumps(result.get("payload", result), ensure_ascii=False, indent=2))
        return 0

    print(result.get("message", json.dumps(result, ensure_ascii=False)))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
