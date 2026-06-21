"""Build the local-only Hype-ready 8-week input panel."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def _add_src_to_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))


_add_src_to_path()

from quant_finance_project.hype.input_panel import (  # noqa: E402
    DEFAULT_MARKET_WEIGHTS_FILE,
    DEFAULT_NEWS_COUNTS_FILE,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PILOT_END_DATE,
    DEFAULT_PILOT_START_DATE,
    DEFAULT_UNIVERSE_FILE,
    HypeInputPanelError,
    build_hype_input_panel,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Join local stock-week GDELT news counts with TEJ weekly "
            "market-cap weights. This does not compute a Hype Index."
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
        "--news-counts-file",
        default=str(DEFAULT_NEWS_COUNTS_FILE),
        help="Goal 3A stock-week news-count panel CSV.",
    )
    parser.add_argument(
        "--market-weights-file",
        default=str(DEFAULT_MARKET_WEIGHTS_FILE),
        help="TEJ weekly market-cap weight CSV.",
    )
    parser.add_argument(
        "--universe-file",
        default=str(DEFAULT_UNIVERSE_FILE),
        help="Local TEJ-derived top-50 universe CSV.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Ignored local output directory under data/processed/hype_index/.",
    )
    args = parser.parse_args(argv)

    try:
        panel, weekly_market_weight_summary, summary, paths = build_hype_input_panel(
            news_counts_file=args.news_counts_file,
            market_weights_file=args.market_weights_file,
            universe_file=args.universe_file,
            output_dir=args.output_dir,
            pilot_start_date=args.pilot_start_date,
            pilot_end_date=args.pilot_end_date,
            repo_root=REPO_ROOT,
            write_files=True,
        )
    except HypeInputPanelError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("Hype-ready input-panel outputs written locally:")
    if paths is not None:
        print(f"- panel: {paths.panel}")
        print(f"- weekly_market_weight_summary: {paths.weekly_market_weight_summary}")
        print(f"- summary_json: {paths.summary_json}")
    print(f"rows: {len(panel)}")
    print(f"weeks: {summary['week_count']}")
    print(f"stocks: {summary['universe_size']}")
    print(f"weekly_market_weight_summary_rows: {len(weekly_market_weight_summary)}")
    print(f"validation_status: {summary['validation_status']}")
    print("market_cap_weights_joined: true")
    print("hype_index_computed: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
