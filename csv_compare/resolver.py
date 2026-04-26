"""Resolves input specifications (single file, comma-list, directory) to file pairs."""

import os
from pathlib import Path
from typing import List, Tuple


def resolve_files(spec: str) -> List[Path]:
    """Return a sorted list of CSV paths from a single file, comma-list, or directory."""
    paths: List[Path] = []
    for part in spec.split(","):
        p = Path(part.strip())
        if not p.exists():
            raise FileNotFoundError(f"Path not found: {p}")
        if p.is_dir():
            paths.extend(sorted(p.glob("*.csv")))
        else:
            if p.suffix.lower() != ".csv":
                raise ValueError(f"Not a CSV file: {p}")
            paths.append(p)
    return paths


def pair_files(expected_spec: str, actual_spec: str) -> List[Tuple[Path, Path]]:
    """
    Match expected and actual files by stem name.
    Returns list of (expected_path, actual_path) pairs.
    Raises if no pairs can be formed.
    """
    expected = resolve_files(expected_spec)
    actual = resolve_files(actual_spec)

    # If exactly one file on each side, pair them directly (no stem matching needed).
    if len(expected) == 1 and len(actual) == 1:
        return [(expected[0], actual[0])]

    actual_by_stem = {p.stem: p for p in actual}

    pairs: List[Tuple[Path, Path]] = []
    unmatched: List[Path] = []
    for exp in expected:
        act = actual_by_stem.get(exp.stem)
        if act:
            pairs.append((exp, act))
        else:
            unmatched.append(exp)

    if not pairs:
        raise ValueError(
            "No file pairs could be matched by name. "
            f"Expected stems: {[p.stem for p in expected]}, "
            f"Actual stems: {list(actual_by_stem.keys())}"
        )
    if unmatched:
        names = ", ".join(p.name for p in unmatched)
        print(f"Warning: no matching actual file found for: {names}")

    return pairs
