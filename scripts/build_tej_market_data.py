"""Build local-only TEJPro processed market-data outputs."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def main(argv: list[str] | None = None) -> int:
    """Run the TEJPro cleaning workflow from repository-root paths."""

    _add_src_to_path()
    from quant_finance_project.data.tej_market_data import (  # noqa: PLC0415
        DEFAULT_COMPANY_RAW_PATH,
        DEFAULT_MARKET_RAW_PATH,
        DEFAULT_OUTPUT_DIR,
        TejBuildConfig,
        TejValidationError,
        build_tej_market_data,
        build_tej_output_paths,
    )

    parser = argparse.ArgumentParser(
        description=(
            "Clean local TEJPro manual exports and write ignored processed "
            "outputs under data/processed/tej/."
        )
    )
    parser.add_argument("--company-raw", type=Path, default=DEFAULT_COMPANY_RAW_PATH)
    parser.add_argument("--market-raw", type=Path, default=DEFAULT_MARKET_RAW_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    missing = [path for path in (args.company_raw, args.market_raw) if not path.exists()]
    if missing:
        missing_text = "\n".join(f"- {path}" for path in missing)
        raise SystemExit(
            "Missing required local TEJPro raw file(s):\n"
            f"{missing_text}\n"
            "These licensed files are ignored by Git. Export them from TEJPro "
            "and place them under data/raw/tej/ before running this script."
        )

    config = TejBuildConfig(
        company_raw_path=args.company_raw,
        market_raw_path=args.market_raw,
        output_dir=args.output_dir,
    )

    try:
        result = build_tej_market_data(config)
    except TejValidationError as exc:
        summary_path = build_tej_output_paths(
            args.output_dir,
            constituent_as_of_date=config.constituent_as_of_date,
            panel_start_date=config.expected_start_date,
            panel_end_date=config.expected_end_date,
        )["validation_summary"]
        raise SystemExit(
            f"{exc}\nValidation summary was written to {summary_path}."
        ) from exc

    output_paths = result["output_paths"]
    print(f"Wrote local TEJ processed outputs under {args.output_dir}:")
    for key in (
        "company_metadata",
        "daily_market_panel",
        "top50_universe",
        "weekly_market_cap_weights",
        "validation_summary",
    ):
        print(f"- {output_paths[key]}")
    return 0


def _add_src_to_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_path = repo_root / "src"
    sys.path.insert(0, str(src_path))


if __name__ == "__main__":
    raise SystemExit(main())
