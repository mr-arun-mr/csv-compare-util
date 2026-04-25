"""Stores and retrieves historical comparison runs for trend analysis."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .comparator import FileComparisonResult

HISTORY_FILE = "comparison_history.json"


def _result_to_dict(result: FileComparisonResult) -> Dict[str, Any]:
    return {
        "expected_file": Path(result.expected_file).name,
        "actual_file": Path(result.actual_file).name,
        "total_expected": result.total_expected,
        "total_actual": result.total_actual,
        "matched_rows": result.matched_rows,
        "fully_matched_rows": result.fully_matched_rows,
        "row_match_pct": round(result.row_match_pct, 2),
        "overall_match_pct": round(result.overall_match_pct, 2),
        "attribute_match_pcts": {k: round(v, 2) for k, v in result.attribute_match_pcts.items()},
    }


def load_history(output_dir: Path) -> List[Dict[str, Any]]:
    history_path = output_dir / HISTORY_FILE
    if not history_path.exists():
        return []
    with open(history_path) as f:
        return json.load(f)


def save_run(output_dir: Path, results: List[FileComparisonResult], run_label: Optional[str] = None) -> None:
    history = load_history(output_dir)

    files_compared = len(results)
    total_rows = sum(r.total_expected for r in results)
    matched_rows = sum(r.matched_rows for r in results)
    total_cells = sum(
        len(r.columns) * r.matched_rows for r in results
    )
    # Weighted overall match %
    overall = (
        sum(r.overall_match_pct * r.matched_rows for r in results) / matched_rows
        if matched_rows else 0.0
    )
    row_match = (
        sum(r.row_match_pct * r.total_expected for r in results) / total_rows
        if total_rows else 0.0
    )

    # Merged attribute match pcts across all files
    attr_totals: Dict[str, List[float]] = {}
    for r in results:
        for col, pct in r.attribute_match_pcts.items():
            attr_totals.setdefault(col, []).append(pct)
    attr_avg = {col: round(sum(vals) / len(vals), 2) for col, vals in attr_totals.items()}

    entry: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "label": run_label or datetime.now().strftime("%Y-%m-%d %H:%M"),
        "files_compared": files_compared,
        "total_rows": total_rows,
        "overall_match_pct": round(overall, 2),
        "row_match_pct": round(row_match, 2),
        "attribute_match_pcts": attr_avg,
        "file_results": [_result_to_dict(r) for r in results],
    }
    history.append(entry)

    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)
