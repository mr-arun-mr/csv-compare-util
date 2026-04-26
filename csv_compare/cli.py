"""CLI entry point for csv-compare."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click

from .comparator import compare_files
from .history import save_run
from .reporter import generate_report
from .resolver import pair_files


@click.command()
@click.option(
    "--expected", "-e", required=True,
    help="Expected CSV: single file, comma-separated files, or directory.",
)
@click.option(
    "--actual", "-a", required=True,
    help="Actual CSV: single file, comma-separated files, or directory.",
)
@click.option(
    "--output", "-o", required=True,
    help="Output directory for the HTML report and history.",
)
@click.option(
    "--row-key", "-k", required=True,
    help="Column name used to match rows between expected and actual.",
)
@click.option(
    "--fuzzy-threshold", "-f", default=100.0, show_default=True,
    type=click.FloatRange(0, 100),
    help="Similarity threshold (0-100) for fuzzy string matching. "
         "Values below 100 allow near-matches to count as matched.",
)
@click.option(
    "--label", "-l", default=None,
    help="Optional label for this run shown in trend charts (defaults to current timestamp).",
)
@click.option(
    "--no-history", "skip_history", is_flag=True, default=False,
    help="Disable history tracking. No history is saved and trend charts are omitted.",
)
def main(
    expected: str,
    actual: str,
    output: str,
    row_key: str,
    fuzzy_threshold: float,
    label: str | None,
    skip_history: bool,
) -> None:
    """Compare CSV files and generate an HTML comparison report."""
    output_dir = Path(output)
    run_label = label or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    click.echo("Resolving file pairs...")
    try:
        pairs = pair_files(expected, actual)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc))

    click.echo(f"Comparing {len(pairs)} file pair(s) with row key '{row_key}' (fuzzy threshold={fuzzy_threshold}%)")

    results = []
    for exp_path, act_path in pairs:
        click.echo(f"  {exp_path.name} vs {act_path.name} ... ", nl=False)
        try:
            result = compare_files(exp_path, act_path, row_key, fuzzy_threshold)
            results.append(result)
            click.echo(
                f"overall={result.overall_match_pct:.1f}%  "
                f"rows={result.matched_rows}/{result.total_expected}"
            )
        except Exception as exc:
            click.echo(f"ERROR: {exc}", err=True)

    if not results:
        raise click.ClickException("No files were successfully compared.")

    if not skip_history:
        click.echo("Saving history...")
        save_run(output_dir, results, run_label)

    click.echo("Generating HTML report...")
    report_path = generate_report(results, output_dir, run_label, include_history=not skip_history)

    click.echo(f"\nReport written to: {report_path}")


if __name__ == "__main__":
    main()
