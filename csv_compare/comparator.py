"""Core CSV comparison logic with fuzzy matching support."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from rapidfuzz import fuzz


@dataclass
class CellResult:
    expected: str
    actual: str
    match: bool
    similarity: float  # 0-100


@dataclass
class RowResult:
    key: str
    status: str  # 'compared' | 'missing_in_actual' | 'extra_in_actual'
    cells: Dict[str, CellResult] = field(default_factory=dict)
    row_match_pct: float = 0.0


@dataclass
class FileComparisonResult:
    expected_file: str
    actual_file: str
    row_key: str
    columns: List[str]
    rows: List[RowResult]

    # Derived metrics (computed post-init)
    total_expected: int = 0
    total_actual: int = 0
    matched_rows: int = 0      # rows present in both sides
    fully_matched_rows: int = 0  # rows where row_match_pct == 100
    row_match_pct: float = 0.0   # % of expected rows found in actual
    overall_match_pct: float = 0.0
    attribute_match_pcts: Dict[str, float] = field(default_factory=dict)

    def compute_metrics(self) -> None:
        compared = [r for r in self.rows if r.status == "compared"]
        missing = [r for r in self.rows if r.status == "missing_in_actual"]
        extra = [r for r in self.rows if r.status == "extra_in_actual"]

        self.total_expected = len(compared) + len(missing)
        self.total_actual = len(compared) + len(extra)
        self.matched_rows = len(compared)
        self.fully_matched_rows = sum(1 for r in compared if r.row_match_pct == 100.0)

        self.row_match_pct = (
            self.matched_rows / self.total_expected * 100
            if self.total_expected else 0.0
        )

        # Attribute-level: across all compared rows
        col_matched: Dict[str, int] = {c: 0 for c in self.columns}
        col_total: Dict[str, int] = {c: 0 for c in self.columns}
        total_cells = total_matched_cells = 0
        for row in compared:
            for col, cell in row.cells.items():
                col_total[col] = col_total.get(col, 0) + 1
                total_cells += 1
                if cell.match:
                    col_matched[col] = col_matched.get(col, 0) + 1
                    total_matched_cells += 1

        self.attribute_match_pcts = {
            col: (col_matched[col] / col_total[col] * 100 if col_total[col] else 0.0)
            for col in self.columns
        }
        self.overall_match_pct = (
            total_matched_cells / total_cells * 100 if total_cells else 0.0
        )


def compare_dataframes(
    expected_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    row_key: str,
    fuzzy_threshold: float,
) -> List[RowResult]:
    """Compare two DataFrames row by row using row_key as the join key."""
    if row_key not in expected_df.columns:
        raise ValueError(f"Row key '{row_key}' not found in expected file columns: {list(expected_df.columns)}")
    if row_key not in actual_df.columns:
        raise ValueError(f"Row key '{row_key}' not found in actual file columns: {list(actual_df.columns)}")

    exp = expected_df.set_index(row_key)
    act = actual_df.set_index(row_key)

    # Convert index to string for consistent matching
    exp.index = exp.index.astype(str)
    act.index = act.index.astype(str)

    # Use expected columns as canonical; ignore extra columns in actual
    columns = list(exp.columns)

    exp_keys = set(exp.index)
    act_keys = set(act.index)
    all_keys = sorted(exp_keys | act_keys, key=str)

    results: List[RowResult] = []
    for key in all_keys:
        in_exp = key in exp_keys
        in_act = key in act_keys

        if in_exp and not in_act:
            results.append(RowResult(key=key, status="missing_in_actual"))
            continue
        if not in_exp and in_act:
            results.append(RowResult(key=key, status="extra_in_actual"))
            continue

        exp_row = exp.loc[key]
        act_row = act.loc[key]
        cells: Dict[str, CellResult] = {}
        matched = 0

        for col in columns:
            exp_val = str(exp_row[col]) if col in exp_row.index else ""
            act_val = str(act_row[col]) if col in act_row.index else ""

            if exp_val == act_val:
                match, similarity = True, 100.0
            else:
                similarity = float(fuzz.ratio(exp_val, act_val))
                match = similarity >= fuzzy_threshold

            if match:
                matched += 1
            cells[col] = CellResult(
                expected=exp_val,
                actual=act_val,
                match=match,
                similarity=similarity,
            )

        row_match_pct = matched / len(columns) * 100 if columns else 100.0
        results.append(RowResult(key=key, status="compared", cells=cells, row_match_pct=row_match_pct))

    return results, columns


def compare_files(
    expected_path: Path,
    actual_path: Path,
    row_key: str,
    fuzzy_threshold: float,
) -> FileComparisonResult:
    expected_df = pd.read_csv(expected_path, dtype=str).fillna("")
    actual_df = pd.read_csv(actual_path, dtype=str).fillna("")

    rows, columns = compare_dataframes(expected_df, actual_df, row_key, fuzzy_threshold)

    result = FileComparisonResult(
        expected_file=str(expected_path),
        actual_file=str(actual_path),
        row_key=row_key,
        columns=columns,
        rows=rows,
    )
    result.compute_metrics()
    return result
