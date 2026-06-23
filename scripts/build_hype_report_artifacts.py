"""Build report-ready artifacts from existing 8-week Hype Index outputs."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def _add_src_to_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))


_add_src_to_path()

from quant_finance_project.reporting.hype_report import (  # noqa: E402
    DEFAULT_COMPANY_METADATA_FILE,
    DEFAULT_DAILY_MARKET_PANEL_FILE,
    DEFAULT_FIGURE_DPI,
    DEFAULT_FIGURES_DIR,
    DEFAULT_HYPE_PANEL_FILE,
    DEFAULT_HYPE_SUMMARY_JSON,
    DEFAULT_HYPE_TRADING_END,
    DEFAULT_HYPE_TRADING_START,
    DEFAULT_KEY_TICKERS,
    DEFAULT_MARKET_BACKGROUND_END,
    DEFAULT_MARKET_BACKGROUND_START,
    DEFAULT_RAW_TEJ_RETURN_FILE,
    DEFAULT_RESULTS_DIR,
    DEFAULT_STOCK_SUMMARY_FILE,
    DEFAULT_TEJ_VALIDATION_JSON,
    DEFAULT_TOP_N,
    DEFAULT_UNIVERSE_FILE,
    DEFAULT_WEEKLY_SUMMARY_FILE,
    DEFAULT_WEEKLY_MARKET_WEIGHTS_FILE,
    HypeReportError,
    build_hype_report_artifacts,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build report-ready tables, figures, and objective visual-QA "
            "manifests from existing Goal 3C Hype Index outputs."
        )
    )
    parser.add_argument(
        "--hype-panel-file",
        default=str(DEFAULT_HYPE_PANEL_FILE),
        help="Existing Goal 3C stock-week Hype panel CSV.",
    )
    parser.add_argument(
        "--weekly-summary-file",
        default=str(DEFAULT_WEEKLY_SUMMARY_FILE),
        help="Existing Goal 3C weekly Hype summary CSV.",
    )
    parser.add_argument(
        "--stock-summary-file",
        default=str(DEFAULT_STOCK_SUMMARY_FILE),
        help="Existing Goal 3C stock Hype summary CSV.",
    )
    parser.add_argument(
        "--hype-summary-json",
        default=str(DEFAULT_HYPE_SUMMARY_JSON),
        help="Existing Goal 3C validation summary JSON.",
    )
    parser.add_argument(
        "--chunk-summary-json",
        action="append",
        default=[],
        help=(
            "Optional GDELT chunk probe_summary.json. Repeat this argument for "
            "multiple selected chunks."
        ),
    )
    parser.add_argument(
        "--include-market-quant",
        action="store_true",
        help="Also build Goal 4B TEJ market, sector, return, and volatility artifacts.",
    )
    parser.add_argument(
        "--daily-market-panel-file",
        default=str(DEFAULT_DAILY_MARKET_PANEL_FILE),
        help="Processed TEJ daily market panel CSV for Goal 4B.",
    )
    parser.add_argument(
        "--weekly-market-weights-file",
        default=str(DEFAULT_WEEKLY_MARKET_WEIGHTS_FILE),
        help="Processed TEJ weekly market-cap weights CSV for Goal 4B.",
    )
    parser.add_argument(
        "--universe-file",
        default=str(DEFAULT_UNIVERSE_FILE),
        help="TEJ-based fixed top-50 universe CSV for Goal 4B.",
    )
    parser.add_argument(
        "--company-metadata-file",
        default=str(DEFAULT_COMPANY_METADATA_FILE),
        help="TEJ company metadata CSV for Goal 4B.",
    )
    parser.add_argument(
        "--tej-validation-json",
        default=str(DEFAULT_TEJ_VALIDATION_JSON),
        help="Processed TEJ validation summary JSON for Goal 4B.",
    )
    parser.add_argument(
        "--raw-tej-return-file",
        default=str(DEFAULT_RAW_TEJ_RETURN_FILE),
        help="Local Big5 semicolon-separated TEJ adjusted return CSV for Goal 4B.",
    )
    parser.add_argument(
        "--market-background-start",
        default=DEFAULT_MARKET_BACKGROUND_START,
        help="One-year TEJ market-background start date.",
    )
    parser.add_argument(
        "--market-background-end",
        default=DEFAULT_MARKET_BACKGROUND_END,
        help="One-year TEJ market-background end date.",
    )
    parser.add_argument(
        "--hype-trading-start",
        default=DEFAULT_HYPE_TRADING_START,
        help="First TEJ trading date used for Hype-window market comparison.",
    )
    parser.add_argument(
        "--hype-trading-end",
        default=DEFAULT_HYPE_TRADING_END,
        help="Last TEJ trading date used for Hype-window market comparison.",
    )
    parser.add_argument(
        "--key-ticker",
        action="append",
        default=[],
        help=(
            "Ticker to include in key-stock case-study figures. Repeat for "
            "multiple tickers. Defaults to 2330, 2454, 2317, and 2357."
        ),
    )
    parser.add_argument(
        "--results-dir",
        default=str(DEFAULT_RESULTS_DIR),
        help="Report results output directory under report/results/.",
    )
    parser.add_argument(
        "--figures-dir",
        default=str(DEFAULT_FIGURES_DIR),
        help="Report figures output directory under report/figures/.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=DEFAULT_TOP_N,
        help="Number of stocks to include in top-stock tables and figures.",
    )
    parser.add_argument(
        "--figure-dpi",
        type=int,
        default=DEFAULT_FIGURE_DPI,
        help="PNG figure DPI. Must be at least 160.",
    )
    args = parser.parse_args(argv)

    try:
        paths = build_hype_report_artifacts(
            hype_panel_file=args.hype_panel_file,
            weekly_summary_file=args.weekly_summary_file,
            stock_summary_file=args.stock_summary_file,
            hype_summary_json=args.hype_summary_json,
            chunk_summary_json=args.chunk_summary_json,
            include_market_quant=args.include_market_quant,
            daily_market_panel_file=args.daily_market_panel_file,
            weekly_market_weights_file=args.weekly_market_weights_file,
            universe_file=args.universe_file,
            company_metadata_file=args.company_metadata_file,
            tej_validation_json=args.tej_validation_json,
            raw_tej_return_file=args.raw_tej_return_file,
            market_background_start=args.market_background_start,
            market_background_end=args.market_background_end,
            hype_trading_start=args.hype_trading_start,
            hype_trading_end=args.hype_trading_end,
            key_tickers=args.key_ticker or DEFAULT_KEY_TICKERS,
            results_dir=args.results_dir,
            figures_dir=args.figures_dir,
            top_n=args.top_n,
            figure_dpi=args.figure_dpi,
            repo_root=REPO_ROOT,
        )
    except HypeReportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("Hype report artifacts written:")
    print(f"- results_dir: {paths.results_dir}")
    print(f"- figures_dir: {paths.figures_dir}")
    print("- tables:")
    for name, (csv_path, md_path) in sorted(paths.table_paths.items()):
        print(f"  - {name}: {csv_path} | {md_path}")
    print(f"- methodology_notes: {paths.methodology_notes}")
    print("- figures:")
    for name, path in sorted(paths.figure_paths.items()):
        print(f"  - {name}: {path}")
    print(f"- figure_index_csv: {paths.figure_manifest_csv}")
    print(f"- figure_visual_qa_manifest_json: {paths.figure_manifest_json}")
    print(f"- figure_index_md: {paths.figure_index_md}")
    print(f"- artifact_manifest: {paths.artifact_manifest}")
    print("objective_visual_qa: passed")
    print("notebook_created: false")
    print("live_gdelt_downloads_run: false")
    print("goal_3_recomputation_performed: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
