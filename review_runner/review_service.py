#!/usr/bin/env python3
"""Shared PR review service used by CLI entrypoints and the webhook server."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_API_URL = "https://api.github.com"
DEFAULT_MLX_REVIEW_CMD = "python3 -m review_runner.sample_mlx_client"


@dataclass
class ReviewComment:
    path: str
    line: int
    body: str
    side: str = "RIGHT"


@dataclass
class PullRequestFile:
    filename: str
    status: str
    patch: str
    additions: int
    deletions: int
    right_side_lines: set[int]


class GitHubApi:
    def __init__(self, token: str, repository: str, api_url: str = DEFAULT_API_URL) -> None:
        self.token = token
        self.repository = repository
        self.api_url = api_url.rstrip("/")

    def request_json(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.api_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        payload = None
        if body is not None:
            payload = json.dumps(body).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=payload,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "mac-mini-pr-reviewer",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request) as response:
                raw = response.read().decode("utf-8")
                if not raw:
                    return None
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API {method} {url} failed: {exc.code} {message}") from exc

    def list_pr_files(self, pull_number: int) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self.request_json(
                "GET",
                f"/repos/{self.repository}/pulls/{pull_number}/files",
                params={"per_page": 100, "page": page},
            )
            if not batch:
                break
            files.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return files

    def post_review(self, pull_number: int, body: dict[str, Any]) -> Any:
        return self.request_json(
            "POST",
            f"/repos/{self.repository}/pulls/{pull_number}/reviews",
            body=body,
        )


def parse_right_side_lines(patch: str) -> set[int]:
    lines: set[int] = set()
    current_new_line = None

    for raw_line in patch.splitlines():
        if raw_line.startswith("@@"):
            parts = raw_line.split()
            new_range = next(part for part in parts if part.startswith("+"))
            start_and_len = new_range[1:]
            if "," in start_and_len:
                start_str, _ = start_and_len.split(",", 1)
            else:
                start_str = start_and_len
            current_new_line = int(start_str)
            continue

        if current_new_line is None:
            continue

        if raw_line.startswith("+"):
            lines.add(current_new_line)
            current_new_line += 1
        elif raw_line.startswith(" "):
            lines.add(current_new_line)
            current_new_line += 1
        elif raw_line.startswith("-"):
            continue
        else:
            current_new_line = None

    return lines


def build_pr_files(raw_files: list[dict[str, Any]]) -> list[PullRequestFile]:
    files: list[PullRequestFile] = []
    for raw in raw_files:
        patch = raw.get("patch") or ""
        if not patch:
            continue
        files.append(
            PullRequestFile(
                filename=raw["filename"],
                status=raw["status"],
                patch=patch,
                additions=int(raw.get("additions", 0)),
                deletions=int(raw.get("deletions", 0)),
                right_side_lines=parse_right_side_lines(patch),
            )
        )
    return files


def make_prompt(repository: str, pull_number: int, files: list[PullRequestFile]) -> str:
    prompt_payload = {
        "repository": repository,
        "pull_request": pull_number,
        "instructions": {
            "task": "Review this PR diff and report concrete, actionable issues.",
            "line_comment_rules": [
                "Only report problems that are actually visible in the diff.",
                "Only use RIGHT-side line numbers listed in each file's valid_comment_lines.",
                "Prefer correctness, security, reliability, and significant maintainability issues.",
                "Do not suggest style-only comments or praise.",
            ],
            "response_schema": {
                "summary": "short overall review summary",
                "event": "COMMENT or REQUEST_CHANGES",
                "comments": [
                    {
                        "path": "relative/file.py",
                        "line": 12,
                        "body": "why this is a problem and what to change",
                    }
                ],
            },
        },
        "files": [
            {
                "path": f.filename,
                "status": f.status,
                "additions": f.additions,
                "deletions": f.deletions,
                "valid_comment_lines": sorted(f.right_side_lines),
                "patch": f.patch,
            }
            for f in files
        ],
    }
    return json.dumps(prompt_payload, ensure_ascii=False, indent=2)


def run_mlx(prompt: str) -> dict[str, Any]:
    raw_command = os.environ.get("MLX_REVIEW_CMD", DEFAULT_MLX_REVIEW_CMD)
    command = shlex.split(raw_command)
    completed = subprocess.run(
        command,
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "MLX command failed with exit code "
            f"{completed.returncode}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )

    stdout = completed.stdout.strip()
    if not stdout:
        raise RuntimeError("MLX command returned empty output")

    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"MLX command returned invalid JSON:\n{stdout}") from exc


def validate_mlx_output(result: dict[str, Any], files: list[PullRequestFile]) -> tuple[list[ReviewComment], str, str]:
    file_index = {f.filename: f for f in files}
    comments: list[ReviewComment] = []

    for raw in result.get("comments", []):
        path = raw.get("path")
        line = raw.get("line")
        body = (raw.get("body") or "").strip()
        if not path or not isinstance(line, int) or not body:
            continue

        pr_file = file_index.get(path)
        if pr_file is None or line not in pr_file.right_side_lines:
            continue

        comments.append(ReviewComment(path=path, line=line, body=body))

    summary = (result.get("summary") or "").strip() or "Automated review completed."

    event = (result.get("event") or "").strip().upper()
    if event not in {"COMMENT", "REQUEST_CHANGES"}:
        event = "REQUEST_CHANGES" if comments else "COMMENT"

    if not comments:
        event = "COMMENT"

    return comments, summary, event


def build_review_payload(summary: str, event: str, comments: list[ReviewComment]) -> dict[str, Any]:
    body = summary
    if comments:
        body = f"{summary}\n\nAutomated review found {len(comments)} actionable issue(s)."
    else:
        body = f"{summary}\n\nNo line-specific findings were produced."

    return {
        "body": body,
        "event": event,
        "comments": [
            {
                "path": comment.path,
                "line": comment.line,
                "side": comment.side,
                "body": comment.body,
            }
            for comment in comments
        ],
    }


def review_pull_request(
    repository: str,
    pull_number: int,
    token: str,
    api_url: str = DEFAULT_API_URL,
    dry_run: bool = False,
) -> dict[str, Any]:
    github = GitHubApi(token=token, repository=repository, api_url=api_url)
    raw_files = github.list_pr_files(pull_number)
    pr_files = build_pr_files(raw_files)

    if not pr_files:
        return {
            "status": "skipped",
            "reason": "No patchable files found.",
            "repository": repository,
            "pull_number": pull_number,
        }

    prompt = make_prompt(repository, pull_number, pr_files)
    if os.environ.get("WRITE_PROMPT_DEBUG") == "1":
        debug_path = os.environ.get("PROMPT_DEBUG_PATH", "/tmp/mlx_pr_review_prompt.json")
        with open(debug_path, "w", encoding="utf-8") as fh:
            fh.write(prompt)

    mlx_result = run_mlx(prompt)
    comments, summary, event = validate_mlx_output(mlx_result, pr_files)
    payload = build_review_payload(summary, event, comments)

    result = {
        "status": "completed",
        "repository": repository,
        "pull_number": pull_number,
        "event": event,
        "comment_count": len(comments),
        "payload": payload,
    }

    if dry_run:
        return result

    response = github.post_review(pull_number, payload)
    result["review_id"] = response.get("id")
    result["message"] = textwrap.dedent(
        f"""\
        Posted review successfully.
        Review ID: {response.get('id')}
        Event: {event}
        Comments: {len(comments)}
        """
    ).strip()
    return result
