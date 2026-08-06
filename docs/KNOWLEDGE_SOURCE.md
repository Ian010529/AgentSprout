# Example Knowledge Source

## Approved source

- Title: *Ocean Literacy: The Essential Principles and Fundamental Concepts of Ocean Sciences for Learners of All Ages*
- Corporate author: United States National Oceanic and Atmospheric Administration (NOAA)
- Edition/year: 2024 repository record
- Repository page: <https://repository.library.noaa.gov/view/noaa/67228>
- DOI shown by NOAA: <https://doi.org/10.25923/dym5-4y14>
- Rights shown by NOAA: CC0 Public Domain
- License URL: <https://creativecommons.org/publicdomain/zero/1.0/>
- Repository-reported size: approximately 11.34 MB
- Accepted accessible edition: NOAA Ocean Service Version 3.2, January 2024

## Handling requirements

- Download the official accessible PDF unchanged from NOAA Ocean Service in M3.
- Do not scrape and recombine article text.
- Do not remove attribution, alter the PDF, or imply AgentSprout authored it.
- Record the final direct download URL and SHA-256 after download.
- Verify the actual byte size, page count, text extraction, and page mapping.
- If the official file/license differs from this record at implementation time, stop and update the decision log before committing the asset.
- If committing the 11 MB PDF materially harms repository usability, preserve reproducibility through a verified download script plus checksum; choose and record one approach in M3 before implementation.

## Verification record

To be completed in M3 after the official file is downloaded:

```text
Retrieved at (UTC): 2026-08-06
Direct download URL: https://cdn.oceanservice.noaa.gov/oceanserviceprod/education/literacy/ocean-literacy-english.pdf
Original filename: ocean-literacy-english.pdf
Byte size: 1,162,058 bytes
Page count: 13
SHA-256: 029d79e6d17e506cc35d3fb2bdc5b676689fcbfee543df9c340feef0eaeb794c
PDF text extraction result: PASS — 29,459 non-whitespace characters; every page has a text layer
License rechecked at: 2026-08-06 on NOAA IR record noaa:67228 (CC0 Public Domain)
Repository strategy: verified download script; PDF remains gitignored
```

The NOAA Institutional Repository's 11.34 MB delivery was also checksum-verified against
its published SHA-512. It was rejected as the ingestion demo asset because 11 of 13 pages
have no extractable text and the MVP intentionally has no OCR. NOAA Ocean Service links the
accepted byte-distinct accessible delivery as Version 3.2, January 2024. Decision D-041
records this conflict resolution.

## Evaluation use

- M5 authors the four in-knowledge and three out-of-knowledge cases only after inspecting the unchanged PDF.
- Each in-knowledge case records expected evidence pages/chunks.
- Out-of-knowledge cases must be demonstrably absent or unsupported; model memory is not an answer source.
- Do not tune case wording solely to make a failing system pass. Record material changes to suite wording in the suite version and decision log.
