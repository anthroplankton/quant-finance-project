"""Build local-only weekly GDELT news-count panels for the 8-week pilot."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def _add_src_to_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))


_add_src_to_path()

from quant_finance_project.news.weekly_counts import (  # noqa: E402
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PILOT_END_DATE,
    DEFAULT_PILOT_START_DATE,
    DEFAULT_UNIVERSE_FILE,
    WeeklyCountAggregationError,
    build_gdelt_weekly_counts,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate local GDELT stock-day counts into a zero-filled "
            "stock-week news-count panel. This does not compute a Hype Index."
        )
    )
    parser.add_argument(
        "--pilot-start-date",
        default=DEFAULT_PILOT_START_DATE,
        help="Inclusive pilot start date. Default: 2025-04-05.",
    )
    parser.add_argument(
        "--pilot-end-date",
        default=DEFAULT_PILOT_END_DATE,
        help="Inclusive pilot end date. Default: 2025-05-30.",
    )
    parser.add_argument(
        "--universe-file",
        default=str(DEFAULT_UNIVERSE_FILE),
        help="Local TEJ-derived top-50 universe CSV.",
    )
    parser.add_argument(
        "--input-dir",
        action="append",
        required=True,
        help=(
            "GDELT chunk directory containing probe_summary.json and "
            "stock_day_counts.csv. Repeat for each selected chunk."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Ignored local output directory under data/processed/news/.",
    )
    args = parser.parse_args(argv)

    try:
        stock_week, weekly_totals, coverage_summary, summary, paths = (
            build_gdelt_weekly_counts(
                input_dirs=args.input_dir,
                universe_file=args.universe_file,
                output_dir=args.output_dir,
                pilot_start_date=args.pilot_start_date,
                pilot_end_date=args.pilot_end_date,
                repo_root=REPO_ROOT,
                write_files=True,
            )
        )
    except WeeklyCountAggregationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("Weekly GDELT news-count outputs written locally:")
    if paths is not None:
        print(f"- stock_week_counts: {paths.stock_week_counts}")
        print(f"- weekly_totals: {paths.weekly_totals}")
        print(f"- coverage_summary: {paths.coverage_summary}")
        print(f"- summary_json: {paths.summary_json}")
    print(f"rows: {len(stock_week)}")
    print(f"weekly_total_rows: {len(weekly_totals)}")
    print(f"coverage_summary_rows: {len(coverage_summary)}")
    print(f"validation_status: {summary['validation_status']}")
    print("hype_index_computed: false")
    print("market_cap_weights_joined: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
