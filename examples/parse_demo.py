"""Runnable demo of the task-title parsing layer -- no credentials required.

The pipeline's job is to turn free-text ClickUp task titles into structured sets
of targets (project code, blocks, lots, model names). That parsing layer is pure:
it touches no network and no spreadsheet, so it can be demonstrated on its own.

Run it from the repository root:

    python examples/parse_demo.py

Everything below is invented sample input in the shape the parsers expect.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from expander import (  # noqa: E402  (path setup must precede the import)
    extract_allowed_targets,
    parse_compound_suffixes,
    parse_number_sequence,
)

SAMPLE_TITLES = [
    "D10001 BLOCK 1 TO 3",
    "D10002 LOT 5, 7",
    "D10003 BLK 2 2ND REVIEW",
    "D10004 BLOCK 1, TO 4, 6 TO 8",
    "a title with no project code",
]

SAMPLE_SEGMENTS = ["1 TO 5", "12-18", "1, TO 4, 6 TO 8", "2 TO 4, 9"]
SAMPLE_SUFFIX_BLOBS = ["1 TO 3", "A, B", "1-3, X"]


def main() -> None:
    print("=" * 68)
    print("Numeric sequence expansion")
    print("=" * 68)
    for seg in SAMPLE_SEGMENTS:
        print(f"  {seg!r:24} -> {parse_number_sequence(seg)}")

    print()
    print("=" * 68)
    print("Compound suffix expansion")
    print("=" * 68)
    for blob in SAMPLE_SUFFIX_BLOBS:
        print(f"  {blob!r:24} -> {parse_compound_suffixes(blob)}")

    print()
    print("=" * 68)
    print("Full task-title extraction")
    print("=" * 68)
    for title in SAMPLE_TITLES:
        project, models, blocks, lots = extract_allowed_targets(title)
        print(f"  {title!r}")
        if project is None:
            print("      -> no project code found; title is skipped\n")
            continue
        print(f"      project : {project}")
        print(f"      blocks  : {sorted(blocks) if blocks else '-'}")
        print(f"      lots    : {sorted(lots) if lots else '-'}")
        print(f"      models  : {len(models)} generated spelling variant(s)")
        print()


if __name__ == "__main__":
    main()
