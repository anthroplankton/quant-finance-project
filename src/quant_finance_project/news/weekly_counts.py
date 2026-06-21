"""Aggregate local GDELT stock-day counts into stock-week news-count panels.

This module only aggregates metadata counts that already exist locally. It does
not download GDELT files, compute a Hype Index, join market-cap weights, or
store article full text.
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
DEFAULT_UNIVERSE_FILE = Path("data/processed/tej/top50_universe_20250331.csv")
DEFAULT_OUTPUT_DIR = Path("data/processed/news/gdelt_pilot_8w/weekly_counts")
ALLOWED_OUTPUT_ROOT = Path("data/processed/news")
OUTPUT_DATE_LABEL = "20250405_20250530"
UNIVERSE_METADATA_COLUMNS = [
    "stock_id",
    "ticker",
    "official_chinese_name",
    "official_english_name",
    "industry",
]
STOCK_DAY_COUNT_COLUMNS = [
    "date",
    "matched_ticker",
    "matched_rows",
    "unique_urls",
]
FORBIDDEN_HYPE_COLUMNS = {
    "hype",
    "raw_hype",
    "hype_index",
    "adjusted_hype",
    "cap_adjusted_hype",
}


class WeeklyCountAggregationError(RuntimeError):
    """Raised when local weekly news-count aggregation cannot proceed."""


@dataclass(frozen=True)
class WeeklyCountOutputPaths:
    """Local output paths written by the weekly aggregation step."""

    stock_week_counts: Path
    weekly_totals: Path
    coverage_summary: Path
    summary_json: Path


def parse_iso_date(value: str) -> date:
    """Parse a YYYY-MM-DD date for the pilot window."""

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise WeeklyCountAggregationError(
            f"Invalid date {value!r}; expected YYYY-MM-DD."
        ) from exc


def build_weekly_bins(
    pilot_start_date: str = DEFAULT_PILOT_START_DATE,
    pilot_end_date: str = DEFAULT_PILOT_END_DATE,
) -> pd.DataFrame:
    """Build Saturday-to-Friday weekly bins for an inclusive pilot window."""

    start = parse_iso_date(pilot_start_date)
    end = parse_iso_date(pilot_end_date)
    if start > end:
        raise WeeklyCountAggregationError("pilot_start_date must be on or before end.")
    if start.weekday() != 5:
        raise WeeklyCountAggregationError("pilot_start_date must be a Saturday.")
    if end.weekday() != 4:
        raise WeeklyCountAggregationError("pilot_end_date must be a Friday.")

    day_count = (end - start).days + 1
    if day_count % 7 != 0:
        raise WeeklyCountAggregationError(
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


def assign_week(
    value: str | date,
    weekly_bins: pd.DataFrame,
) -> tuple[int, str, str]:
    """Return the weekly bin assignment for a date."""

    row_date = parse_iso_date(value) if isinstance(value, str) else value
    for row in weekly_bins.itertuples(index=False):
        start = parse_iso_date(str(row.week_start))
        end = parse_iso_date(str(row.week_end))
        if start <= row_date <= end:
            return int(row.week_index), str(row.week_start), str(row.week_end)
    raise WeeklyCountAggregationError(
        f"Date {row_date.isoformat()} is outside the pilot weekly bins."
    )


def resolve_repo_path(path: str | Path, *, repo_root: Path) -> Path:
    """Resolve an absolute or repository-relative path."""

    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return repo_root / candidate


def validate_output_dir(output_dir: str | Path, *, repo_root: Path) -> Path:
    """Require aggregation outputs to stay under ignored news data paths."""

    resolved = resolve_repo_path(output_dir, repo_root=repo_root).resolve(strict=False)
    allowed_root = (repo_root / ALLOWED_OUTPUT_ROOT).resolve(strict=False)
    if not (resolved == allowed_root or allowed_root in resolved.parents):
        raise WeeklyCountAggregationError(
            f"Output directory must be under ignored local path {ALLOWED_OUTPUT_ROOT}."
        )
    return resolved


def _require_file(path: Path, *, label: str) -> None:
    if not path.is_file():
        raise WeeklyCountAggregationError(f"Missing required {label}: {path}.")


def _require_columns(frame: pd.DataFrame, columns: Iterable[str], *, label: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise WeeklyCountAggregationError(
            f"{label} is missing required column(s): {', '.join(missing)}."
        )


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().casefold() in {"1", "true", "t", "yes", "y"}


def _as_int(value: object, *, field: str) -> int:
    if value is None or value == "":
        raise WeeklyCountAggregationError(f"Missing required numeric field: {field}.")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise WeeklyCountAggregationError(
            f"Invalid integer value for {field}: {value!r}."
        ) from exc


def _required_summary_int(summary: dict[str, Any], field: str, *, input_dir: Path) -> int:
    value = summary.get(field)
    if field not in summary or value is None or value == "":
        raise WeeklyCountAggregationError(
            f"Probe summary for {input_dir} is missing required field {field}."
        )
    return _as_int(value, field=field)


def _optional_summary_int(summary: dict[str, Any], field: str) -> int | None:
    value = summary.get(field)
    if field not in summary or value is None or value == "":
        return None
    return _as_int(value, field=field)


def load_universe(universe_file: str | Path, *, repo_root: Path) -> pd.DataFrame:
    """Load and validate the fixed-universe table."""

    path = resolve_repo_path(universe_file, repo_root=repo_root)
    _require_file(path, label="universe file")
    universe = pd.read_csv(path, dtype=str).fillna("")
    _require_columns(universe, ["ticker"], label="universe file")

    for column in UNIVERSE_METADATA_COLUMNS:
        if column not in universe.columns:
            universe[column] = ""
    universe = universe[UNIVERSE_METADATA_COLUMNS].copy()
    for column in UNIVERSE_METADATA_COLUMNS:
        universe[column] = universe[column].astype(str).str.strip()

    universe = universe.loc[universe["ticker"] != ""].reset_index(drop=True)
    if universe.empty:
        raise WeeklyCountAggregationError("Universe file contains no ticker rows.")
    duplicate_tickers = sorted(
        universe.loc[universe["ticker"].duplicated(), "ticker"].unique().tolist()
    )
    if duplicate_tickers:
        raise WeeklyCountAggregationError(
            "Universe file contains duplicate ticker(s): "
            + ", ".join(duplicate_tickers)
        )
    return universe


def _validate_probe_summary(
    summary: dict[str, Any],
    *,
    input_dir: Path,
) -> dict[str, Any]:
    if summary.get("completed") is not True:
        raise WeeklyCountAggregationError(
            f"Probe summary for {input_dir} is not completed=true."
        )
    files_failed = _required_summary_int(
        summary,
        "files_failed",
        input_dir=input_dir,
    )
    if files_failed != 0:
        raise WeeklyCountAggregationError(
            f"Probe summary for {input_dir} has files_failed={files_failed}."
        )
    candidate_file_count_capped = _required_summary_int(
        summary,
        "candidate_file_count_capped",
        input_dir=input_dir,
    )
    candidate_file_count_uncapped = _required_summary_int(
        summary,
        "candidate_file_count_uncapped",
        input_dir=input_dir,
    )
    files_processed = _required_summary_int(
        summary,
        "files_processed",
        input_dir=input_dir,
    )
    files_missing = _required_summary_int(
        summary,
        "files_missing",
        input_dir=input_dir,
    )
    matched_rows = _required_summary_int(
        summary,
        "matched_rows",
        input_dir=input_dir,
    )
    unique_urls = _optional_summary_int(summary, "unique_urls")
    if candidate_file_count_capped < candidate_file_count_uncapped:
        raise WeeklyCountAggregationError(
            f"Probe summary for {input_dir} is capped: "
            f"candidate_file_count_capped={candidate_file_count_capped}, "
            f"candidate_file_count_uncapped={candidate_file_count_uncapped}. "
            "Capped chunks cannot be used for weekly aggregation."
        )
    if candidate_file_count_capped != candidate_file_count_uncapped:
        raise WeeklyCountAggregationError(
            f"Probe summary for {input_dir} has candidate_file_count_capped="
            f"{candidate_file_count_capped}, but candidate_file_count_uncapped="
            f"{candidate_file_count_uncapped}."
        )
    accounted_files = files_processed + files_missing + files_failed
    if accounted_files != candidate_file_count_uncapped:
        raise WeeklyCountAggregationError(
            f"Probe summary for {input_dir} has incomplete GDELT file-grid "
            f"coverage: files_processed + files_missing + files_failed = "
            f"{accounted_files}, but candidate_file_count_uncapped = "
            f"{candidate_file_count_uncapped}."
        )
    for field in (
        "missing_file_threshold_exceeded",
        "disk_limit_exceeded",
        "max_download_mb_exceeded",
    ):
        if _as_bool(summary.get(field)):
            raise WeeklyCountAggregationError(
                f"Probe summary for {input_dir} has {field}=true."
            )
    start_date = str(summary.get("start_date", "")).strip()
    end_date = str(summary.get("end_date", "")).strip()
    if not start_date or not end_date:
        raise WeeklyCountAggregationError(
            f"Probe summary for {input_dir} must include start_date and end_date."
        )
    parse_iso_date(start_date)
    parse_iso_date(end_date)

    return {
        "input_dir": str(input_dir),
        "start_date": start_date,
        "end_date": end_date,
        "candidate_file_count_capped": candidate_file_count_capped,
        "candidate_file_count_uncapped": candidate_file_count_uncapped,
        "files_processed": files_processed,
        "files_missing": files_missing,
        "files_failed": files_failed,
        "matched_rows": matched_rows,
        "unique_urls": unique_urls,
        "missing_file_ratio": summary.get("missing_file_ratio"),
        "completed": summary.get("completed"),
    }


def _validate_stock_day_count_totals(
    counts: pd.DataFrame,
    *,
    chunk_summary: dict[str, Any],
    counts_path: Path,
    input_path: Path,
) -> None:
    summary_matched_rows = _as_int(
        chunk_summary.get("matched_rows"),
        field="matched_rows",
    )
    summary_unique_urls = chunk_summary.get("unique_urls")
    count_matched_rows = int(counts["matched_rows"].sum()) if not counts.empty else 0
    count_unique_urls = int(counts["unique_urls"].sum()) if not counts.empty else 0

    if counts.empty and summary_matched_rows > 0:
        raise WeeklyCountAggregationError(
            f"{counts_path} in input directory {input_path} is empty, but "
            f"probe_summary matched_rows={summary_matched_rows}; "
            f"stock_day_counts matched_rows sum={count_matched_rows}."
        )
    if count_matched_rows != summary_matched_rows:
        raise WeeklyCountAggregationError(
            f"{counts_path} in input directory {input_path} is inconsistent "
            f"with probe_summary: summary matched_rows={summary_matched_rows}; "
            f"stock_day_counts matched_rows sum={count_matched_rows}."
        )
    if summary_unique_urls is not None and int(summary_unique_urls) > 0:
        if count_unique_urls <= 0:
            raise WeeklyCountAggregationError(
                f"{counts_path} in input directory {input_path} is inconsistent "
                f"with probe_summary: summary unique_urls={summary_unique_urls}; "
                f"stock_day_counts unique_urls sum={count_unique_urls}."
            )


def _read_input_chunk(
    input_dir: str | Path,
    *,
    pilot_start: date,
    pilot_end: date,
    universe_tickers: set[str],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    input_path = Path(input_dir)
    summary_path = input_path / "probe_summary.json"
    counts_path = input_path / "stock_day_counts.csv"
    _require_file(summary_path, label="probe_summary.json")
    _require_file(counts_path, label="stock_day_counts.csv")

    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WeeklyCountAggregationError(
            f"Invalid JSON in probe summary: {summary_path}."
        ) from exc
    chunk_summary = _validate_probe_summary(summary, input_dir=input_path)

    counts = pd.read_csv(counts_path, dtype=str).fillna("")
    _require_columns(counts, STOCK_DAY_COUNT_COLUMNS, label=str(counts_path))
    counts = counts[STOCK_DAY_COUNT_COLUMNS].copy()
    if counts.empty:
        _validate_stock_day_count_totals(
            counts,
            chunk_summary=chunk_summary,
            counts_path=counts_path,
            input_path=input_path,
        )
        return counts, chunk_summary

    counts["date"] = counts["date"].astype(str).str.strip()
    counts["matched_ticker"] = counts["matched_ticker"].astype(str).str.strip()
    for column in ("matched_rows", "unique_urls"):
        try:
            counts[column] = pd.to_numeric(counts[column], errors="raise").astype(int)
        except (TypeError, ValueError) as exc:
            raise WeeklyCountAggregationError(
                f"{counts_path} has invalid integer values in {column}."
            ) from exc
        if (counts[column] < 0).any():
            raise WeeklyCountAggregationError(
                f"{counts_path} has negative values in {column}."
            )
    _validate_stock_day_count_totals(
        counts,
        chunk_summary=chunk_summary,
        counts_path=counts_path,
        input_path=input_path,
    )

    try:
        parsed_dates = pd.to_datetime(
            counts["date"],
            format="%Y-%m-%d",
            errors="raise",
        )
    except ValueError as exc:
        raise WeeklyCountAggregationError(
            f"{counts_path} has invalid date values; expected YYYY-MM-DD."
        ) from exc
    counts["_parsed_date"] = parsed_dates.dt.date
    chunk_start = parse_iso_date(str(chunk_summary["start_date"]))
    chunk_end = parse_iso_date(str(chunk_summary["end_date"]))
    outside = counts.loc[
        (counts["_parsed_date"] < pilot_start) | (counts["_parsed_date"] > pilot_end)
    ]
    if not outside.empty:
        bad_dates = sorted(outside["date"].unique().tolist())
        raise WeeklyCountAggregationError(
            f"{counts_path} has date(s) outside the pilot window: "
            + ", ".join(bad_dates)
        )
    outside_chunk = counts.loc[
        (counts["_parsed_date"] < chunk_start) | (counts["_parsed_date"] > chunk_end)
    ]
    if not outside_chunk.empty:
        bad_dates = sorted(outside_chunk["date"].unique().tolist())
        raise WeeklyCountAggregationError(
            f"{counts_path} in input directory {input_path} has date(s) outside "
            f"its chunk range: {', '.join(bad_dates)}. Expected dates from "
            f"{chunk_start.isoformat()} to {chunk_end.isoformat()}."
        )

    unknown_tickers = sorted(set(counts["matched_ticker"]) - universe_tickers)
    if unknown_tickers:
        raise WeeklyCountAggregationError(
            f"{counts_path} has matched_ticker outside the universe: "
            + ", ".join(unknown_tickers)
        )

    counts["input_dir"] = str(input_path)
    return counts, chunk_summary


def validate_chunk_coverage(
    chunk_summaries: list[dict[str, Any]],
    *,
    pilot_start_date: str,
    pilot_end_date: str,
) -> None:
    """Validate selected chunks exactly and continuously cover the pilot window."""

    if not chunk_summaries:
        raise WeeklyCountAggregationError("No chunk summaries were provided.")

    pilot_start = parse_iso_date(pilot_start_date)
    pilot_end = parse_iso_date(pilot_end_date)
    intervals: list[tuple[date, date, str]] = []
    for summary in chunk_summaries:
        start = parse_iso_date(str(summary["start_date"]))
        end = parse_iso_date(str(summary["end_date"]))
        input_dir = str(summary.get("input_dir", ""))
        if start > end:
            raise WeeklyCountAggregationError(
                f"Chunk coverage start is after end for {input_dir}: "
                f"{start.isoformat()} to {end.isoformat()}."
            )
        if start < pilot_start or end > pilot_end:
            raise WeeklyCountAggregationError(
                "Chunk coverage outside pilot window: "
                f"{input_dir} covers {start.isoformat()} to {end.isoformat()}, "
                f"but the pilot window is {pilot_start_date} to {pilot_end_date}."
            )
        intervals.append((start, end, input_dir))

    intervals.sort(key=lambda item: item[0])
    first_start = intervals[0][0]
    if first_start != pilot_start:
        missing_end = first_start - timedelta(days=1)
        raise WeeklyCountAggregationError(
            "Missing chunk coverage from "
            f"{pilot_start.isoformat()} to {missing_end.isoformat()}."
        )

    expected_start = pilot_start
    previous_start: date | None = None
    previous_end: date | None = None
    previous_input_dir = ""
    for start, end, input_dir in intervals:
        if start < expected_start:
            previous_range = (
                f"{previous_start.isoformat()} to {previous_end.isoformat()}"
                if previous_start is not None and previous_end is not None
                else "unknown"
            )
            raise WeeklyCountAggregationError(
                "Overlapping chunk coverage detected: "
                f"{previous_input_dir} covers {previous_range}; "
                f"{input_dir} covers {start.isoformat()} to {end.isoformat()}."
            )
        if start > expected_start:
            missing_start = expected_start
            missing_end = start - timedelta(days=1)
            raise WeeklyCountAggregationError(
                "Missing chunk coverage from "
                f"{missing_start.isoformat()} to {missing_end.isoformat()}."
            )
        previous_start = start
        previous_end = end
        previous_input_dir = input_dir
        expected_start = end + timedelta(days=1)

    if expected_start <= pilot_end:
        raise WeeklyCountAggregationError(
            "Missing chunk coverage from "
            f"{expected_start.isoformat()} to {pilot_end.isoformat()}."
        )


def load_and_validate_stock_day_counts(
    input_dirs: list[str | Path],
    *,
    pilot_start_date: str,
    pilot_end_date: str,
    universe_tickers: set[str],
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Load selected chunk inputs and reject unsafe count inputs."""

    if not input_dirs:
        raise WeeklyCountAggregationError("At least one --input-dir is required.")
    pilot_start = parse_iso_date(pilot_start_date)
    pilot_end = parse_iso_date(pilot_end_date)

    frames: list[pd.DataFrame] = []
    chunk_summaries: list[dict[str, Any]] = []
    for input_dir in input_dirs:
        counts, summary = _read_input_chunk(
            input_dir,
            pilot_start=pilot_start,
            pilot_end=pilot_end,
            universe_tickers=universe_tickers,
        )
        frames.append(counts)
        chunk_summaries.append(summary)

    validate_chunk_coverage(
        chunk_summaries,
        pilot_start_date=pilot_start_date,
        pilot_end_date=pilot_end_date,
    )

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if combined.empty:
        return combined, chunk_summaries

    duplicated = combined.duplicated(["date", "matched_ticker"], keep=False)
    if duplicated.any():
        duplicate_rows = combined.loc[
            duplicated,
            ["date", "matched_ticker", "input_dir"],
        ].sort_values(["date", "matched_ticker"])
        examples = duplicate_rows.head(10).to_dict(orient="records")
        raise WeeklyCountAggregationError(
            "Duplicate or overlapping stock-day rows detected: "
            + json.dumps(examples, ensure_ascii=False)
        )
    return combined, chunk_summaries


def aggregate_stock_week_counts(
    *,
    universe: pd.DataFrame,
    stock_day_counts: pd.DataFrame,
    weekly_bins: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Aggregate daily count rows and zero-fill the full stock-week panel."""

    stock_day = stock_day_counts.copy()
    if not stock_day.empty:
        assignments = stock_day["date"].map(lambda value: assign_week(value, weekly_bins))
        stock_day["week_index"] = assignments.map(lambda item: item[0])
        stock_day["week_start"] = assignments.map(lambda item: item[1])
        stock_day["week_end"] = assignments.map(lambda item: item[2])
        stock_day["active_news_day"] = (stock_day["unique_urls"] > 0).astype(int)
        aggregated = (
            stock_day.groupby(
                ["matched_ticker", "week_index", "week_start", "week_end"],
                as_index=False,
            )
            .agg(
                news_count_unique_urls=("unique_urls", "sum"),
                matched_rows=("matched_rows", "sum"),
                active_news_days=("active_news_day", "sum"),
            )
            .rename(columns={"matched_ticker": "ticker"})
        )
    else:
        aggregated = pd.DataFrame(
            columns=[
                "ticker",
                "week_index",
                "week_start",
                "week_end",
                "news_count_unique_urls",
                "matched_rows",
                "active_news_days",
            ]
        )

    universe_ordered = universe[UNIVERSE_METADATA_COLUMNS].copy()
    week_frame = weekly_bins.copy()
    full_panel = universe_ordered.merge(week_frame, how="cross")
    stock_week = full_panel.merge(
        aggregated,
        on=["ticker", "week_index", "week_start", "week_end"],
        how="left",
    )
    for column in ("news_count_unique_urls", "matched_rows", "active_news_days"):
        stock_week[column] = stock_week[column].fillna(0).astype(int)

    stock_week = stock_week[
        [
            *UNIVERSE_METADATA_COLUMNS,
            "week_index",
            "week_start",
            "week_end",
            "news_count_unique_urls",
            "matched_rows",
            "active_news_days",
        ]
    ].sort_values(["ticker", "week_index"], kind="stable")

    weekly_totals = (
        stock_week.groupby(["week_index", "week_start", "week_end"], as_index=False)
        .agg(
            news_count_unique_urls=("news_count_unique_urls", "sum"),
            matched_rows=("matched_rows", "sum"),
            active_stock_days=("active_news_days", "sum"),
            stocks_with_news=("news_count_unique_urls", lambda values: int((values > 0).sum())),
            zero_stock_weeks=("news_count_unique_urls", lambda values: int((values == 0).sum())),
        )
        .sort_values("week_index")
    )

    coverage_summary = (
        stock_week.groupby(UNIVERSE_METADATA_COLUMNS, as_index=False, dropna=False)
        .agg(
            total_news_count_unique_urls=("news_count_unique_urls", "sum"),
            total_matched_rows=("matched_rows", "sum"),
            active_news_days=("active_news_days", "sum"),
            nonzero_weeks=("news_count_unique_urls", lambda values: int((values > 0).sum())),
            zero_weeks=("news_count_unique_urls", lambda values: int((values == 0).sum())),
        )
        .sort_values("ticker", kind="stable")
    )

    return (
        stock_week.reset_index(drop=True),
        weekly_totals.reset_index(drop=True),
        coverage_summary.reset_index(drop=True),
    )


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
    input_dirs: list[str | Path],
    input_chunk_summaries: list[dict[str, Any]],
    stock_week: pd.DataFrame,
    weekly_totals: pd.DataFrame,
    universe_size: int,
    week_count: int,
) -> dict[str, Any]:
    """Build a JSON-serializable aggregation summary."""

    actual_rows = int(len(stock_week))
    expected_rows = int(universe_size * week_count)
    zero_stock_week_rows = int((stock_week["news_count_unique_urls"] == 0).sum())
    if actual_rows:
        zero_stock_week_ratio = round(zero_stock_week_rows / actual_rows, 6)
    else:
        zero_stock_week_ratio = None
    stocks_with_news = int(
        stock_week.loc[stock_week["news_count_unique_urls"] > 0, "ticker"].nunique()
    )

    return {
        "pilot_start_date": pilot_start_date,
        "pilot_end_date": pilot_end_date,
        "week_count": week_count,
        "universe_size": universe_size,
        "expected_rows": expected_rows,
        "actual_rows": actual_rows,
        "input_dirs": [str(path) for path in input_dirs],
        "input_chunk_summaries": input_chunk_summaries,
        "total_matched_rows": int(stock_week["matched_rows"].sum()),
        "total_news_count_unique_urls": int(
            stock_week["news_count_unique_urls"].sum()
        ),
        "stocks_with_at_least_one_nonzero_week": stocks_with_news,
        "zero_stock_week_rows": zero_stock_week_rows,
        "zero_stock_week_ratio": zero_stock_week_ratio,
        "weekly_total_counts": _json_records(weekly_totals),
        "validation_status": "passed"
        if actual_rows == expected_rows
        else "failed_row_count_mismatch",
        "count_definition": (
            "news_count_unique_urls is the sum of stock-day unique URL counts "
            "within each stock-week; it is not full cross-day URL deduplication."
        ),
        "matched_rows_definition": (
            "matched_rows is preserved as a diagnostic row-count measure from "
            "the stock_day_counts input."
        ),
        "hype_index_computed": False,
        "market_cap_weights_joined": False,
        "article_text_stored": False,
    }


def output_paths(output_dir: Path, *, label: str = OUTPUT_DATE_LABEL) -> WeeklyCountOutputPaths:
    """Return the standard local output paths for a date label."""

    return WeeklyCountOutputPaths(
        stock_week_counts=output_dir / f"stock_week_news_counts_{label}.csv",
        weekly_totals=output_dir / f"weekly_news_totals_{label}.csv",
        coverage_summary=output_dir / f"stock_news_coverage_summary_{label}.csv",
        summary_json=output_dir / f"news_count_aggregation_summary_{label}.json",
    )


def write_outputs(
    *,
    output_dir: Path,
    stock_week: pd.DataFrame,
    weekly_totals: pd.DataFrame,
    coverage_summary: pd.DataFrame,
    summary: dict[str, Any],
    label: str = OUTPUT_DATE_LABEL,
) -> WeeklyCountOutputPaths:
    """Write local-only weekly aggregation outputs."""

    if FORBIDDEN_HYPE_COLUMNS & set(stock_week.columns):
        raise WeeklyCountAggregationError("Stock-week output contains Hype columns.")
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = output_paths(output_dir, label=label)
    stock_week.to_csv(paths.stock_week_counts, index=False)
    weekly_totals.to_csv(paths.weekly_totals, index=False)
    coverage_summary.to_csv(paths.coverage_summary, index=False)
    paths.summary_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return paths


def build_gdelt_weekly_counts(
    *,
    input_dirs: list[str | Path],
    universe_file: str | Path = DEFAULT_UNIVERSE_FILE,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    pilot_start_date: str = DEFAULT_PILOT_START_DATE,
    pilot_end_date: str = DEFAULT_PILOT_END_DATE,
    repo_root: Path = Path.cwd(),
    write_files: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any], WeeklyCountOutputPaths | None]:
    """Build the zero-filled stock-week news-count panel."""

    weekly_bins = build_weekly_bins(pilot_start_date, pilot_end_date)
    universe = load_universe(universe_file, repo_root=repo_root)
    resolved_input_dirs = [
        resolve_repo_path(input_dir, repo_root=repo_root) for input_dir in input_dirs
    ]
    stock_day_counts, chunk_summaries = load_and_validate_stock_day_counts(
        resolved_input_dirs,
        pilot_start_date=pilot_start_date,
        pilot_end_date=pilot_end_date,
        universe_tickers=set(universe["ticker"]),
    )
    stock_week, weekly_totals, coverage_summary = aggregate_stock_week_counts(
        universe=universe,
        stock_day_counts=stock_day_counts,
        weekly_bins=weekly_bins,
    )
    summary = build_summary(
        pilot_start_date=pilot_start_date,
        pilot_end_date=pilot_end_date,
        input_dirs=resolved_input_dirs,
        input_chunk_summaries=chunk_summaries,
        stock_week=stock_week,
        weekly_totals=weekly_totals,
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
            stock_week=stock_week,
            weekly_totals=weekly_totals,
            coverage_summary=coverage_summary,
            summary=summary,
            label=label,
        )
    return stock_week, weekly_totals, coverage_summary, summary, paths
