"""Build local-only weekly Hype Index outputs for the 8-week pilot."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def _add_src_to_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))


_add_src_to_path()

from quant_finance_project.hype.index import (  # noqa: E402
    DEFAULT_INPUT_PANEL_FILE,
    DEFAULT_OUTPUT_DIR,
    HypeIndexError,
    build_hype_indices,
)
from quant_finance_project.hype.input_panel import (  # noqa: E402
    DEFAULT_PILOT_END_DATE,
    DEFAULT_PILOT_START_DATE,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compute weekly raw Hype and market-cap-adjusted Hype from the "
            "Goal 3B Hype-ready input panel."
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
        "--input-panel-file",
        default=str(DEFAULT_INPUT_PANEL_FILE),
        help="Goal 3B Hype-ready input-panel CSV.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Ignored local output directory under data/processed/hype_index/.",
    )
    args = parser.parse_args(argv)

    try:
        panel, weekly_summary, stock_summary, summary, paths = build_hype_indices(
            input_panel_file=args.input_panel_file,
            output_dir=args.output_dir,
            pilot_start_date=args.pilot_start_date,
            pilot_end_date=args.pilot_end_date,
            repo_root=REPO_ROOT,
            write_files=True,
        )
    except HypeIndexError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("Hype Index outputs written locally:")
    if paths is not None:
        print(f"- panel: {paths.panel}")
        print(f"- weekly_summary: {paths.weekly_summary}")
        print(f"- stock_summary: {paths.stock_summary}")
        print(f"- summary_json: {paths.summary_json}")
    print(f"rows: {len(panel)}")
    print(f"weeks: {summary['week_count']}")
    print(f"stocks: {summary['universe_size']}")
    print(f"weekly_summary_rows: {len(weekly_summary)}")
    print(f"stock_summary_rows: {len(stock_summary)}")
    print(f"validation_status: {summary['validation_status']}")
    print(f"missing_hype_week_count: {summary['missing_hype_week_count']}")
    print("hype_index_computed: true")
    print("market_cap_adjusted_hype_computed: true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
