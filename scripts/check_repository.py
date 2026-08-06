#!/usr/bin/env python3
"""Fail CI when tracked/history content violates the public demo repository boundary."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATHS = (
    re.compile(r"(^|/)(\.env|\.env\..+)$"),
    re.compile(r"(^|/)(data|uploads|chroma)(/|$)"),
    re.compile(r"\.(db|db-shm|db-wal|sqlite|sqlite3|log)$"),
    re.compile(r"^examples/knowledge/.+\.pdf$"),
)
SECRET_PATTERNS = {
    "OpenAI-style API key": re.compile(rb"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def tracked_files() -> list[str]:
    return [
        item.decode()
        for item in git(
            "ls-files", "-z", "--cached", "--others", "--exclude-standard"
        ).split(b"\0")
        if item
    ]


def history_blobs() -> list[tuple[str, str]]:
    objects: list[tuple[str, str]] = []
    for line in git("rev-list", "--objects", "--all").decode().splitlines():
        object_id, separator, path = line.partition(" ")
        if separator:
            objects.append((object_id, path))
    return objects


def scan_secret_bytes(label: str, content: bytes, failures: list[str]) -> None:
    for name, pattern in SECRET_PATTERNS.items():
        if pattern.search(content):
            failures.append(f"{label}: contains a possible {name}")


def check_markdown_links(files: list[str], failures: list[str]) -> None:
    for filename in files:
        if not filename.endswith(".md"):
            continue
        source = ROOT / filename
        text = source.read_text(encoding="utf-8")
        for target in MARKDOWN_LINK.findall(text):
            clean = target.strip().strip("<>").split("#", 1)[0]
            if not clean or re.match(r"^(?:https?://|mailto:)", clean):
                continue
            destination = (source.parent / unquote(clean)).resolve()
            if not destination.exists():
                failures.append(f"{filename}: broken local link {target}")


def check_deployment_contract(failures: list[str]) -> None:
    config = json.loads((ROOT / "railway.json").read_text(encoding="utf-8"))
    if config.get("build", {}).get("builder") != "DOCKERFILE":
        failures.append("railway.json: backend must use the Dockerfile builder")
    if config.get("deploy", {}).get("healthcheckPath") != "/api/v1/ready":
        failures.append("railway.json: healthcheck must use the real readiness route")
    lock = (ROOT / "backend/requirements.lock").read_text(encoding="utf-8")
    if re.search(r"^-e\s+/(?:Users|home)/", lock, flags=re.MULTILINE):
        failures.append(
            "backend/requirements.lock: contains a machine-local editable path"
        )


def main() -> int:
    failures: list[str] = []
    files = tracked_files()
    for filename in files:
        if not filename.endswith(".env.example") and any(
            pattern.search(filename) for pattern in RUNTIME_PATHS
        ):
            failures.append(f"{filename}: runtime or secret-bearing path is tracked")
        path = ROOT / filename
        if path.is_file():
            scan_secret_bytes(filename, path.read_bytes(), failures)

    for object_id, path in history_blobs():
        content = git("cat-file", "-p", object_id)
        scan_secret_bytes(f"history:{path}@{object_id[:12]}", content, failures)

    check_markdown_links(files, failures)
    check_deployment_contract(failures)
    if failures:
        print("Repository validation failed:", file=sys.stderr)
        for failure in sorted(set(failures)):
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(
        f"Repository validation passed: {len(files)} tracked files, "
        f"{len(history_blobs())} history blobs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
