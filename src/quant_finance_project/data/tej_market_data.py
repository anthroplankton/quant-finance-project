"""Clean and validate local-only TEJPro market-data exports.

The functions in this module deliberately operate on local files or in-memory
DataFrames only. They do not download TEJ data, news data, or Hype Index
results.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any
import unicodedata

import pandas as pd

DEFAULT_COMPANY_RAW_PATH = Path(
    "data/raw/tej/tej_company_basic_tse_current_minimal_20260615.csv"
)
DEFAULT_MARKET_RAW_PATH = Path(
    "data/raw/tej/tej_top50_daily_market_panel_20250401_20260331.csv"
)
DEFAULT_OUTPUT_DIR = Path("data/processed/tej")

CONSTITUENT_AS_OF_DATE = "2025-03-31"
PANEL_START_DATE = "2025-04-01"
PANEL_END_DATE = "2026-03-31"
EXPECTED_TICKER_COUNT = 50
EXPECTED_TRADING_DATE_COUNT = 243
WEIGHT_TOLERANCE = 1e-8
MARKET_CAP_RECONSTRUCTION_TOLERANCE = 0.02

CANONICAL_MARKET_UNITS = {
    "close": "TWD per share",
    "shares_outstanding": "shares",
    "market_cap": "TWD",
    "volume": "shares",
    "traded_value": "TWD",
    "daily_market_cap_weight": "fraction, not percent",
    "weekly_market_cap_weight": "fraction, not percent",
    "market_cap_weight_from_tej": "fraction, not percent",
}

TEJ_NUMERIC_UNIT_MULTIPLIERS = {
    "shares_outstanding": {
        "流通在外股數(千股)": 1_000.0,
    },
    "market_cap": {
        "市值(千元)": 1_000.0,
        "市值(百萬元)": 1_000_000.0,
    },
    "volume": {
        "成交量(千股)": 1_000.0,
    },
    "traded_value": {
        "成交值(千元)": 1_000.0,
    },
    "market_cap_weight_from_tej": {
        "市值比重%": 0.01,
        "市值比重％": 0.01,
        "市值比重(%)": 0.01,
    },
}

COMPANY_METADATA_COLUMNS = [
    "stock_id",
    "ticker",
    "exchange",
    "status",
    "listing_date",
    "tse_industry_code",
    "tse_industry",
    "tej_industry",
    "tej_subindustry",
    "official_chinese_name",
    "chinese_short_name",
    "official_english_name",
    "english_short_name",
    "industry",
    "paid_in_capital",
]

DAILY_MARKET_PANEL_COLUMNS = [
    "date",
    "stock_id",
    "ticker",
    "close",
    "shares_outstanding",
    "market_cap",
    "volume",
    "traded_value",
    "market_cap_weight_from_tej",
    "daily_market_cap_weight",
]

WEEKLY_MARKET_CAP_WEIGHT_COLUMNS = [
    "week_end",
    "weight_date",
    "stock_id",
    "ticker",
    "market_cap",
    "weekly_market_cap_weight",
]

TOP50_UNIVERSE_COLUMNS = [
    "stock_id",
    "ticker",
    "official_chinese_name",
    "official_english_name",
    "industry",
    "constituent_source",
    "constituent_as_of_date",
    "notes",
]

COMPANY_COLUMN_ALIASES = {
    "ticker": (
        "ticker",
        "stock_code",
        "stock_id",
        "證期會代碼",
        "證券代碼",
        "股票代號",
        "公司代碼",
        "代號",
    ),
    "exchange": (
        "exchange",
        "market",
        "上市別",
    ),
    "status": (
        "status",
        "目前狀態",
    ),
    "listing_date": (
        "listing_date",
        "最近上市日",
    ),
    "tse_industry_code": (
        "tse_industry_code",
        "TSE 產業別",
        "TSE產業別",
    ),
    "tse_industry": (
        "tse_industry",
        "TSE產業名",
    ),
    "tej_industry": (
        "tej_industry",
        "TEJ產業名",
    ),
    "tej_subindustry": (
        "tej_subindustry",
        "TEJ子產業名",
    ),
    "official_chinese_name": (
        "official_chinese_name",
        "chinese_name",
        "company_chinese_name",
        "公司中文全稱",
        "公司中文簡稱",
        "公司名稱",
        "中文名稱",
        "證券名稱",
        "簡稱",
    ),
    "chinese_short_name": (
        "chinese_short_name",
        "short_chinese_name",
        "公司中文簡稱",
        "簡稱",
    ),
    "official_english_name": (
        "official_english_name",
        "english_name",
        "company_english_name",
        "公司英文全稱",
        "公司英文簡稱",
        "英文名稱",
        "英文簡稱",
        "英名",
    ),
    "english_short_name": (
        "english_short_name",
        "short_english_name",
        "公司英文簡稱",
        "英文簡稱",
    ),
    "industry": (
        "industry",
        "tej_industry",
        "industry_name",
        "TEJ產業名",
        "TSE產業名",
        "產業名稱",
        "產業別",
        "TSE產業別",
    ),
    "paid_in_capital": (
        "paid_in_capital",
        "實收資本額(元)",
    ),
}

MARKET_COLUMN_ALIASES = {
    "date": (
        "date",
        "trading_date",
        "年月日",
        "日期",
        "證券交易日",
        "資料日",
    ),
    "ticker": (
        "ticker",
        "stock_code",
        "stock_id",
        "證券代碼",
        "股票代號",
        "公司代碼",
        "代號",
    ),
    "close": (
        "close",
        "closing_price",
        "close_price",
        "收盤價",
        "收盤價(元)",
        "未調整收盤價",
        "收盤",
    ),
    "shares_outstanding": (
        "shares_outstanding",
        "shares",
        "流通在外股數",
        "流通在外股數(千股)",
        "發行股數",
        "上市股數",
        "流通股數",
    ),
    "market_cap": (
        "market_cap",
        "market_value",
        "市值",
        "市場價值",
        "總市值",
        "市值(百萬元)",
        "市值(千元)",
    ),
    "volume": (
        "volume",
        "trading_volume",
        "成交股數",
        "成交量",
        "成交量(千股)",
    ),
    "traded_value": (
        "traded_value",
        "turnover",
        "trading_value",
        "成交值",
        "成交金額",
        "成交值(千元)",
    ),
    "market_cap_weight_from_tej": (
        "market_cap_weight_from_tej",
        "market_cap_weight",
        "市值比重%",
        "市值比重％",
        "市值比重(%)",
    ),
}


class TejDataError(ValueError):
    """Raised when a TEJPro input cannot be parsed into the expected schema."""


class TejValidationError(TejDataError):
    """Raised when cleaned TEJPro outputs fail validation checks."""


@dataclass(frozen=True)
class TejBuildConfig:
    """Configuration for the local TEJPro cleaning workflow."""

    company_raw_path: Path = DEFAULT_COMPANY_RAW_PATH
    market_raw_path: Path = DEFAULT_MARKET_RAW_PATH
    output_dir: Path = DEFAULT_OUTPUT_DIR
    expected_ticker_count: int = EXPECTED_TICKER_COUNT
    expected_trading_date_count: int = EXPECTED_TRADING_DATE_COUNT
    expected_start_date: str = PANEL_START_DATE
    expected_end_date: str = PANEL_END_DATE
    constituent_as_of_date: str = CONSTITUENT_AS_OF_DATE
    weight_tolerance: float = WEIGHT_TOLERANCE
    market_cap_reconstruction_tolerance: float = MARKET_CAP_RECONSTRUCTION_TOLERANCE


def read_tej_csv(path: str | Path, encoding: str | None = None) -> pd.DataFrame:
    """Read a semicolon-delimited TEJPro CSV and strip text whitespace.

    TEJPro manual exports may use cp950 / Big5-style encodings. When no
    encoding is supplied, this reader tries common TEJ and UTF encodings.
    """

    path = Path(path)
    encodings = [encoding] if encoding else ["cp950", "big5", "utf-8-sig", "utf-8"]
    errors: list[str] = []

    for candidate in encodings:
        if candidate is None:
            continue
        try:
            raw = pd.read_csv(
                path,
                sep=";",
                encoding=candidate,
                dtype=str,
                keep_default_na=False,
            )
            return strip_dataframe_whitespace(raw)
        except UnicodeDecodeError as exc:
            errors.append(f"{candidate}: {exc}")

    tried = ", ".join(candidate for candidate in encodings if candidate)
    detail = "; ".join(errors)
    raise TejDataError(f"Could not decode TEJPro CSV {path} with {tried}. {detail}")


def strip_dataframe_whitespace(frame: pd.DataFrame) -> pd.DataFrame:
    """Strip surrounding whitespace from column labels and string-like values."""

    cleaned = frame.copy()
    cleaned.columns = [_clean_text(column) for column in cleaned.columns]

    for column in cleaned.columns:
        if isinstance(cleaned[column], pd.Series):
            cleaned[column] = cleaned[column].map(_clean_text)

    return cleaned


def normalize_stock_code(value: object) -> str:
    """Normalize a TEJPro stock-code cell into a compact ticker string."""

    text = _clean_text(value).upper()
    if not text:
        return ""

    text = re.sub(r"\.(TWO|TW)$", "", text)
    match = re.search(r"\d{4,6}[A-Z]?", text)
    if match:
        return match.group(0)
    return re.sub(r"\s+", "", text)


def clean_company_metadata(raw_company: pd.DataFrame) -> pd.DataFrame:
    """Clean a TEJ Company DB / 基本資料 export into a stable metadata table."""

    standardized = _select_alias_columns(
        raw_company,
        COMPANY_COLUMN_ALIASES,
        required=("ticker", "official_chinese_name", "industry"),
    )
    standardized["ticker"] = standardized["ticker"].map(normalize_stock_code)
    standardized["stock_id"] = standardized["ticker"]
    standardized["listing_date"] = parse_tej_dates(standardized["listing_date"])
    standardized["paid_in_capital"] = parse_numeric_series(
        standardized["paid_in_capital"]
    )

    standardized["industry"] = _coalesce_text_columns(
        standardized,
        ("tej_industry", "tse_industry", "industry"),
    )

    if "official_english_name" not in standardized:
        standardized["official_english_name"] = ""

    cleaned = standardized[COMPANY_METADATA_COLUMNS]
    cleaned = cleaned.loc[cleaned["ticker"] != ""]
    cleaned = cleaned.drop_duplicates(subset=["ticker"], keep="first")
    return cleaned.sort_values("ticker").reset_index(drop=True)


def clean_daily_market_panel(raw_market: pd.DataFrame) -> pd.DataFrame:
    """Clean a TEJ daily market panel and compute daily market-cap weights."""

    standardized, source_columns = _select_alias_columns_with_sources(
        raw_market,
        MARKET_COLUMN_ALIASES,
        required=(
            "date",
            "ticker",
            "close",
            "shares_outstanding",
            "market_cap",
            "volume",
            "traded_value",
        ),
    )
    cleaned = pd.DataFrame(
        {
            "date": parse_tej_dates(
                standardized["date"],
                field_name="date",
                raise_on_invalid=True,
                require_present=True,
            ),
            "ticker": standardized["ticker"].map(normalize_stock_code),
            "close": parse_market_numeric_column(
                standardized["close"],
                field="close",
                source_column=source_columns["close"],
            ),
            "shares_outstanding": parse_market_numeric_column(
                standardized["shares_outstanding"],
                field="shares_outstanding",
                source_column=source_columns["shares_outstanding"],
            ),
            "market_cap": parse_market_numeric_column(
                standardized["market_cap"],
                field="market_cap",
                source_column=source_columns["market_cap"],
            ),
            "volume": parse_market_numeric_column(
                standardized["volume"],
                field="volume",
                source_column=source_columns["volume"],
            ),
            "traded_value": parse_market_numeric_column(
                standardized["traded_value"],
                field="traded_value",
                source_column=source_columns["traded_value"],
            ),
            "market_cap_weight_from_tej": parse_market_numeric_column(
                standardized["market_cap_weight_from_tej"],
                field="market_cap_weight_from_tej",
                source_column=source_columns["market_cap_weight_from_tej"],
            ),
        }
    )
    _raise_if_missing_required_values(cleaned["ticker"], field_name="ticker")
    cleaned["stock_id"] = cleaned["ticker"]
    cleaned = cleaned.sort_values(["date", "ticker"]).reset_index(drop=True)
    cleaned = compute_daily_market_cap_weights(cleaned)
    return cleaned[DAILY_MARKET_PANEL_COLUMNS]


def compute_daily_market_cap_weights(daily_panel: pd.DataFrame) -> pd.DataFrame:
    """Compute each stock's daily market-cap share within the panel universe."""

    weighted = daily_panel.copy()
    daily_total = weighted.groupby("date")["market_cap"].transform("sum")
    invalid_total = daily_total.isna() | (daily_total <= 0)
    if invalid_total.any():
        raise TejDataError("Cannot compute weights for dates with nonpositive market cap.")
    weighted["daily_market_cap_weight"] = weighted["market_cap"] / daily_total
    return weighted


def aggregate_weekly_market_cap_weights(daily_panel: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily market-cap data to weekly weights.

    Each week uses the last available trading day in a Friday-ending calendar
    week, then recomputes weights from market cap on that selected date.
    """

    daily = daily_panel.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    daily["week_end"] = daily["date"].dt.to_period("W-FRI").dt.end_time.dt.normalize()
    last_trading_date = daily.groupby("week_end")["date"].transform("max")
    weekly = daily.loc[daily["date"].eq(last_trading_date)].copy()
    weekly_total = weekly.groupby("week_end")["market_cap"].transform("sum")
    invalid_total = weekly_total.isna() | (weekly_total <= 0)
    if invalid_total.any():
        raise TejDataError("Cannot compute weekly weights from nonpositive market cap.")

    weekly["weight_date"] = weekly["date"]
    weekly["weekly_market_cap_weight"] = weekly["market_cap"] / weekly_total
    weekly = weekly.sort_values(["week_end", "ticker"]).reset_index(drop=True)
    return weekly[WEEKLY_MARKET_CAP_WEIGHT_COLUMNS]


def build_top50_universe(
    company_metadata: pd.DataFrame,
    daily_panel: pd.DataFrame,
    constituent_as_of_date: str = CONSTITUENT_AS_OF_DATE,
    *,
    allow_missing_metadata: bool = False,
) -> pd.DataFrame:
    """Build the fixed top-50 universe table from panel tickers and metadata."""

    tickers = pd.DataFrame({"ticker": sorted(daily_panel["ticker"].unique())})
    tickers["stock_id"] = tickers["ticker"]
    merged = tickers.merge(
        company_metadata,
        on=["stock_id", "ticker"],
        how="left",
    )
    missing_tickers = _missing_metadata_tickers(merged)
    if missing_tickers and not allow_missing_metadata:
        raise TejValidationError(
            "Missing company metadata for market-panel ticker(s): "
            f"{', '.join(missing_tickers)}"
        )
    for column in ("official_chinese_name", "official_english_name", "industry"):
        merged[column] = merged[column].fillna("")

    merged["constituent_source"] = "TEJ market capitalization top 50"
    merged["constituent_as_of_date"] = constituent_as_of_date
    merged["notes"] = (
        "Fixed TEJ-based top-50 market-cap universe; not an official Taiwan 50 "
        "constituent flag."
    )
    return merged[TOP50_UNIVERSE_COLUMNS].sort_values("ticker").reset_index(drop=True)


def build_validation_summary(
    company_metadata: pd.DataFrame,
    daily_panel: pd.DataFrame,
    weekly_weights: pd.DataFrame,
    *,
    expected_ticker_count: int = EXPECTED_TICKER_COUNT,
    expected_trading_date_count: int = EXPECTED_TRADING_DATE_COUNT,
    expected_start_date: str = PANEL_START_DATE,
    expected_end_date: str = PANEL_END_DATE,
    tolerance: float = WEIGHT_TOLERANCE,
    market_cap_reconstruction_tolerance: float = (
        MARKET_CAP_RECONSTRUCTION_TOLERANCE
    ),
) -> dict[str, Any]:
    """Return validation checks for cleaned TEJPro market-data outputs."""

    company_has_columns = _has_columns(company_metadata, COMPANY_METADATA_COLUMNS)
    daily_has_columns = _has_columns(daily_panel, DAILY_MARKET_PANEL_COLUMNS)
    weekly_has_columns = _has_columns(weekly_weights, WEEKLY_MARKET_CAP_WEIGHT_COLUMNS)

    checks: dict[str, bool] = {
        "company_metadata_has_expected_columns": company_has_columns,
        "market_panel_has_expected_columns": daily_has_columns,
        "weekly_weights_have_expected_columns": weekly_has_columns,
    }

    counts: dict[str, Any] = {
        "company_metadata_rows": int(len(company_metadata)),
        "daily_market_panel_rows": int(len(daily_panel)),
        "weekly_market_cap_weight_rows": int(len(weekly_weights)),
    }
    metadata_coverage = _build_metadata_coverage(company_metadata, daily_panel)
    missing_metadata_tickers = _missing_metadata_tickers(metadata_coverage)
    checks["market_panel_tickers_have_company_metadata"] = (
        company_has_columns and daily_has_columns and not missing_metadata_tickers
    )
    counts["missing_metadata_ticker_count"] = len(missing_metadata_tickers)

    if daily_has_columns:
        daily_dates = pd.to_datetime(daily_panel["date"])
        observed_ticker_count = int(daily_panel["ticker"].nunique())
        observed_trading_date_count = int(daily_dates.nunique())
        observed_start_date = _date_to_text(daily_dates.min())
        observed_end_date = _date_to_text(daily_dates.max())
        rows_by_date = daily_panel.groupby("date").size()
        tickers_by_date = daily_panel.groupby("date")["ticker"].nunique()
        obs_by_ticker = daily_panel.groupby("ticker")["date"].nunique()
        duplicate_count = int(daily_panel.duplicated(["ticker", "date"]).sum())
        market_cap_relative_errors = _market_cap_reconstruction_relative_errors(
            daily_panel
        )
        daily_weight_sums = daily_panel.groupby("date")[
            "daily_market_cap_weight"
        ].sum()

        counts.update(
            {
                "daily_ticker_count": observed_ticker_count,
                "trading_date_count": observed_trading_date_count,
                "daily_min_date": observed_start_date,
                "daily_max_date": observed_end_date,
                "observed_ticker_count": observed_ticker_count,
                "observed_trading_date_count": observed_trading_date_count,
                "observed_start_date": observed_start_date,
                "observed_end_date": observed_end_date,
                "duplicate_ticker_date_rows": duplicate_count,
                "min_rows_per_trading_date": _series_min_int(rows_by_date),
                "max_rows_per_trading_date": _series_max_int(rows_by_date),
                "min_observations_per_ticker": _series_min_int(obs_by_ticker),
                "max_observations_per_ticker": _series_max_int(obs_by_ticker),
                "market_cap_reconstruction_max_relative_error": (
                    _series_max_float(market_cap_relative_errors)
                ),
            }
        )
        checks.update(
            {
                "daily_market_panel_has_expected_ticker_count": (
                    observed_ticker_count == expected_ticker_count
                ),
                "daily_market_panel_has_expected_date_range": (
                    observed_start_date == expected_start_date
                    and observed_end_date == expected_end_date
                ),
                "trading_date_count_matches_expected": (
                    observed_trading_date_count == expected_trading_date_count
                ),
                "each_trading_date_has_expected_rows": bool(
                    not rows_by_date.empty
                    and rows_by_date.eq(expected_ticker_count).all()
                    and tickers_by_date.eq(expected_ticker_count).all()
                ),
                "every_observed_date_has_expected_ticker_count": bool(
                    not rows_by_date.empty
                    and rows_by_date.eq(expected_ticker_count).all()
                    and tickers_by_date.eq(expected_ticker_count).all()
                ),
                "each_ticker_has_same_observation_count": (
                    int(obs_by_ticker.nunique()) == 1
                ),
                "every_ticker_has_expected_trading_date_count": bool(
                    not obs_by_ticker.empty
                    and obs_by_ticker.eq(expected_trading_date_count).all()
                ),
                "no_duplicate_ticker_date_rows": duplicate_count == 0,
                "close_is_present_and_positive": bool(
                    not daily_panel.empty
                    and daily_panel["close"].notna().all()
                    and daily_panel["close"].gt(0).all()
                ),
                "market_cap_is_positive": bool(
                    not daily_panel.empty
                    and daily_panel["market_cap"].notna().all()
                    and daily_panel["market_cap"].gt(0).all()
                ),
                "shares_outstanding_is_positive": bool(
                    not daily_panel.empty
                    and daily_panel["shares_outstanding"].notna().all()
                    and daily_panel["shares_outstanding"].gt(0).all()
                ),
                "market_cap_matches_close_times_shares": (
                    _market_cap_matches_close_times_shares(
                        daily_panel,
                        tolerance=market_cap_reconstruction_tolerance,
                    )
                ),
                "daily_universe_weights_sum_to_one": _weight_sums_are_one(
                    daily_weight_sums,
                    tolerance,
                ),
            }
        )
    else:
        checks.update(
            {
                "daily_market_panel_has_expected_ticker_count": False,
                "daily_market_panel_has_expected_date_range": False,
                "trading_date_count_matches_expected": False,
                "each_trading_date_has_expected_rows": False,
                "every_observed_date_has_expected_ticker_count": False,
                "each_ticker_has_same_observation_count": False,
                "every_ticker_has_expected_trading_date_count": False,
                "no_duplicate_ticker_date_rows": False,
                "close_is_present_and_positive": False,
                "market_cap_is_positive": False,
                "shares_outstanding_is_positive": False,
                "market_cap_matches_close_times_shares": False,
                "daily_universe_weights_sum_to_one": False,
            }
        )

    if weekly_has_columns:
        weekly_weight_sums = weekly_weights.groupby("week_end")[
            "weekly_market_cap_weight"
        ].sum()
        counts["weekly_count"] = int(weekly_weights["week_end"].nunique())
        checks["weekly_universe_weights_sum_to_one"] = _weight_sums_are_one(
            weekly_weight_sums,
            tolerance,
        )
    else:
        checks["weekly_universe_weights_sum_to_one"] = False

    failed_checks = [name for name, passed in checks.items() if not passed]
    return {
        "parameters": {
            "expected_ticker_count": expected_ticker_count,
            "expected_trading_date_count": expected_trading_date_count,
            "expected_start_date": expected_start_date,
            "expected_end_date": expected_end_date,
            "weight_tolerance": tolerance,
            "market_cap_reconstruction_tolerance": (
                market_cap_reconstruction_tolerance
            ),
        },
        "canonical_units": CANONICAL_MARKET_UNITS,
        "counts": counts,
        "panel_completeness": {
            "expected_start_date": expected_start_date,
            "expected_end_date": expected_end_date,
            "observed_start_date": counts.get("observed_start_date"),
            "observed_end_date": counts.get("observed_end_date"),
            "expected_trading_date_count": expected_trading_date_count,
            "observed_trading_date_count": counts.get("observed_trading_date_count"),
            "expected_ticker_count": expected_ticker_count,
            "observed_ticker_count": counts.get("observed_ticker_count"),
            "trading_date_count_matches_expected": checks.get(
                "trading_date_count_matches_expected"
            ),
            "every_observed_date_has_expected_ticker_count": checks.get(
                "every_observed_date_has_expected_ticker_count"
            ),
            "every_ticker_has_expected_trading_date_count": checks.get(
                "every_ticker_has_expected_trading_date_count"
            ),
        },
        "metadata_coverage": {
            "required_columns": [
                "official_chinese_name",
                "official_english_name",
                "industry",
            ],
            "missing_tickers": missing_metadata_tickers,
        },
        "checks": checks,
        "failed_checks": failed_checks,
    }


def ensure_validation_passed(summary: dict[str, Any]) -> None:
    """Raise a compact error if any validation check failed."""

    failed_checks = list(summary.get("failed_checks", []))
    if failed_checks:
        joined = ", ".join(failed_checks)
        missing_tickers = summary.get("metadata_coverage", {}).get("missing_tickers", [])
        detail = ""
        if missing_tickers:
            detail = f"; missing metadata tickers: {', '.join(missing_tickers)}"
        raise TejValidationError(f"TEJ validation failed: {joined}{detail}")


def build_tej_market_data(
    config: TejBuildConfig = TejBuildConfig(),
    *,
    require_valid: bool = True,
) -> dict[str, Any]:
    """Run the local TEJPro cleaning workflow and write regenerated outputs."""

    company_raw = read_tej_csv(config.company_raw_path)
    market_raw = read_tej_csv(config.market_raw_path)

    company_metadata = clean_company_metadata(company_raw)
    daily_panel = clean_daily_market_panel(market_raw)
    weekly_weights = aggregate_weekly_market_cap_weights(daily_panel)
    universe = build_top50_universe(
        company_metadata,
        daily_panel,
        constituent_as_of_date=config.constituent_as_of_date,
        allow_missing_metadata=True,
    )
    summary = build_validation_summary(
        company_metadata,
        daily_panel,
        weekly_weights,
        expected_ticker_count=config.expected_ticker_count,
        expected_trading_date_count=config.expected_trading_date_count,
        expected_start_date=config.expected_start_date,
        expected_end_date=config.expected_end_date,
        tolerance=config.weight_tolerance,
        market_cap_reconstruction_tolerance=(
            config.market_cap_reconstruction_tolerance
        ),
    )

    output_paths = write_tej_outputs(
        config.output_dir,
        company_metadata=company_metadata,
        daily_panel=daily_panel,
        universe=universe,
        weekly_weights=weekly_weights,
        validation_summary=summary,
        constituent_as_of_date=config.constituent_as_of_date,
        panel_start_date=config.expected_start_date,
        panel_end_date=config.expected_end_date,
    )

    if require_valid:
        ensure_validation_passed(summary)

    return {
        "company_metadata": company_metadata,
        "daily_market_panel": daily_panel,
        "top50_universe": universe,
        "weekly_market_cap_weights": weekly_weights,
        "validation_summary": summary,
        "output_paths": output_paths,
    }


def write_tej_outputs(
    output_dir: str | Path,
    *,
    company_metadata: pd.DataFrame,
    daily_panel: pd.DataFrame,
    universe: pd.DataFrame,
    weekly_weights: pd.DataFrame,
    validation_summary: dict[str, Any],
    constituent_as_of_date: str,
    panel_start_date: str,
    panel_end_date: str,
) -> dict[str, Path]:
    """Write regenerated local TEJ outputs under an ignored output directory."""

    output_paths = build_tej_output_paths(
        output_dir,
        constituent_as_of_date=constituent_as_of_date,
        panel_start_date=panel_start_date,
        panel_end_date=panel_end_date,
    )
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    company_metadata.to_csv(output_paths["company_metadata"], index=False)
    daily_panel.to_csv(
        output_paths["daily_market_panel"],
        index=False,
        date_format="%Y-%m-%d",
    )
    universe.to_csv(output_paths["top50_universe"], index=False)
    weekly_weights.to_csv(
        output_paths["weekly_market_cap_weights"],
        index=False,
        date_format="%Y-%m-%d",
    )
    output_paths["validation_summary"].write_text(
        json.dumps(validation_summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_paths


def build_tej_output_paths(
    output_dir: str | Path,
    *,
    constituent_as_of_date: str,
    panel_start_date: str,
    panel_end_date: str,
) -> dict[str, Path]:
    """Return local processed-output paths using config-derived date labels."""

    output_dir = Path(output_dir)
    constituent_label = _compact_date_label(constituent_as_of_date)
    start_label = _compact_date_label(panel_start_date)
    end_label = _compact_date_label(panel_end_date)
    panel_label = f"{start_label}_{end_label}"
    return {
        "company_metadata": output_dir / "company_metadata.csv",
        "daily_market_panel": output_dir / f"daily_market_panel_{panel_label}.csv",
        "top50_universe": output_dir / f"top50_universe_{constituent_label}.csv",
        "weekly_market_cap_weights": output_dir
        / f"weekly_market_cap_weights_{panel_label}.csv",
        "validation_summary": output_dir / f"validation_summary_{panel_label}.json",
    }


def _compact_date_label(value: str) -> str:
    parsed = parse_tej_dates(
        pd.Series([value]),
        field_name="output filename date",
        raise_on_invalid=True,
        require_present=True,
    ).iloc[0]
    return pd.Timestamp(parsed).strftime("%Y%m%d")


def parse_tej_dates(
    series: pd.Series,
    *,
    field_name: str = "date",
    raise_on_invalid: bool = False,
    require_present: bool = False,
) -> pd.Series:
    """Parse TEJ date strings, including Gregorian and ROC-year forms."""

    parsed = pd.to_datetime(series.map(_parse_tej_date_value), errors="coerce")
    if raise_on_invalid:
        invalid_values = _nonempty_invalid_date_values(series, parsed)
        if invalid_values:
            invalid_count = _nonempty_invalid_date_count(series, parsed)
            shown = ", ".join(invalid_values[:5])
            extra = "" if len(invalid_values) <= 5 else f" (+{len(invalid_values) - 5})"
            raise TejDataError(
                f"Invalid TEJ {field_name} value(s) could not be parsed "
                f"({invalid_count} row(s)): "
                f"{shown}{extra}"
            )
        if require_present:
            missing_count = _missing_required_value_count(series)
            if missing_count:
                raise TejDataError(
                    f"Missing required TEJ {field_name} value(s): "
                    f"{missing_count} blank row(s)"
                )
    return parsed


def parse_numeric_series(series: pd.Series) -> pd.Series:
    """Parse TEJ numeric text while tolerating commas and blank placeholders."""

    cleaned = (
        series.map(_clean_text)
        .str.replace(",", "", regex=False)
        .str.replace("，", "", regex=False)
        .str.replace(" ", "", regex=False)
    )
    cleaned = cleaned.replace(
        {
            "": pd.NA,
            "--": pd.NA,
            "-": pd.NA,
            "NA": pd.NA,
            "N/A": pd.NA,
            "nan": pd.NA,
        }
    )
    return pd.to_numeric(cleaned, errors="coerce")


def parse_market_numeric_column(
    series: pd.Series,
    *,
    field: str,
    source_column: str | None,
) -> pd.Series:
    """Parse a market-data numeric column and convert it to canonical units."""

    multiplier = _market_numeric_unit_multiplier(field, source_column)
    return parse_numeric_series(series) * multiplier


def _select_alias_columns(
    frame: pd.DataFrame,
    aliases: dict[str, tuple[str, ...]],
    *,
    required: tuple[str, ...],
) -> pd.DataFrame:
    selected, _ = _select_alias_columns_with_sources(
        frame,
        aliases,
        required=required,
    )
    return selected


def _select_alias_columns_with_sources(
    frame: pd.DataFrame,
    aliases: dict[str, tuple[str, ...]],
    *,
    required: tuple[str, ...],
) -> tuple[pd.DataFrame, dict[str, str | None]]:
    selected = pd.DataFrame(index=frame.index)
    source_columns: dict[str, str | None] = {}
    for output_name, candidates in aliases.items():
        source_column = _find_column(frame, candidates)
        source_columns[output_name] = source_column
        if source_column is None:
            if output_name in required:
                expected = ", ".join(candidates)
                raise TejDataError(
                    f"Missing required TEJ column for {output_name}: {expected}"
                )
            selected[output_name] = ""
        else:
            selected[output_name] = frame[source_column]
    return selected, source_columns


def _find_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    normalized_columns = {_normalize_column_name(column): column for column in frame}
    for candidate in candidates:
        match = normalized_columns.get(_normalize_column_name(candidate))
        if match is not None:
            return match
    return None


def _normalize_column_name(value: object) -> str:
    text = _clean_text(value).casefold()
    return re.sub(r"[\s_\-./()（）:：]+", "", text)


def _market_numeric_unit_multiplier(field: str, source_column: str | None) -> float:
    if source_column is None:
        return 1.0

    source_key = _normalize_column_name(source_column)
    for unit_column, multiplier in TEJ_NUMERIC_UNIT_MULTIPLIERS.get(field, {}).items():
        if source_key == _normalize_column_name(unit_column):
            return multiplier
    return 1.0


def _clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return unicodedata.normalize("NFKC", str(value)).strip()


def _parse_tej_date_value(value: object) -> pd.Timestamp | pd.NaT:
    text = _clean_text(value)
    if not text:
        return pd.NaT

    text = text.replace("年", "/").replace("月", "/").replace("日", "")
    text = text.replace("-", "/").replace(".", "/")

    if re.fullmatch(r"\d{7}", text):
        year = int(text[:3]) + 1911
        month = int(text[3:5])
        day = int(text[5:7])
        return _timestamp_or_nat(year=year, month=month, day=day)

    if re.fullmatch(r"\d{8}", text):
        year = int(text[:4])
        month = int(text[4:6])
        day = int(text[6:8])
        return _timestamp_or_nat(year=year, month=month, day=day)

    parts = text.split("/")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        year, month, day = (int(part) for part in parts)
        if year < 1911:
            year += 1911
        return _timestamp_or_nat(year=year, month=month, day=day)

    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return pd.NaT
    return pd.Timestamp(parsed).normalize()


def _timestamp_or_nat(*, year: int, month: int, day: int) -> pd.Timestamp | pd.NaT:
    try:
        return pd.Timestamp(year=year, month=month, day=day)
    except ValueError:
        return pd.NaT


def _nonempty_invalid_date_values(
    original: pd.Series,
    parsed: pd.Series,
) -> list[str]:
    original_text = original.map(_clean_text)
    invalid_mask = original_text.ne("") & parsed.isna()
    return original_text.loc[invalid_mask].drop_duplicates().astype(str).tolist()


def _nonempty_invalid_date_count(original: pd.Series, parsed: pd.Series) -> int:
    original_text = original.map(_clean_text)
    invalid_mask = original_text.ne("") & parsed.isna()
    return int(invalid_mask.sum())


def _missing_required_value_count(series: pd.Series) -> int:
    return int(series.map(_clean_text).eq("").sum())


def _raise_if_missing_required_values(series: pd.Series, *, field_name: str) -> None:
    missing_count = _missing_required_value_count(series)
    if missing_count:
        raise TejDataError(
            f"Missing required TEJ {field_name} value(s): "
            f"{missing_count} blank row(s)"
        )


def _has_columns(frame: pd.DataFrame, columns: list[str]) -> bool:
    return set(columns).issubset(frame.columns)


def _build_metadata_coverage(
    company_metadata: pd.DataFrame,
    daily_panel: pd.DataFrame,
) -> pd.DataFrame:
    required_columns = [
        "ticker",
        "official_chinese_name",
        "official_english_name",
        "industry",
    ]
    if not set(required_columns).issubset(company_metadata.columns):
        return pd.DataFrame(columns=required_columns)
    if "ticker" not in daily_panel.columns:
        return pd.DataFrame(columns=required_columns)

    tickers = pd.DataFrame({"ticker": sorted(daily_panel["ticker"].dropna().unique())})
    return tickers.merge(company_metadata[required_columns], on="ticker", how="left")


def _missing_metadata_tickers(metadata_coverage: pd.DataFrame) -> list[str]:
    required_columns = ["official_chinese_name", "official_english_name", "industry"]
    if metadata_coverage.empty or not set(required_columns).issubset(
        metadata_coverage.columns
    ):
        return []

    missing_mask = pd.Series(False, index=metadata_coverage.index)
    for column in required_columns:
        missing_mask = missing_mask | metadata_coverage[column].map(_clean_text).eq("")
    return metadata_coverage.loc[missing_mask, "ticker"].astype(str).tolist()


def _coalesce_text_columns(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=str)

    result = pd.Series("", index=frame.index, dtype=object)
    for column in columns:
        if column not in frame.columns:
            continue
        values = frame[column].map(_clean_text)
        result = result.mask(result.map(_clean_text).eq(""), values)
    return result


def _date_to_text(value: object) -> str | None:
    if pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _weight_sums_are_one(weight_sums: pd.Series, tolerance: float) -> bool:
    if weight_sums.empty:
        return False
    return bool((weight_sums - 1.0).abs().le(tolerance).all())


def _market_cap_matches_close_times_shares(
    daily_panel: pd.DataFrame,
    *,
    tolerance: float,
) -> bool:
    relative_errors = _market_cap_reconstruction_relative_errors(daily_panel)
    if relative_errors.empty:
        return False
    return bool(relative_errors.le(tolerance).all())


def _market_cap_reconstruction_relative_errors(daily_panel: pd.DataFrame) -> pd.Series:
    required_columns = {"close", "shares_outstanding", "market_cap"}
    if not required_columns.issubset(daily_panel.columns):
        return pd.Series(dtype=float)

    comparable = daily_panel[list(required_columns)].dropna()
    comparable = comparable.loc[
        comparable["close"].gt(0)
        & comparable["shares_outstanding"].gt(0)
        & comparable["market_cap"].gt(0)
    ]
    if comparable.empty:
        return pd.Series(dtype=float)

    reconstructed = comparable["close"] * comparable["shares_outstanding"]
    denominator = pd.concat(
        [comparable["market_cap"].abs(), reconstructed.abs()],
        axis=1,
    ).max(axis=1)
    denominator = denominator.replace(0, pd.NA).dropna()
    errors = (comparable.loc[denominator.index, "market_cap"] - reconstructed).abs()
    return errors / denominator


def _series_min_int(series: pd.Series) -> int:
    if series.empty:
        return 0
    return int(series.min())


def _series_max_int(series: pd.Series) -> int:
    if series.empty:
        return 0
    return int(series.max())


def _series_max_float(series: pd.Series) -> float | None:
    if series.empty:
        return None
    return float(series.max())
