"""Build local-only Hype-ready input panels.

This module joins the Goal 3A stock-week news-count panel with TEJ weekly
market-cap weights. It deliberately does not compute raw Hype, capitalization-
adjusted Hype, or any denominator ratios.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


DEFAULT_PILOT_START_DATE = "2025-04-05"
DEFAULT_PILOT_END_DATE = "2025-05-30"
DEFAULT_NEWS_COUNTS_FILE = Path(
    "data/processed/news/gdelt_pilot_8w/weekly_counts/"
    "stock_week_news_counts_20250405_20250530.csv"
)
DEFAULT_MARKET_WEIGHTS_FILE = Path(
    "data/processed/tej/weekly_market_cap_weights_20250401_20260331.csv"
)
DEFAULT_UNIVERSE_FILE = Path("data/processed/tej/top50_universe_20250331.csv")
DEFAULT_OUTPUT_DIR = Path("data/processed/hype_index/pilot_8w")
ALLOWED_OUTPUT_ROOT = Path("data/processed/hype_index")
OUTPUT_DATE_LABEL = "20250405_20250530"
WEIGHT_SUM_TOLERANCE = 1e-8
UNIVERSE_METADATA_COLUMNS = [
    "stock_id",
    "ticker",
    "official_chinese_name",
    "official_english_name",
    "industry",
]
OPTIONAL_UNIVERSE_METADATA_COLUMNS = [
    "sector",
    "sector_group",
    "tse_industry",
    "tej_industry",
]
NEWS_COUNT_COLUMNS = [
    "week_start",
    "week_end",
    "news_count_unique_urls",
    "matched_rows",
    "active_news_days",
]
MARKET_WEIGHT_COLUMNS = [
    "week_end",
    "weight_date",
    "stock_id",
    "ticker",
    "market_cap",
    "weekly_market_cap_weight",
]
FORBIDDEN_HYPE_COLUMNS = {
    "hype",
    "raw_hype",
    "hype_index",
    "adjusted_hype",
    "cap_adjusted_hype",
    "market_cap_adjusted_hype",
}


class HypeInputPanelError(RuntimeError):
    """Raised when the Hype-ready input panel cannot be built safely."""


@dataclass(frozen=True)
class HypeInputPanelPaths:
    """Local output paths written by Goal 3B."""

    panel: Path
    summary_json: Path
    weekly_market_weight_summary: Path


def parse_iso_date(value: str) -> date:
    """Parse a YYYY-MM-DD date for the pilot window."""

    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise HypeInputPanelError(
            f"Invalid date {value!r}; expected YYYY-MM-DD."
        ) from exc


def resolve_repo_path(path: str | Path, *, repo_root: Path) -> Path:
    """Resolve an absolute or repository-relative path."""

    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return repo_root / candidate


def validate_output_dir(output_dir: str | Path, *, repo_root: Path) -> Path:
    """Require Goal 3B outputs to stay under ignored local Hype data paths."""

    resolved = resolve_repo_path(output_dir, repo_root=repo_root).resolve(strict=False)
    allowed_root = (repo_root / ALLOWED_OUTPUT_ROOT).resolve(strict=False)
    if not (resolved == allowed_root or allowed_root in resolved.parents):
        raise HypeInputPanelError(
            f"Output directory must be under ignored local path {ALLOWED_OUTPUT_ROOT}."
        )
    return resolved


def _require_file(path: Path, *, label: str) -> None:
    if not path.is_file():
        raise HypeInputPanelError(f"Missing required {label}: {path}.")


def _require_columns(frame: pd.DataFrame, columns: Iterable[str], *, label: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise HypeInputPanelError(
            f"{label} is missing required column(s): {', '.join(missing)}."
        )


def _universe_metadata_columns(frame: pd.DataFrame) -> list[str]:
    columns = [
        *UNIVERSE_METADATA_COLUMNS,
        *OPTIONAL_UNIVERSE_METADATA_COLUMNS,
    ]
    return [column for column in columns if column in frame.columns]


def _parse_date_column(
    frame: pd.DataFrame,
    column: str,
    *,
    label: str,
) -> pd.Series:
    try:
        return pd.to_datetime(
            frame[column].astype(str).str.strip(),
            format="%Y-%m-%d",
            errors="raise",
        ).dt.date
    except ValueError as exc:
        raise HypeInputPanelError(
            f"{label} has invalid {column} value(s); expected YYYY-MM-DD."
        ) from exc


def _coerce_nonnegative_integer(
    frame: pd.DataFrame,
    column: str,
    *,
    label: str,
) -> None:
    try:
        values = pd.to_numeric(frame[column], errors="raise").astype(int)
    except (TypeError, ValueError) as exc:
        raise HypeInputPanelError(
            f"{label} has invalid integer value(s) in {column}."
        ) from exc
    if (values < 0).any():
        raise HypeInputPanelError(f"{label} has negative value(s) in {column}.")
    frame[column] = values


def _coerce_positive_float(frame: pd.DataFrame, column: str, *, label: str) -> None:
    try:
        values = pd.to_numeric(frame[column], errors="raise").astype(float)
    except (TypeError, ValueError) as exc:
        raise HypeInputPanelError(
            f"{label} has invalid numeric value(s) in {column}."
        ) from exc
    if (values <= 0).any():
        raise HypeInputPanelError(f"{label} has nonpositive value(s) in {column}.")
    frame[column] = values


def load_universe(universe_file: str | Path, *, repo_root: Path) -> pd.DataFrame:
    """Load and validate the fixed top-50 universe table."""

    path = resolve_repo_path(universe_file, repo_root=repo_root)
    _require_file(path, label="universe file")
    universe = pd.read_csv(path, dtype=str).fillna("")
    _require_columns(universe, ["ticker"], label="universe file")

    for column in UNIVERSE_METADATA_COLUMNS:
        if column not in universe.columns:
            universe[column] = ""
    metadata_columns = _universe_metadata_columns(universe)
    universe = universe[metadata_columns].copy()
    for column in metadata_columns:
        universe[column] = universe[column].astype(str).str.strip()

    universe = universe.loc[universe["ticker"] != ""].reset_index(drop=True)
    if universe.empty:
        raise HypeInputPanelError("Universe file contains no ticker rows.")
    duplicate_tickers = sorted(
        universe.loc[universe["ticker"].duplicated(), "ticker"].unique().tolist()
    )
    if duplicate_tickers:
        raise HypeInputPanelError(
            "Universe file contains duplicate ticker(s): "
            + ", ".join(duplicate_tickers)
        )
    return universe


def build_weekly_bins(
    pilot_start_date: str,
    pilot_end_date: str,
) -> pd.DataFrame:
    """Build Saturday-to-Friday weekly bins for an inclusive pilot window."""

    start = parse_iso_date(pilot_start_date)
    end = parse_iso_date(pilot_end_date)
    if start > end:
        raise HypeInputPanelError("pilot_start_date must be on or before end.")
    if start.weekday() != 5:
        raise HypeInputPanelError("pilot_start_date must be a Saturday.")
    if end.weekday() != 4:
        raise HypeInputPanelError("pilot_end_date must be a Friday.")

    day_count = (end - start).days + 1
    if day_count % 7 != 0:
        raise HypeInputPanelError(
            "Pilot window must contain complete Saturday-to-Friday weeks."
        )

    rows: list[dict[str, str | int]] = []
    current = start
    for week_index in range(1, day_count // 7 + 1):
        week_end = current + timedelta(days=6)
        rows.append(
            {
                "week_index": week_index,
                "week_start": current.isoformat(),
                "week_end": week_end.isoformat(),
            }
        )
        current += timedelta(days=7)
    return pd.DataFrame(rows)


def load_and_validate_news_counts(
    news_counts_file: str | Path,
    *,
    repo_root: Path,
    universe_tickers: set[str],
    weekly_bins: pd.DataFrame,
) -> pd.DataFrame:
    """Load the Goal 3A stock-week news-count panel and validate coverage."""

    path = resolve_repo_path(news_counts_file, repo_root=repo_root)
    _require_file(path, label="news-count panel")
    news = pd.read_csv(path, dtype=str).fillna("")
    if "ticker" not in news.columns and "matched_ticker" in news.columns:
        news = news.rename(columns={"matched_ticker": "ticker"})
    _require_columns(news, ["ticker", *NEWS_COUNT_COLUMNS], label="news-count panel")

    for column in news.columns:
        if column in {"ticker", "stock_id", "week_start", "week_end"}:
            news[column] = news[column].astype(str).str.strip()

    week_start_by_end = dict(zip(weekly_bins["week_end"], weekly_bins["week_start"]))
    week_index_by_end = dict(zip(weekly_bins["week_end"], weekly_bins["week_index"]))
    expected_weeks = set(weekly_bins["week_end"])
    universe_size = len(universe_tickers)
    expected_rows = universe_size * len(weekly_bins)

    if len(news) != expected_rows:
        raise HypeInputPanelError(
            f"News-count panel has {len(news)} rows; expected {expected_rows}."
        )
    if news["ticker"].nunique() != universe_size:
        raise HypeInputPanelError(
            "News-count panel ticker count does not match the universe size."
        )
    if set(news["week_end"].unique()) != expected_weeks:
        missing_weeks = sorted(expected_weeks - set(news["week_end"].unique()))
        extra_weeks = sorted(set(news["week_end"].unique()) - expected_weeks)
        raise HypeInputPanelError(
            "News-count panel week_end values do not match the pilot window. "
            f"missing={missing_weeks}; extra={extra_weeks}."
        )
    if news["week_end"].nunique() != len(weekly_bins):
        raise HypeInputPanelError("News-count panel week count mismatch.")

    duplicated = news.duplicated(["ticker", "week_end"], keep=False)
    if duplicated.any():
        examples = news.loc[duplicated, ["ticker", "week_end"]].head(10)
        raise HypeInputPanelError(
            "News-count panel has duplicate ticker-week row(s): "
            + json.dumps(examples.to_dict(orient="records"), ensure_ascii=False)
        )

    unknown_tickers = sorted(set(news["ticker"]) - universe_tickers)
    if unknown_tickers:
        raise HypeInputPanelError(
            "News-count panel has ticker(s) outside the universe: "
            + ", ".join(unknown_tickers)
        )

    news["_week_start_date"] = _parse_date_column(
        news,
        "week_start",
        label="news-count panel",
    )
    news["_week_end_date"] = _parse_date_column(
        news,
        "week_end",
        label="news-count panel",
    )
    pilot_start = parse_iso_date(str(weekly_bins["week_start"].iloc[0]))
    pilot_end = parse_iso_date(str(weekly_bins["week_end"].iloc[-1]))
    outside = news.loc[
        (news["_week_start_date"] < pilot_start)
        | (news["_week_end_date"] > pilot_end)
    ]
    if not outside.empty:
        raise HypeInputPanelError(
            "News-count panel has week_start/week_end outside the pilot window."
        )

    bad_start = news.loc[
        news["week_start"].ne(news["week_end"].map(week_start_by_end))
    ]
    if not bad_start.empty:
        raise HypeInputPanelError(
            "News-count panel week_start values do not match Saturday-to-Friday bins."
        )
    canonical_week_index = news["week_end"].map(week_index_by_end).astype(int)
    if "week_index" in news.columns:
        try:
            observed_week_index = pd.to_numeric(
                news["week_index"],
                errors="raise",
            ).astype(int)
        except (TypeError, ValueError) as exc:
            raise HypeInputPanelError(
                "News-count panel has invalid week_index value(s)."
            ) from exc
        mismatched_week_index = news.loc[observed_week_index.ne(canonical_week_index)]
        if not mismatched_week_index.empty:
            examples = mismatched_week_index[
                ["ticker", "week_start", "week_end", "week_index"]
            ].head(10)
            raise HypeInputPanelError(
                "News-count panel week_index values do not match canonical "
                "Saturday-to-Friday bins: "
                + json.dumps(examples.to_dict(orient="records"), ensure_ascii=False)
            )
    news["week_index"] = canonical_week_index

    rows_by_week = news.groupby("week_end")["ticker"].count()
    bad_week_counts = rows_by_week.loc[rows_by_week.ne(universe_size)]
    if not bad_week_counts.empty:
        raise HypeInputPanelError(
            f"News-count panel must have {universe_size} rows per week; "
            f"bad weeks={bad_week_counts.to_dict()}."
        )

    for column in (
        "news_count_unique_urls",
        "matched_rows",
        "active_news_days",
    ):
        _coerce_nonnegative_integer(news, column, label="news-count panel")
    if (news["active_news_days"] > 7).any():
        raise HypeInputPanelError(
            "News-count panel has active_news_days outside the 0 to 7 range."
        )

    return news.drop(columns=["_week_start_date", "_week_end_date"])


def load_and_validate_market_weights(
    market_weights_file: str | Path,
    *,
    repo_root: Path,
    universe_tickers: set[str],
    weekly_bins: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load TEJ weekly weights for the pilot weeks and validate the schema."""

    path = resolve_repo_path(market_weights_file, repo_root=repo_root)
    _require_file(path, label="market-weight file")
    weights = pd.read_csv(path, dtype=str).fillna("")
    _require_columns(weights, MARKET_WEIGHT_COLUMNS, label="market-weight file")
    for column in ("week_end", "weight_date", "stock_id", "ticker"):
        weights[column] = weights[column].astype(str).str.strip()

    weekly_lookup = weekly_bins[["week_start", "week_end"]].copy()
    expected_weeks = set(weekly_lookup["week_end"])
    weights = weights.loc[weights["week_end"].isin(expected_weeks)].copy()
    if weights.empty:
        raise HypeInputPanelError(
            "Market-weight file contains no rows for the selected pilot weeks."
        )

    observed_weeks = set(weights["week_end"].unique())
    if observed_weeks != expected_weeks:
        missing_weeks = sorted(expected_weeks - observed_weeks)
        extra_weeks = sorted(observed_weeks - expected_weeks)
        raise HypeInputPanelError(
            "Market-weight week_end values do not match the news-count panel. "
            f"missing={missing_weeks}; extra={extra_weeks}."
        )

    duplicated = weights.duplicated(["ticker", "week_end"], keep=False)
    if duplicated.any():
        examples = weights.loc[duplicated, ["ticker", "week_end"]].head(10)
        raise HypeInputPanelError(
            "Market-weight file has duplicate ticker-week row(s): "
            + json.dumps(examples.to_dict(orient="records"), ensure_ascii=False)
        )

    unknown_tickers = sorted(set(weights["ticker"]) - universe_tickers)
    if unknown_tickers:
        raise HypeInputPanelError(
            "Market-weight file has ticker(s) outside the universe: "
            + ", ".join(unknown_tickers)
        )

    universe_size = len(universe_tickers)
    rows_by_week = weights.groupby("week_end")["ticker"].count()
    bad_week_counts = rows_by_week.loc[rows_by_week.ne(universe_size)]
    if not bad_week_counts.empty:
        raise HypeInputPanelError(
            f"Market weights must have {universe_size} rows per selected week; "
            f"bad weeks={bad_week_counts.to_dict()}."
        )

    for column in ("market_cap", "weekly_market_cap_weight"):
        _coerce_positive_float(weights, column, label="market-weight file")

    weight_sums = weights.groupby("week_end")["weekly_market_cap_weight"].sum()
    bad_sums = weight_sums.loc[(weight_sums - 1.0).abs().gt(WEIGHT_SUM_TOLERANCE)]
    if not bad_sums.empty:
        raise HypeInputPanelError(
            "Market weights must sum to 1 within tolerance by week; "
            f"bad sums={bad_sums.to_dict()}."
        )

    weights = weights.merge(weekly_lookup, on="week_end", how="left")
    weights["_week_start_date"] = _parse_date_column(
        weights,
        "week_start",
        label="market-weight file",
    )
    weights["_week_end_date"] = _parse_date_column(
        weights,
        "week_end",
        label="market-weight file",
    )
    weights["_weight_date"] = _parse_date_column(
        weights,
        "weight_date",
        label="market-weight file",
    )
    outside_bin = weights.loc[
        (weights["_weight_date"] < weights["_week_start_date"])
        | (weights["_weight_date"] > weights["_week_end_date"])
    ]
    if not outside_bin.empty:
        examples = outside_bin[["ticker", "week_start", "week_end", "weight_date"]]
        raise HypeInputPanelError(
            "Market-weight weight_date must be inside the corresponding "
            "Saturday-to-Friday week: "
            + json.dumps(
                examples.head(10).to_dict(orient="records"),
                ensure_ascii=False,
            )
        )
    if (weights["_weight_date"] > weights["_week_end_date"]).any():
        raise HypeInputPanelError("Market-weight weight_date must be <= week_end.")

    weight_dates_by_week = weights.groupby("week_end")["weight_date"].nunique()
    inconsistent_dates = weight_dates_by_week.loc[weight_dates_by_week.ne(1)]
    if not inconsistent_dates.empty:
        raise HypeInputPanelError(
            "Market-weight file must use one TEJ weight_date per week; "
            f"bad weeks={inconsistent_dates.to_dict()}."
        )

    weights = weights.drop(columns=["_week_start_date", "_week_end_date", "_weight_date"])
    weight_summary = build_weekly_market_weight_summary(weights)
    return weights, weight_summary


def build_weekly_market_weight_summary(weights: pd.DataFrame) -> pd.DataFrame:
    """Summarize selected TEJ weekly market-cap weights by week."""

    return (
        weights.groupby(["week_start", "week_end", "weight_date"], as_index=False)
        .agg(
            ticker_count=("ticker", "nunique"),
            market_cap_total=("market_cap", "sum"),
            market_cap_weight_sum=("weekly_market_cap_weight", "sum"),
            min_market_cap_weight=("weekly_market_cap_weight", "min"),
            max_market_cap_weight=("weekly_market_cap_weight", "max"),
        )
        .sort_values("week_end", kind="stable")
        .reset_index(drop=True)
    )


def join_news_counts_with_market_weights(
    *,
    news_counts: pd.DataFrame,
    market_weights: pd.DataFrame,
    universe: pd.DataFrame,
) -> pd.DataFrame:
    """Join validated news counts to validated TEJ weekly weights."""

    metadata_columns = _universe_metadata_columns(universe)
    metadata = universe[metadata_columns].copy()
    news = news_counts.copy()
    metadata_columns_to_drop = [
        column
        for column in metadata_columns
        if column in news.columns and column != "ticker"
    ]
    if metadata_columns_to_drop:
        news = news.drop(columns=metadata_columns_to_drop)
    news = metadata.merge(news, on="ticker", how="inner")

    weight_columns = [
        "ticker",
        "week_end",
        "weight_date",
        "market_cap",
        "weekly_market_cap_weight",
    ]
    panel = news.merge(
        market_weights[weight_columns],
        on=["ticker", "week_end"],
        how="left",
        validate="one_to_one",
    )
    if panel["weekly_market_cap_weight"].isna().any():
        missing = panel.loc[
            panel["weekly_market_cap_weight"].isna(),
            ["ticker", "week_end"],
        ]
        raise HypeInputPanelError(
            "Missing market weight for ticker-week row(s): "
            + json.dumps(missing.head(10).to_dict(orient="records"))
        )

    weekly_totals = panel.groupby("week_end")["news_count_unique_urls"].transform("sum")
    panel["weekly_total_news_count_unique_urls"] = weekly_totals.astype(int)
    zero_total_weeks = sorted(
        panel.loc[
            panel["weekly_total_news_count_unique_urls"].eq(0),
            "week_end",
        ]
        .unique()
        .tolist()
    )
    if zero_total_weeks:
        raise HypeInputPanelError(
            "Weekly total news_count_unique_urls must be greater than 0; "
            f"zero-total week(s): {', '.join(zero_total_weeks)}."
        )

    output_columns = [
        *metadata_columns,
        "week_index",
        "week_start",
        "week_end",
        "weight_date",
        "market_cap",
        "weekly_market_cap_weight",
        "news_count_unique_urls",
        "matched_rows",
        "active_news_days",
        "weekly_total_news_count_unique_urls",
    ]
    output_columns = [column for column in output_columns if column in panel.columns]
    panel = panel[output_columns].sort_values(["ticker", "week_end"], kind="stable")
    forbidden = FORBIDDEN_HYPE_COLUMNS & set(panel.columns)
    if forbidden:
        raise HypeInputPanelError(
            "Hype-ready input panel unexpectedly contains Hype column(s): "
            + ", ".join(sorted(forbidden))
        )
    return panel.reset_index(drop=True)


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
    news_counts_file: str | Path,
    market_weights_file: str | Path,
    universe_file: str | Path,
    panel: pd.DataFrame,
    weekly_market_weight_summary: pd.DataFrame,
    universe_size: int,
    week_count: int,
) -> dict[str, Any]:
    """Build a JSON-serializable Goal 3B validation summary."""

    actual_rows = int(len(panel))
    expected_rows = int(universe_size * week_count)
    zero_stock_week_rows = int((panel["news_count_unique_urls"] == 0).sum())
    zero_stock_week_ratio = (
        round(zero_stock_week_rows / actual_rows, 6) if actual_rows else None
    )
    weekly_total_news = (
        panel[
            [
                "week_start",
                "week_end",
                "weekly_total_news_count_unique_urls",
            ]
        ]
        .drop_duplicates()
        .sort_values("week_end", kind="stable")
    )

    return {
        "pilot_start_date": pilot_start_date,
        "pilot_end_date": pilot_end_date,
        "week_count": week_count,
        "universe_size": universe_size,
        "expected_rows": expected_rows,
        "actual_rows": actual_rows,
        "news_counts_file": str(news_counts_file),
        "market_weights_file": str(market_weights_file),
        "universe_file": str(universe_file),
        "total_news_count_unique_urls": int(
            panel["news_count_unique_urls"].sum()
        ),
        "weekly_total_news_count_unique_urls": _json_records(weekly_total_news),
        "zero_stock_week_rows": zero_stock_week_rows,
        "zero_stock_week_ratio": zero_stock_week_ratio,
        "market_weight_sum_by_week": _json_records(
            weekly_market_weight_summary[
                ["week_start", "week_end", "market_cap_weight_sum"]
            ]
        ),
        "weight_date_by_week": _json_records(
            weekly_market_weight_summary[
                ["week_start", "week_end", "weight_date"]
            ]
        ),
        "validation_status": "passed"
        if actual_rows == expected_rows
        else "failed_row_count_mismatch",
        "hype_index_computed": False,
        "market_cap_weights_joined": True,
    }


def output_paths(output_dir: Path, *, label: str = OUTPUT_DATE_LABEL) -> HypeInputPanelPaths:
    """Return the standard local output paths for a date label."""

    return HypeInputPanelPaths(
        panel=output_dir / f"hype_input_panel_{label}.csv",
        summary_json=output_dir / f"weekly_input_validation_summary_{label}.json",
        weekly_market_weight_summary=(
            output_dir / f"weekly_market_weight_summary_{label}.csv"
        ),
    )


def write_outputs(
    *,
    output_dir: Path,
    panel: pd.DataFrame,
    weekly_market_weight_summary: pd.DataFrame,
    summary: dict[str, Any],
    label: str = OUTPUT_DATE_LABEL,
) -> HypeInputPanelPaths:
    """Write local-only Goal 3B outputs."""

    forbidden = FORBIDDEN_HYPE_COLUMNS & set(panel.columns)
    if forbidden:
        raise HypeInputPanelError(
            "Hype-ready input panel contains forbidden Hype column(s): "
            + ", ".join(sorted(forbidden))
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = output_paths(output_dir, label=label)
    panel.to_csv(paths.panel, index=False)
    weekly_market_weight_summary.to_csv(
        paths.weekly_market_weight_summary,
        index=False,
    )
    paths.summary_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return paths


def build_hype_input_panel(
    *,
    news_counts_file: str | Path = DEFAULT_NEWS_COUNTS_FILE,
    market_weights_file: str | Path = DEFAULT_MARKET_WEIGHTS_FILE,
    universe_file: str | Path = DEFAULT_UNIVERSE_FILE,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    pilot_start_date: str = DEFAULT_PILOT_START_DATE,
    pilot_end_date: str = DEFAULT_PILOT_END_DATE,
    repo_root: Path = Path.cwd(),
    write_files: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], HypeInputPanelPaths | None]:
    """Build the Hype-ready stock-week input panel without computing Hype."""

    weekly_bins = build_weekly_bins(pilot_start_date, pilot_end_date)
    universe = load_universe(universe_file, repo_root=repo_root)
    universe_tickers = set(universe["ticker"])
    news_counts = load_and_validate_news_counts(
        news_counts_file,
        repo_root=repo_root,
        universe_tickers=universe_tickers,
        weekly_bins=weekly_bins,
    )
    market_weights, weekly_market_weight_summary = load_and_validate_market_weights(
        market_weights_file,
        repo_root=repo_root,
        universe_tickers=universe_tickers,
        weekly_bins=weekly_bins,
    )
    panel = join_news_counts_with_market_weights(
        news_counts=news_counts,
        market_weights=market_weights,
        universe=universe,
    )
    summary = build_summary(
        pilot_start_date=pilot_start_date,
        pilot_end_date=pilot_end_date,
        news_counts_file=resolve_repo_path(news_counts_file, repo_root=repo_root),
        market_weights_file=resolve_repo_path(market_weights_file, repo_root=repo_root),
        universe_file=resolve_repo_path(universe_file, repo_root=repo_root),
        panel=panel,
        weekly_market_weight_summary=weekly_market_weight_summary,
        universe_size=int(len(universe)),
        week_count=int(len(weekly_bins)),
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
            weekly_market_weight_summary=weekly_market_weight_summary,
            summary=summary,
            label=label,
        )
    return panel, weekly_market_weight_summary, summary, paths
