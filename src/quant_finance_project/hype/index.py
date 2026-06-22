"""Compute weekly Hype Index measures from a validated input panel.

The formulas follow the local reference paper's core definitions in
``references/local/arXiv-2506.06329v1`` and adapt them to this project's
weekly TEJ top-50 pilot:

* raw_hype = stock weekly news-count share within the fixed universe;
* market_cap_adjusted_hype = raw_hype / weekly market-cap weight.

This module does not create figures, notebooks, forecasts, or portfolio inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from quant_finance_project.hype.input_panel import (
    DEFAULT_PILOT_END_DATE,
    DEFAULT_PILOT_START_DATE,
    HypeInputPanelError,
    build_weekly_bins,
    resolve_repo_path,
)


DEFAULT_INPUT_PANEL_FILE = Path(
    "data/processed/hype_index/pilot_8w/hype_input_panel_20250405_20250530.csv"
)
DEFAULT_OUTPUT_DIR = Path("data/processed/hype_index/pilot_8w/indices")
ALLOWED_OUTPUT_ROOT = Path("data/processed/hype_index")
OUTPUT_DATE_LABEL = "20250405_20250530"
WEIGHT_SUM_TOLERANCE = 1e-8
RAW_HYPE_SUM_TOLERANCE = 1e-8
REQUIRED_INPUT_COLUMNS = [
    "ticker",
    "week_index",
    "week_start",
    "week_end",
    "news_count_unique_urls",
    "matched_rows",
    "active_news_days",
    "weekly_total_news_count_unique_urls",
    "weekly_market_cap_weight",
]
OPTIONAL_INPUT_COLUMNS = [
    "stock_id",
    "official_chinese_name",
    "official_english_name",
    "industry",
    "sector",
    "sector_group",
    "tse_industry",
    "tej_industry",
    "weight_date",
]
METADATA_COLUMNS = [
    "stock_id",
    "ticker",
    "official_chinese_name",
    "official_english_name",
    "industry",
    "sector",
    "sector_group",
    "tse_industry",
    "tej_industry",
]
FORBIDDEN_PREEXISTING_HYPE_COLUMNS = {
    "hype",
    "raw_hype",
    "hype_index",
    "adjusted_hype",
    "cap_adjusted_hype",
    "market_cap_adjusted_hype",
    "raw_hype_minus_market_cap_weight",
}


class HypeIndexError(RuntimeError):
    """Raised when Hype Index computation cannot proceed safely."""


@dataclass(frozen=True)
class HypeIndexOutputPaths:
    """Local output paths written by Goal 3C."""

    panel: Path
    weekly_summary: Path
    stock_summary: Path
    summary_json: Path


def validate_output_dir(output_dir: str | Path, *, repo_root: Path) -> Path:
    """Require Goal 3C outputs to stay under ignored local Hype data paths."""

    resolved = resolve_repo_path(output_dir, repo_root=repo_root).resolve(strict=False)
    allowed_root = (repo_root / ALLOWED_OUTPUT_ROOT).resolve(strict=False)
    if not (resolved == allowed_root or allowed_root in resolved.parents):
        raise HypeIndexError(
            f"Output directory must be under ignored local path {ALLOWED_OUTPUT_ROOT}."
        )
    return resolved


def _require_file(path: Path, *, label: str) -> None:
    if not path.is_file():
        raise HypeIndexError(f"Missing required {label}: {path}.")


def _require_columns(frame: pd.DataFrame, columns: Iterable[str], *, label: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise HypeIndexError(
            f"{label} is missing required column(s): {', '.join(missing)}."
        )


def _coerce_nonnegative_integer(
    frame: pd.DataFrame,
    column: str,
    *,
    label: str,
) -> None:
    try:
        values = pd.to_numeric(frame[column], errors="raise")
    except (TypeError, ValueError) as exc:
        raise HypeIndexError(
            f"{label} has invalid integer value(s) in {column}."
        ) from exc
    if values.isna().any():
        raise HypeIndexError(f"{label} has missing value(s) in {column}.")
    finite = values.map(math.isfinite)
    if not finite.all():
        raise HypeIndexError(f"{label} has non-finite value(s) in {column}.")
    integral = values.eq(values.round())
    if not integral.all():
        raise HypeIndexError(f"{label} has non-integral value(s) in {column}.")
    if (values < 0).any():
        raise HypeIndexError(f"{label} has negative value(s) in {column}.")
    frame[column] = values.astype(int)


def _coerce_positive_float(frame: pd.DataFrame, column: str, *, label: str) -> None:
    try:
        values = pd.to_numeric(frame[column], errors="raise").astype(float)
    except (TypeError, ValueError) as exc:
        raise HypeIndexError(
            f"{label} has invalid numeric value(s) in {column}."
        ) from exc
    if values.isna().any():
        raise HypeIndexError(f"{label} has missing value(s) in {column}.")
    if (values <= 0).any():
        raise HypeIndexError(f"{label} has nonpositive value(s) in {column}.")
    frame[column] = values


def _canonical_week_lookup(weekly_bins: pd.DataFrame) -> pd.DataFrame:
    return weekly_bins[["week_index", "week_start", "week_end"]].copy()


def _metadata_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in METADATA_COLUMNS if column in frame.columns]


def load_and_validate_input_panel(
    input_panel_file: str | Path,
    *,
    repo_root: Path,
    weekly_bins: pd.DataFrame,
) -> pd.DataFrame:
    """Load and validate the Goal 3B Hype-ready input panel."""

    path = resolve_repo_path(input_panel_file, repo_root=repo_root)
    _require_file(path, label="Hype-ready input panel")
    panel = pd.read_csv(path, dtype=str).fillna("")
    _require_columns(panel, REQUIRED_INPUT_COLUMNS, label="Hype-ready input panel")

    forbidden = FORBIDDEN_PREEXISTING_HYPE_COLUMNS & set(panel.columns)
    if forbidden:
        raise HypeIndexError(
            "Input panel already contains Hype output column(s): "
            + ", ".join(sorted(forbidden))
        )

    for column in [
        *OPTIONAL_INPUT_COLUMNS,
        *REQUIRED_INPUT_COLUMNS,
    ]:
        if column in panel.columns:
            panel[column] = panel[column].astype(str).str.strip()

    for column in (
        "week_index",
        "news_count_unique_urls",
        "matched_rows",
        "active_news_days",
        "weekly_total_news_count_unique_urls",
    ):
        _coerce_nonnegative_integer(panel, column, label="Hype-ready input panel")
    if (panel["active_news_days"] > 7).any():
        raise HypeIndexError(
            "Hype-ready input panel has active_news_days outside the 0 to 7 range."
        )
    _coerce_positive_float(
        panel,
        "weekly_market_cap_weight",
        label="Hype-ready input panel",
    )

    week_lookup = _canonical_week_lookup(weekly_bins)
    expected_weeks = set(week_lookup["week_end"])
    observed_weeks = set(panel["week_end"].unique())
    if observed_weeks != expected_weeks:
        missing_weeks = sorted(expected_weeks - observed_weeks)
        extra_weeks = sorted(observed_weeks - expected_weeks)
        raise HypeIndexError(
            "Hype-ready input panel week_end values do not match the pilot window. "
            f"missing={missing_weeks}; extra={extra_weeks}."
        )

    universe_size = int(panel["ticker"].nunique())
    week_count = int(len(weekly_bins))
    duplicated = panel.duplicated(["ticker", "week_end"], keep=False)
    if duplicated.any():
        examples = panel.loc[duplicated, ["ticker", "week_end"]].head(10)
        raise HypeIndexError(
            "Hype-ready input panel has duplicate ticker-week row(s): "
            + json.dumps(examples.to_dict(orient="records"), ensure_ascii=False)
        )

    expected_rows = universe_size * week_count
    if len(panel) != expected_rows:
        raise HypeIndexError(
            f"Hype-ready input panel has {len(panel)} rows; expected {expected_rows}."
        )
    if universe_size <= 0:
        raise HypeIndexError("Hype-ready input panel contains no ticker rows.")

    rows_by_week = panel.groupby("week_end")["ticker"].count()
    bad_week_counts = rows_by_week.loc[rows_by_week.ne(universe_size)]
    if not bad_week_counts.empty:
        raise HypeIndexError(
            f"Hype-ready input panel must have {universe_size} rows per week; "
            f"bad weeks={bad_week_counts.to_dict()}."
        )

    panel = panel.merge(
        week_lookup.rename(
            columns={
                "week_index": "_canonical_week_index",
                "week_start": "_canonical_week_start",
            }
        ),
        on="week_end",
        how="left",
        validate="many_to_one",
    )
    mismatched_week_labels = panel.loc[
        panel["week_index"].ne(panel["_canonical_week_index"])
        | panel["week_start"].ne(panel["_canonical_week_start"])
    ]
    if not mismatched_week_labels.empty:
        examples = mismatched_week_labels[
            ["ticker", "week_index", "week_start", "week_end"]
        ].head(10)
        raise HypeIndexError(
            "Hype-ready input panel has stale week_index/week_start values: "
            + json.dumps(examples.to_dict(orient="records"), ensure_ascii=False)
        )
    panel = panel.drop(columns=["_canonical_week_index", "_canonical_week_start"])

    weight_sums = panel.groupby("week_end")["weekly_market_cap_weight"].sum()
    bad_weight_sums = weight_sums.loc[
        (weight_sums - 1.0).abs().gt(WEIGHT_SUM_TOLERANCE)
    ]
    if not bad_weight_sums.empty:
        raise HypeIndexError(
            "weekly_market_cap_weight must sum to 1 within tolerance by week; "
            f"bad sums={bad_weight_sums.to_dict()}."
        )

    weekly_news = panel.groupby("week_end")["news_count_unique_urls"].transform("sum")
    if (weekly_news <= 0).any():
        bad_weeks = sorted(panel.loc[weekly_news <= 0, "week_end"].unique().tolist())
        raise HypeIndexError(
            "weekly_total_news_count_unique_urls must be positive for each week; "
            f"zero-total week(s): {', '.join(bad_weeks)}."
        )

    total_values_by_week = panel.groupby("week_end")[
        "weekly_total_news_count_unique_urls"
    ].nunique()
    inconsistent_weekly_totals = total_values_by_week.loc[total_values_by_week.ne(1)]
    if not inconsistent_weekly_totals.empty:
        raise HypeIndexError(
            "weekly_total_news_count_unique_urls must be constant within each week; "
            f"bad weeks={inconsistent_weekly_totals.to_dict()}."
        )

    observed_weekly_total = panel.groupby("week_end")[
        "weekly_total_news_count_unique_urls"
    ].transform("first")
    mismatched_totals = panel.loc[observed_weekly_total.ne(weekly_news)]
    if not mismatched_totals.empty:
        examples = (
            mismatched_totals[
                ["week_index", "week_start", "week_end", "weekly_total_news_count_unique_urls"]
            ]
            .drop_duplicates()
            .head(10)
        )
        raise HypeIndexError(
            "weekly_total_news_count_unique_urls conflicts with weekly "
            "news_count_unique_urls sums: "
            + json.dumps(examples.to_dict(orient="records"), ensure_ascii=False)
        )
    panel["weekly_total_news_count_unique_urls"] = weekly_news.astype(int)

    return panel.sort_values(["ticker", "week_index"], kind="stable").reset_index(
        drop=True
    )


def compute_hype_indices(input_panel: pd.DataFrame) -> pd.DataFrame:
    """Compute raw Hype and capitalization-adjusted Hype for each stock-week."""

    panel = input_panel.copy()
    panel["raw_hype"] = (
        panel["news_count_unique_urls"] / panel["weekly_total_news_count_unique_urls"]
    )
    panel["market_cap_adjusted_hype"] = (
        panel["raw_hype"] / panel["weekly_market_cap_weight"]
    )
    panel["raw_hype_minus_market_cap_weight"] = (
        panel["raw_hype"] - panel["weekly_market_cap_weight"]
    )
    panel["is_zero_news_stock_week"] = panel["news_count_unique_urls"].eq(0)
    validate_hype_outputs(panel)

    output_columns = [
        *_metadata_columns(panel),
        "week_index",
        "week_start",
        "week_end",
        "weight_date",
        "news_count_unique_urls",
        "matched_rows",
        "active_news_days",
        "weekly_total_news_count_unique_urls",
        "weekly_market_cap_weight",
        "raw_hype",
        "market_cap_adjusted_hype",
        "raw_hype_minus_market_cap_weight",
        "is_zero_news_stock_week",
    ]
    output_columns = [column for column in output_columns if column in panel.columns]
    return panel[output_columns].sort_values(["ticker", "week_index"], kind="stable")


def validate_hype_outputs(panel: pd.DataFrame) -> None:
    """Validate computed Hype Index outputs."""

    for column in ("raw_hype", "market_cap_adjusted_hype"):
        if (panel[column] < 0).any():
            raise HypeIndexError(f"{column} must be nonnegative.")
        finite = panel[column].map(math.isfinite)
        if not finite.all():
            raise HypeIndexError(f"{column} contains NaN or infinite value(s).")

    raw_sums = panel.groupby("week_end")["raw_hype"].sum()
    bad_raw_sums = raw_sums.loc[(raw_sums - 1.0).abs().gt(RAW_HYPE_SUM_TOLERANCE)]
    if not bad_raw_sums.empty:
        raise HypeIndexError(
            "raw_hype must sum to 1 within tolerance by week; "
            f"bad sums={bad_raw_sums.to_dict()}."
        )

    zero_news = panel["news_count_unique_urls"].eq(0)
    if not panel.loc[zero_news, "raw_hype"].eq(0).all():
        raise HypeIndexError("Zero-news stock-week rows must have raw_hype=0.")
    if not panel.loc[zero_news, "market_cap_adjusted_hype"].eq(0).all():
        raise HypeIndexError(
            "Zero-news stock-week rows must have market_cap_adjusted_hype=0."
        )


def _ticker_with_max(group: pd.DataFrame, column: str) -> str:
    ordered = group.sort_values([column, "ticker"], ascending=[False, True])
    return str(ordered.iloc[0]["ticker"])


def build_weekly_hype_summary(panel: pd.DataFrame) -> pd.DataFrame:
    """Build per-week Hype Index diagnostics."""

    rows: list[dict[str, Any]] = []
    for (week_index, week_start, week_end), group in panel.groupby(
        ["week_index", "week_start", "week_end"],
        sort=True,
    ):
        rows.append(
            {
                "week_index": int(week_index),
                "week_start": week_start,
                "week_end": week_end,
                "weekly_total_news_count_unique_urls": int(
                    group["news_count_unique_urls"].sum()
                ),
                "nonzero_stock_count": int(
                    group["news_count_unique_urls"].gt(0).sum()
                ),
                "zero_stock_count": int(group["news_count_unique_urls"].eq(0).sum()),
                "max_raw_hype": float(group["raw_hype"].max()),
                "ticker_with_max_raw_hype": _ticker_with_max(group, "raw_hype"),
                "max_market_cap_adjusted_hype": float(
                    group["market_cap_adjusted_hype"].max()
                ),
                "ticker_with_max_market_cap_adjusted_hype": _ticker_with_max(
                    group,
                    "market_cap_adjusted_hype",
                ),
                "raw_hype_sum": float(group["raw_hype"].sum()),
                "market_cap_weight_sum": float(
                    group["weekly_market_cap_weight"].sum()
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("week_index", kind="stable")


def build_stock_hype_summary(panel: pd.DataFrame) -> pd.DataFrame:
    """Build per-stock Hype Index diagnostics."""

    group_columns = _metadata_columns(panel)
    grouped = (
        panel.groupby(group_columns, as_index=False, dropna=False)
        .agg(
            total_news_count_unique_urls=("news_count_unique_urls", "sum"),
            nonzero_week_count=("news_count_unique_urls", lambda values: int((values > 0).sum())),
            zero_week_count=("news_count_unique_urls", lambda values: int((values == 0).sum())),
            mean_raw_hype=("raw_hype", "mean"),
            max_raw_hype=("raw_hype", "max"),
            mean_market_cap_adjusted_hype=("market_cap_adjusted_hype", "mean"),
            max_market_cap_adjusted_hype=("market_cap_adjusted_hype", "max"),
            mean_weekly_market_cap_weight=("weekly_market_cap_weight", "mean"),
        )
        .sort_values("ticker", kind="stable")
        .reset_index(drop=True)
    )
    return grouped


def _json_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records = frame.to_dict(orient="records")
    return [
        {
            key: (value.item() if hasattr(value, "item") else value)
            for key, value in row.items()
        }
        for row in records
    ]


def build_summary(
    *,
    pilot_start_date: str,
    pilot_end_date: str,
    input_panel_file: str | Path,
    panel: pd.DataFrame,
    weekly_summary: pd.DataFrame,
) -> dict[str, Any]:
    """Build a JSON-serializable Goal 3C validation summary."""

    universe_size = int(panel["ticker"].nunique())
    week_count = int(panel["week_end"].nunique())
    actual_rows = int(len(panel))
    expected_rows = int(universe_size * week_count)
    zero_count = int(panel["is_zero_news_stock_week"].sum())
    return {
        "pilot_start_date": pilot_start_date,
        "pilot_end_date": pilot_end_date,
        "week_count": week_count,
        "universe_size": universe_size,
        "expected_rows": expected_rows,
        "actual_rows": actual_rows,
        "input_panel_file": str(input_panel_file),
        "total_news_count_unique_urls": int(panel["news_count_unique_urls"].sum()),
        "zero_stock_week_count": zero_count,
        "zero_stock_week_ratio": round(zero_count / actual_rows, 6)
        if actual_rows
        else None,
        "weekly_raw_hype_sum_check": _json_records(
            weekly_summary[["week_index", "week_end", "raw_hype_sum"]]
        ),
        "weekly_market_cap_weight_sum_check": _json_records(
            weekly_summary[["week_index", "week_end", "market_cap_weight_sum"]]
        ),
        "hype_index_computed": True,
        "market_cap_adjusted_hype_computed": True,
        "validation_status": "passed"
        if actual_rows == expected_rows
        else "failed_row_count_mismatch",
    }


def output_paths(output_dir: Path, *, label: str = OUTPUT_DATE_LABEL) -> HypeIndexOutputPaths:
    """Return the standard local output paths for a date label."""

    return HypeIndexOutputPaths(
        panel=output_dir / f"hype_index_panel_{label}.csv",
        weekly_summary=output_dir / f"weekly_hype_summary_{label}.csv",
        stock_summary=output_dir / f"stock_hype_summary_{label}.csv",
        summary_json=output_dir / f"hype_index_summary_{label}.json",
    )


def write_outputs(
    *,
    output_dir: Path,
    panel: pd.DataFrame,
    weekly_summary: pd.DataFrame,
    stock_summary: pd.DataFrame,
    summary: dict[str, Any],
    label: str = OUTPUT_DATE_LABEL,
) -> HypeIndexOutputPaths:
    """Write local-only Goal 3C outputs."""

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = output_paths(output_dir, label=label)
    panel.to_csv(paths.panel, index=False)
    weekly_summary.to_csv(paths.weekly_summary, index=False)
    stock_summary.to_csv(paths.stock_summary, index=False)
    paths.summary_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return paths


def build_hype_indices(
    *,
    input_panel_file: str | Path = DEFAULT_INPUT_PANEL_FILE,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    pilot_start_date: str = DEFAULT_PILOT_START_DATE,
    pilot_end_date: str = DEFAULT_PILOT_END_DATE,
    repo_root: Path = Path.cwd(),
    write_files: bool = True,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, Any],
    HypeIndexOutputPaths | None,
]:
    """Build weekly raw and market-cap-adjusted Hype Index outputs."""

    try:
        weekly_bins = build_weekly_bins(pilot_start_date, pilot_end_date)
    except HypeInputPanelError as exc:
        raise HypeIndexError(f"Invalid pilot window: {exc}") from exc
    input_panel = load_and_validate_input_panel(
        input_panel_file,
        repo_root=repo_root,
        weekly_bins=weekly_bins,
    )
    panel = compute_hype_indices(input_panel)
    weekly_summary = build_weekly_hype_summary(panel)
    stock_summary = build_stock_hype_summary(panel)
    summary = build_summary(
        pilot_start_date=pilot_start_date,
        pilot_end_date=pilot_end_date,
        input_panel_file=resolve_repo_path(input_panel_file, repo_root=repo_root),
        panel=panel,
        weekly_summary=weekly_summary,
    )

    paths = None
    if write_files:
        resolved_output_dir = validate_output_dir(output_dir, repo_root=repo_root)
        label = (
            pilot_start_date.replace("-", "")
            + "_"
            + pilot_end_date.replace("-", "")
        )
        paths = write_outputs(
            output_dir=resolved_output_dir,
            panel=panel,
            weekly_summary=weekly_summary,
            stock_summary=stock_summary,
            summary=summary,
            label=label,
        )
    return panel, weekly_summary, stock_summary, summary, paths
