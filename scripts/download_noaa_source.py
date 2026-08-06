#!/usr/bin/env python3
"""Download NOAA's accessible Ocean Literacy PDF and verify its bytes."""

from __future__ import annotations

import hashlib
import sys
import urllib.error
import urllib.request
from pathlib import Path

SOURCE_URL = (
    "https://cdn.oceanservice.noaa.gov/oceanserviceprod/education/literacy/"
    "ocean-literacy-english.pdf"
)
EXPECTED_SHA256 = "029d79e6d17e506cc35d3fb2bdc5b676689fcbfee543df9c340feef0eaeb794c"
DESTINATION = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "knowledge"
    / "ocean-literacy-2024.pdf"
)


def main() -> int:
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    temporary = DESTINATION.with_suffix(".pdf.download")
    digest = hashlib.sha256()
    try:
        with (
            urllib.request.urlopen(SOURCE_URL, timeout=60) as response,
            temporary.open("wb") as output,
        ):
            while block := response.read(1024 * 1024):
                digest.update(block)
                output.write(block)
        if digest.hexdigest() != EXPECTED_SHA256:
            temporary.unlink(missing_ok=True)
            print("NOAA source checksum changed; download rejected.", file=sys.stderr)
            return 1
        temporary.replace(DESTINATION)
    except (OSError, TimeoutError, urllib.error.URLError) as error:
        temporary.unlink(missing_ok=True)
        print(f"NOAA source download failed: {type(error).__name__}", file=sys.stderr)
        return 1
    print(DESTINATION)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
