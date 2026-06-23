"""Build curated report artifacts from existing Hype Index outputs.

This module consumes Goal 3C Hype Index outputs. It does not download data,
join raw inputs, recompute Hype formulas, create notebooks, or write under
``data/raw`` or ``data/processed``.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


DEFAULT_HYPE_PANEL_FILE = Path(
    "data/processed/hype_index/pilot_8w/indices/hype_index_panel_20250405_20250530.csv"
)
DEFAULT_WEEKLY_SUMMARY_FILE = Path(
    "data/processed/hype_index/pilot_8w/indices/"
    "weekly_hype_summary_20250405_20250530.csv"
)
DEFAULT_STOCK_SUMMARY_FILE = Path(
    "data/processed/hype_index/pilot_8w/indices/"
    "stock_hype_summary_20250405_20250530.csv"
)
DEFAULT_HYPE_SUMMARY_JSON = Path(
    "data/processed/hype_index/pilot_8w/indices/"
    "hype_index_summary_20250405_20250530.json"
)
DEFAULT_DAILY_MARKET_PANEL_FILE = Path(
    "data/processed/tej/daily_market_panel_20250401_20260331.csv"
)
DEFAULT_WEEKLY_MARKET_WEIGHTS_FILE = Path(
    "data/processed/tej/weekly_market_cap_weights_20250401_20260331.csv"
)
DEFAULT_UNIVERSE_FILE = Path("data/processed/tej/top50_universe_20250331.csv")
DEFAULT_COMPANY_METADATA_FILE = Path("data/processed/tej/company_metadata.csv")
DEFAULT_TEJ_VALIDATION_JSON = Path(
    "data/processed/tej/validation_summary_20250401_20260331.json"
)
DEFAULT_RAW_TEJ_RETURN_FILE = Path(
    "data/raw/tej/tej_top50_daily_adjusted_price_exrights_panel_20250401_20260331.csv"
)
DEFAULT_RESULTS_DIR = Path("report/results/pilot_8w")
DEFAULT_FIGURES_DIR = Path("report/figures/pilot_8w")
DEFAULT_TOP_N = 10
DEFAULT_FIGURE_DPI = 160
DEFAULT_MARKET_BACKGROUND_START = "2025-04-01"
DEFAULT_MARKET_BACKGROUND_END = "2026-03-31"
DEFAULT_HYPE_TRADING_START = "2025-04-07"
DEFAULT_HYPE_TRADING_END = "2025-05-29"
DEFAULT_KEY_TICKERS = ("2330", "2454", "2317", "2357")
DEFAULT_EXPECTED_ROWS = 400
DEFAULT_EXPECTED_WEEK_COUNT = 8
DEFAULT_EXPECTED_UNIVERSE_SIZE = 50
RAW_HYPE_SUM_TOLERANCE = 1e-8
MARKET_CAP_ADJUSTED_SUM_TOLERANCE = 1e-8
MIN_FIGURE_WIDTH_PX = 1000
MIN_FIGURE_HEIGHT_PX = 600

REQUIRED_PANEL_COLUMNS = [
    "ticker",
    "week_index",
    "week_start",
    "week_end",
    "news_count_unique_urls",
    "weekly_total_news_count_unique_urls",
    "weekly_market_cap_weight",
    "raw_hype",
    "market_cap_adjusted_hype",
]
REQUIRED_WEEKLY_SUMMARY_COLUMNS = [
    "week_index",
    "week_start",
    "week_end",
    "weekly_total_news_count_unique_urls",
    "nonzero_stock_count",
    "zero_stock_count",
    "ticker_with_max_raw_hype",
    "max_raw_hype",
    "ticker_with_max_market_cap_adjusted_hype",
    "max_market_cap_adjusted_hype",
    "raw_hype_sum",
    "market_cap_weight_sum",
]
REQUIRED_STOCK_SUMMARY_COLUMNS = [
    "ticker",
    "total_news_count_unique_urls",
    "nonzero_week_count",
    "zero_week_count",
    "mean_raw_hype",
    "max_raw_hype",
    "mean_market_cap_adjusted_hype",
    "max_market_cap_adjusted_hype",
    "mean_weekly_market_cap_weight",
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
REQUIRED_FIGURE_FILENAMES = [
    "weekly_news_counts.png",
    "top_stock_news_counts.png",
    "top_pooled_raw_hype_stocks.png",
    "top_pooled_market_cap_adjusted_hype_stocks.png",
    "raw_hype_heatmap_top_stocks.png",
    "market_cap_adjusted_hype_heatmap_top_stocks.png",
    "pooled_raw_hype_vs_pooled_market_cap_weight_scatter.png",
    "pooled_raw_hype_vs_pooled_market_cap_weight_scatter_zoom.png",
    "pooled_attention_size_imbalance_top_stocks.png",
    "zero_news_stock_weeks.png",
]
GOAL4B_MARKET_FIGURE_FILENAMES = [
    "sector_stock_count.png",
    "sector_market_cap_weight.png",
    "equal_weight_cumulative_return_hype_window.png",
    "equal_weight_rolling_volatility_20d_hype_window.png",
    "hype_vs_weekly_return_scatter.png",
    "hype_vs_weekly_volatility_scatter.png",
    "cap_adjusted_hype_vs_weekly_return_scatter.png",
    "cap_adjusted_hype_vs_weekly_volatility_scatter.png",
    "pooled_sector_raw_hype_vs_pooled_market_cap_weight_scatter.png",
    "pooled_sector_raw_hype_vs_pooled_market_cap_weight_scatter_zoom.png",
    "pooled_sector_market_cap_adjusted_hype_ranking.png",
    "pooled_sector_attention_size_imbalance.png",
    "sector_market_cap_adjusted_hype_heatmap.png",
    "key_stock_case_study_2330.png",
    "key_stock_case_study_2454.png",
    "key_stock_case_study_2317.png",
    "key_stock_case_study_2357.png",
]
GOAL4A_TABLE_NAMES = [
    "pipeline_validation_summary",
    "news_acquisition_summary",
    "weekly_news_totals",
    "weekly_hype_summary",
    "top_stock_news_counts",
    "stock_pooled_hype_summary",
    "top_pooled_raw_hype_stocks",
    "top_pooled_market_cap_adjusted_hype_stocks",
    "top_pooled_attention_size_imbalance_stocks",
    "zero_news_stock_summary",
]
GOAL4B_TABLE_NAMES = [
    "data_source_summary",
    "tej_market_validation_summary",
    "universe_summary",
    "sector_market_structure_summary",
    "basic_return_statistics_full_vs_hype_window",
    "hype_return_volatility_correlation_summary",
    "key_stock_case_study_summary",
    "sector_pooled_hype_summary",
    "top_pooled_sector_market_cap_adjusted_hype",
    "tej_industry_label_mapping",
    "sector_weekly_hype_summary",
]
DEPRECATED_REPORT_TABLE_NAMES = [
    "top_raw_hype_stocks",
    "top_market_cap_adjusted_hype_stocks",
    "sector_hype_summary",
]
DEPRECATED_REPORT_FIGURE_FILENAMES = [
    "top_mean_raw_hype.png",
    "top_mean_market_cap_adjusted_hype.png",
    "raw_hype_vs_market_cap_weight_scatter.png",
    "raw_hype_vs_market_cap_weight_scatter_zoom.png",
    "attention_size_imbalance_top_stocks.png",
    "sector_news_attention_vs_market_cap_weight.png",
    "return_distribution_full_vs_hype_window.png",
    "mean_vs_pooled_raw_hype_comparison.png",
    "mean_vs_pooled_cap_adjusted_hype_comparison.png",
]


class HypeReportError(RuntimeError):
    """Raised when Hype report artifacts cannot be built safely."""


@dataclass(frozen=True)
class HypeReportInputs:
    """Loaded Goal 3C output tables used by the reporting layer."""

    panel: pd.DataFrame
    weekly_summary: pd.DataFrame
    stock_summary: pd.DataFrame
    summary: dict[str, Any]
    chunk_summaries: list[dict[str, Any]]


@dataclass(frozen=True)
class MarketReportInputs:
    """Loaded TEJ market data used by the Goal 4B reporting layer."""

    daily_market_panel: pd.DataFrame
    weekly_market_weights: pd.DataFrame
    universe: pd.DataFrame
    company_metadata: pd.DataFrame
    adjusted_returns: pd.DataFrame
    validation_summary: dict[str, Any]
    market_background_start: str
    market_background_end: str
    hype_trading_start: str
    hype_trading_end: str


@dataclass(frozen=True)
class FigureSpec:
    """Metadata and objective checks for one generated figure."""

    filename: str
    title: str
    chart_type: str
    purpose: str
    input_rows_used: int
    dpi: int
    x_label: str = ""
    y_label: str = ""
    stock_label_count: int = 0
    require_axis_labels: bool = True


@dataclass(frozen=True)
class HypeReportArtifactPaths:
    """Paths written by the Goal 4A report artifact builder."""

    results_dir: Path
    figures_dir: Path
    table_paths: dict[str, tuple[Path, Path]]
    methodology_notes: Path
    figure_paths: dict[str, Path]
    figure_manifest_csv: Path
    figure_manifest_json: Path
    figure_index_md: Path
    artifact_manifest: Path


def resolve_repo_path(path: str | Path, *, repo_root: Path) -> Path:
    """Resolve an absolute or repository-relative path."""

    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return repo_root / candidate


def _require_file(path: Path, *, label: str) -> None:
    if not path.is_file():
        raise HypeReportError(f"Missing required {label}: {path}.")


def _require_columns(
    frame: pd.DataFrame, columns: Iterable[str], *, label: str
) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise HypeReportError(
            f"{label} is missing required column(s): {', '.join(missing)}."
        )


def _validate_output_dir(
    output_dir: str | Path,
    *,
    repo_root: Path,
    allowed_root: Path,
    label: str,
) -> Path:
    resolved = resolve_repo_path(output_dir, repo_root=repo_root).resolve(strict=False)
    allowed = (repo_root / allowed_root).resolve(strict=False)
    if not (resolved == allowed or allowed in resolved.parents):
        raise HypeReportError(f"{label} must be under {allowed_root}.")
    return resolved


def validate_results_dir(results_dir: str | Path, *, repo_root: Path) -> Path:
    """Require report table outputs to stay under ``report/results``."""

    return _validate_output_dir(
        results_dir,
        repo_root=repo_root,
        allowed_root=Path("report/results"),
        label="Results directory",
    )


def validate_figures_dir(figures_dir: str | Path, *, repo_root: Path) -> Path:
    """Require report figure outputs to stay under ``report/figures``."""

    return _validate_output_dir(
        figures_dir,
        repo_root=repo_root,
        allowed_root=Path("report/figures"),
        label="Figures directory",
    )


def _coerce_numeric_columns(
    frame: pd.DataFrame,
    columns: Iterable[str],
    *,
    label: str,
) -> None:
    for column in columns:
        if column not in frame.columns:
            continue
        try:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise HypeReportError(
                f"{label} has invalid numeric value(s) in {column}."
            ) from exc


def _load_csv(path: Path, *, label: str) -> pd.DataFrame:
    _require_file(path, label=label)
    return pd.read_csv(path)


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    _require_file(path, label=label)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HypeReportError(f"{label} is not valid JSON: {path}.") from exc


def load_hype_report_inputs(
    *,
    hype_panel_file: str | Path = DEFAULT_HYPE_PANEL_FILE,
    weekly_summary_file: str | Path = DEFAULT_WEEKLY_SUMMARY_FILE,
    stock_summary_file: str | Path = DEFAULT_STOCK_SUMMARY_FILE,
    hype_summary_json: str | Path = DEFAULT_HYPE_SUMMARY_JSON,
    chunk_summary_json: Iterable[str | Path] = (),
    repo_root: Path = Path.cwd(),
) -> HypeReportInputs:
    """Load and validate existing Goal 3C output artifacts."""

    panel_path = resolve_repo_path(hype_panel_file, repo_root=repo_root)
    weekly_path = resolve_repo_path(weekly_summary_file, repo_root=repo_root)
    stock_path = resolve_repo_path(stock_summary_file, repo_root=repo_root)
    summary_path = resolve_repo_path(hype_summary_json, repo_root=repo_root)

    panel = _load_csv(panel_path, label="Hype panel")
    weekly_summary = _load_csv(weekly_path, label="weekly Hype summary")
    stock_summary = _load_csv(stock_path, label="stock Hype summary")
    summary = _load_json(summary_path, label="Hype summary JSON")
    chunk_summaries = [
        _load_json(resolve_repo_path(path, repo_root=repo_root), label="chunk summary")
        for path in chunk_summary_json
    ]

    validate_hype_inputs(
        panel=panel,
        weekly_summary=weekly_summary,
        stock_summary=stock_summary,
        summary=summary,
    )
    return HypeReportInputs(
        panel=panel,
        weekly_summary=weekly_summary,
        stock_summary=stock_summary,
        summary=summary,
        chunk_summaries=chunk_summaries,
    )


def _ticker_text(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip()


def _date_series(series: pd.Series, *, format: str | None = None) -> pd.Series:
    return pd.to_datetime(series, format=format, errors="raise")


def _load_adjusted_return_file(path: Path, universe_tickers: set[str]) -> pd.DataFrame:
    _require_file(path, label="TEJ adjusted return data")
    columns = {
        "證期會代碼": "ticker",
        "年月日": "date",
        "收盤價(元)": "adjusted_close",
        "報酬率％": "simple_return_percent",
        "報酬率-Ln": "log_return_percent",
    }
    try:
        frame = pd.read_csv(
            path,
            sep=";",
            encoding="big5",
            usecols=list(columns),
        )
    except UnicodeDecodeError as exc:
        raise HypeReportError(
            f"TEJ adjusted return data is not readable as Big5: {path}."
        ) from exc
    frame = frame.rename(columns=columns)
    frame["ticker"] = _ticker_text(frame["ticker"])
    frame["date"] = _date_series(frame["date"].astype(str), format="%Y%m%d")
    for column in ["adjusted_close", "simple_return_percent", "log_return_percent"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["simple_return"] = frame["simple_return_percent"] / 100.0
    frame["log_return"] = frame["log_return_percent"] / 100.0
    frame = frame.loc[frame["ticker"].isin(universe_tickers)].copy()
    frame = frame.sort_values(["date", "ticker"], kind="stable").reset_index(drop=True)
    if frame.empty:
        raise HypeReportError("TEJ adjusted return data has no selected-universe rows.")
    return frame


def load_market_report_inputs(
    *,
    daily_market_panel_file: str | Path = DEFAULT_DAILY_MARKET_PANEL_FILE,
    weekly_market_weights_file: str | Path = DEFAULT_WEEKLY_MARKET_WEIGHTS_FILE,
    universe_file: str | Path = DEFAULT_UNIVERSE_FILE,
    company_metadata_file: str | Path = DEFAULT_COMPANY_METADATA_FILE,
    tej_validation_json: str | Path = DEFAULT_TEJ_VALIDATION_JSON,
    raw_tej_return_file: str | Path = DEFAULT_RAW_TEJ_RETURN_FILE,
    market_background_start: str = DEFAULT_MARKET_BACKGROUND_START,
    market_background_end: str = DEFAULT_MARKET_BACKGROUND_END,
    hype_trading_start: str = DEFAULT_HYPE_TRADING_START,
    hype_trading_end: str = DEFAULT_HYPE_TRADING_END,
    repo_root: Path = Path.cwd(),
) -> MarketReportInputs:
    """Load local TEJ market inputs for notebook-ready Goal 4B artifacts."""

    daily = _load_csv(
        resolve_repo_path(daily_market_panel_file, repo_root=repo_root),
        label="TEJ daily market panel",
    )
    weekly_weights = _load_csv(
        resolve_repo_path(weekly_market_weights_file, repo_root=repo_root),
        label="TEJ weekly market-cap weights",
    )
    universe = _load_csv(
        resolve_repo_path(universe_file, repo_root=repo_root),
        label="TEJ top-50 universe",
    )
    metadata = _load_csv(
        resolve_repo_path(company_metadata_file, repo_root=repo_root),
        label="TEJ company metadata",
    )
    validation = _load_json(
        resolve_repo_path(tej_validation_json, repo_root=repo_root),
        label="TEJ validation summary JSON",
    )

    _require_columns(
        daily,
        [
            "date",
            "ticker",
            "market_cap",
            "daily_market_cap_weight",
        ],
        label="TEJ daily market panel",
    )
    _require_columns(
        weekly_weights,
        ["week_end", "weight_date", "ticker", "weekly_market_cap_weight"],
        label="TEJ weekly market-cap weights",
    )
    _require_columns(
        universe,
        [
            "ticker",
            "official_chinese_name",
            "official_english_name",
            "industry",
        ],
        label="TEJ top-50 universe",
    )

    for frame in [daily, weekly_weights, universe, metadata]:
        if "ticker" in frame.columns:
            frame["ticker"] = _ticker_text(frame["ticker"])
    daily["date"] = _date_series(daily["date"])
    weekly_weights["week_end"] = _date_series(weekly_weights["week_end"])
    weekly_weights["weight_date"] = _date_series(weekly_weights["weight_date"])
    for column in ["market_cap", "daily_market_cap_weight"]:
        daily[column] = pd.to_numeric(daily[column], errors="raise")
    weekly_weights["weekly_market_cap_weight"] = pd.to_numeric(
        weekly_weights["weekly_market_cap_weight"], errors="raise"
    )

    universe_tickers = set(universe["ticker"])
    returns = _load_adjusted_return_file(
        resolve_repo_path(raw_tej_return_file, repo_root=repo_root),
        universe_tickers,
    )
    return MarketReportInputs(
        daily_market_panel=daily,
        weekly_market_weights=weekly_weights,
        universe=universe,
        company_metadata=metadata,
        adjusted_returns=returns,
        validation_summary=validation,
        market_background_start=market_background_start,
        market_background_end=market_background_end,
        hype_trading_start=hype_trading_start,
        hype_trading_end=hype_trading_end,
    )


def validate_hype_inputs(
    *,
    panel: pd.DataFrame,
    weekly_summary: pd.DataFrame,
    stock_summary: pd.DataFrame,
    summary: dict[str, Any],
) -> None:
    """Validate report inputs without recomputing the Hype pipeline."""

    _require_columns(panel, REQUIRED_PANEL_COLUMNS, label="Hype panel")
    _require_columns(
        weekly_summary,
        REQUIRED_WEEKLY_SUMMARY_COLUMNS,
        label="weekly Hype summary",
    )
    _require_columns(
        stock_summary,
        REQUIRED_STOCK_SUMMARY_COLUMNS,
        label="stock Hype summary",
    )

    _coerce_numeric_columns(
        panel,
        [
            "week_index",
            "news_count_unique_urls",
            "weekly_total_news_count_unique_urls",
            "weekly_market_cap_weight",
            "raw_hype",
            "market_cap_adjusted_hype",
        ],
        label="Hype panel",
    )
    _coerce_numeric_columns(
        weekly_summary,
        [
            "week_index",
            "weekly_total_news_count_unique_urls",
            "nonzero_stock_count",
            "zero_stock_count",
            "max_raw_hype",
            "max_market_cap_adjusted_hype",
            "raw_hype_sum",
            "market_cap_weight_sum",
        ],
        label="weekly Hype summary",
    )
    _coerce_numeric_columns(
        stock_summary,
        [
            "total_news_count_unique_urls",
            "nonzero_week_count",
            "zero_week_count",
            "mean_raw_hype",
            "max_raw_hype",
            "mean_market_cap_adjusted_hype",
            "max_market_cap_adjusted_hype",
            "mean_weekly_market_cap_weight",
        ],
        label="stock Hype summary",
    )

    expected_rows = int(summary.get("expected_rows", DEFAULT_EXPECTED_ROWS))
    expected_week_count = int(summary.get("week_count", DEFAULT_EXPECTED_WEEK_COUNT))
    expected_universe_size = int(
        summary.get("universe_size", DEFAULT_EXPECTED_UNIVERSE_SIZE)
    )
    if len(panel) != expected_rows:
        raise HypeReportError(
            f"Hype panel has {len(panel)} rows; expected {expected_rows}."
        )
    observed_weeks = int(panel["week_index"].nunique())
    if observed_weeks != expected_week_count:
        raise HypeReportError(
            f"Hype panel has {observed_weeks} weeks; expected {expected_week_count}."
        )
    observed_stocks = int(panel["ticker"].nunique())
    if observed_stocks != expected_universe_size:
        raise HypeReportError(
            f"Hype panel has {observed_stocks} stocks; expected "
            f"{expected_universe_size}."
        )
    if len(panel) != observed_weeks * observed_stocks:
        raise HypeReportError("Hype panel is not a complete stock-week grid.")

    if summary.get("validation_status", "passed") != "passed":
        raise HypeReportError(
            "Hype summary JSON does not report validation_status='passed'."
        )
    if summary.get("hype_index_computed", True) is not True:
        raise HypeReportError("Hype summary JSON does not confirm Hype computed.")
    if summary.get("market_cap_adjusted_hype_computed", True) is not True:
        raise HypeReportError(
            "Hype summary JSON does not confirm market-cap-adjusted Hype computed."
        )

    positive_news = panel["weekly_total_news_count_unique_urls"].gt(0)
    raw_positive = panel.loc[positive_news, "raw_hype"]
    if raw_positive.isna().any():
        raise HypeReportError("raw_hype is missing for positive-news weeks.")
    raw_sums = panel.loc[positive_news].groupby("week_index")["raw_hype"].sum()
    bad_raw_sums = raw_sums.loc[(raw_sums - 1.0).abs().gt(RAW_HYPE_SUM_TOLERANCE)]
    if not bad_raw_sums.empty:
        raise HypeReportError(
            "raw_hype must sum to 1 by positive-news week; "
            f"bad sums={bad_raw_sums.to_dict()}."
        )

    adjusted_positive = panel.loc[positive_news, "market_cap_adjusted_hype"]
    if adjusted_positive.isna().any():
        raise HypeReportError(
            "market_cap_adjusted_hype is missing for positive-news weeks."
        )
    adjusted_sums = (
        panel.loc[positive_news].groupby("week_index")["market_cap_adjusted_hype"].sum()
    )
    if (
        not adjusted_sums.empty
        and (adjusted_sums - 1.0).abs().le(MARKET_CAP_ADJUSTED_SUM_TOLERANCE).all()
    ):
        raise HypeReportError(
            "market_cap_adjusted_hype appears normalized to sum to 1."
        )


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return f"{value:.10g}"
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _escape_markdown_cell(value: Any) -> str:
    return _stringify(value).replace("|", "\\|").replace("\n", "<br>")


def markdown_table(frame: pd.DataFrame) -> str:
    """Render a small GitHub-flavored Markdown table without extra dependencies."""

    columns = [str(column) for column in frame.columns]
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    rows = [
        "| "
        + " | ".join(_escape_markdown_cell(row[column]) for column in frame.columns)
        + " |"
        for _, row in frame.iterrows()
    ]
    return "\n".join([header, divider, *rows]) + "\n"


def _write_table_pair(
    frame: pd.DataFrame,
    *,
    output_dir: Path,
    name: str,
) -> tuple[Path, Path]:
    csv_path = output_dir / f"{name}.csv"
    md_path = output_dir / f"{name}.md"
    frame.to_csv(csv_path, index=False, float_format="%.10g")
    md_path.write_text(markdown_table(frame), encoding="utf-8")
    return csv_path, md_path


def cleanup_deprecated_report_artifacts(
    *, results_dir: Path, figures_dir: Path
) -> None:
    """Remove report artifacts superseded by pooled cross-sectional reporting."""

    for name in DEPRECATED_REPORT_TABLE_NAMES:
        for suffix in (".csv", ".md"):
            (results_dir / f"{name}{suffix}").unlink(missing_ok=True)
    for filename in DEPRECATED_REPORT_FIGURE_FILENAMES:
        (figures_dir / filename).unlink(missing_ok=True)


def _metadata_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in METADATA_COLUMNS if column in frame.columns]


def _ordered_columns(frame: pd.DataFrame, columns: Iterable[str]) -> list[str]:
    return [column for column in columns if column in frame.columns]


def _top_stocks(
    stock_summary: pd.DataFrame,
    *,
    metric: str,
    top_n: int,
) -> pd.DataFrame:
    ordered = stock_summary.sort_values(
        [metric, "ticker"],
        ascending=[False, True],
        na_position="last",
        kind="stable",
    )
    return ordered.head(top_n).reset_index(drop=True)


def _market_cap_pool_values(
    *,
    hype_panel: pd.DataFrame,
    market_inputs: MarketReportInputs | None,
) -> pd.Series:
    """Return stock-week market-cap pool values aligned to ``hype_panel`` rows."""

    if market_inputs is None:
        return hype_panel["weekly_market_cap_weight"].astype(float)

    market_caps = market_inputs.weekly_market_weights[
        ["ticker", "week_end", "market_cap"]
    ].copy()
    market_caps["ticker"] = _ticker_text(market_caps["ticker"])
    market_caps["week_end"] = _date_series(market_caps["week_end"])
    panel_keys = hype_panel[["ticker", "week_end"]].copy()
    panel_keys["ticker"] = _ticker_text(panel_keys["ticker"])
    panel_keys["week_end"] = _date_series(panel_keys["week_end"])
    merged = panel_keys.merge(
        market_caps,
        on=["ticker", "week_end"],
        how="left",
        validate="many_to_one",
    )
    if merged["market_cap"].isna().any():
        missing = panel_keys.loc[merged["market_cap"].isna()].head(5).to_dict("records")
        raise HypeReportError(
            f"Missing TEJ weekly market cap for pooled reporting row(s): {missing}."
        )
    return pd.Series(
        merged["market_cap"].to_numpy(dtype=float),
        index=hype_panel.index,
    )


def build_stock_pooled_hype_summary(
    *,
    hype_panel: pd.DataFrame,
    market_inputs: MarketReportInputs | None = None,
) -> pd.DataFrame:
    """Build pooled 8-week stock-level Hype summary rows."""

    frame = hype_panel.copy()
    frame["ticker"] = _ticker_text(frame["ticker"])
    frame["_market_cap_pool_value"] = _market_cap_pool_values(
        hype_panel=frame,
        market_inputs=market_inputs,
    )
    total_news = frame["news_count_unique_urls"].sum()
    total_market_cap_pool = frame["_market_cap_pool_value"].sum()
    grouped = (
        frame.groupby(
            [
                "ticker",
                "official_chinese_name",
                "official_english_name",
                "industry",
            ],
            as_index=False,
        )
        .agg(
            total_news_count_unique_urls=("news_count_unique_urls", "sum"),
            pooled_market_cap_pool_value=("_market_cap_pool_value", "sum"),
            nonzero_week_count=(
                "news_count_unique_urls",
                lambda values: int((values > 0).sum()),
            ),
            zero_week_count=(
                "news_count_unique_urls",
                lambda values: int((values == 0).sum()),
            ),
        )
        .sort_values(
            ["total_news_count_unique_urls", "ticker"], ascending=[False, True]
        )
    )
    grouped["pooled_raw_hype"] = grouped["total_news_count_unique_urls"] / total_news
    grouped["pooled_market_cap_weight"] = (
        grouped["pooled_market_cap_pool_value"] / total_market_cap_pool
    )
    grouped["pooled_market_cap_adjusted_hype"] = (
        grouped["pooled_raw_hype"] / grouped["pooled_market_cap_weight"]
    )
    grouped["pooled_attention_size_imbalance"] = (
        grouped["pooled_raw_hype"] - grouped["pooled_market_cap_weight"]
    )
    columns = [
        "ticker",
        "official_chinese_name",
        "official_english_name",
        "industry",
        "total_news_count_unique_urls",
        "pooled_raw_hype",
        "pooled_market_cap_weight",
        "pooled_market_cap_adjusted_hype",
        "pooled_attention_size_imbalance",
        "nonzero_week_count",
        "zero_week_count",
    ]
    return grouped[columns].reset_index(drop=True)


def _chunk_number(summary: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = summary.get(key, default)
    if value is None:
        return default
    return float(value)


def _candidate_file_count(summary: dict[str, Any]) -> float:
    for key in (
        "candidate_file_count_uncapped",
        "candidate_file_count_capped",
        "files_attempted",
    ):
        if key in summary and summary[key] is not None:
            return float(summary[key])
    return 0.0


def build_data_pipeline_summary(
    *,
    summary: dict[str, Any],
    chunk_summaries: list[dict[str, Any]],
) -> pd.DataFrame:
    """Build report-ready provenance and pipeline-scope rows."""

    start = summary.get("pilot_start_date", "")
    end = summary.get("pilot_end_date", "")
    rows: list[dict[str, str]] = [
        {
            "section": "pilot",
            "metric": "pilot window",
            "value": f"{start} to {end} inclusive",
            "notes": "Bounded 8-week descriptive pilot.",
        },
        {
            "section": "pilot",
            "metric": "weekly frequency",
            "value": "Saturday-to-Friday",
            "notes": "Weekly bins end on Fridays.",
        },
        {
            "section": "universe",
            "metric": "universe size",
            "value": _stringify(summary.get("universe_size")),
            "notes": "TEJ-based fixed top-50 market-cap listed-stock universe.",
        },
        {
            "section": "panel",
            "metric": "expected stock-week rows",
            "value": _stringify(summary.get("expected_rows")),
            "notes": "Universe size multiplied by week count.",
        },
        {
            "section": "news counts",
            "metric": "main news-count definition",
            "value": str(
                summary.get(
                    "count_definition",
                    "sum_of_stock_day_unique_document_counts",
                )
            ),
            "notes": "Main column: news_count_unique_urls.",
        },
        {
            "section": "news counts",
            "metric": "matched_rows role",
            "value": str(summary.get("matched_rows_role", "diagnostic_only")),
            "notes": "Diagnostic count only.",
        },
        {
            "section": "news counts",
            "metric": "cross_day_url_deduplicated",
            "value": _stringify(summary.get("cross_day_url_deduplicated", False)),
            "notes": "Current pilot is not full ticker-week URL deduplication.",
        },
        {
            "section": "indices",
            "metric": "Hype Index computed",
            "value": _stringify(summary.get("hype_index_computed", True)),
            "notes": "Consumed from Goal 3C outputs.",
        },
        {
            "section": "indices",
            "metric": "market-cap-adjusted Hype computed",
            "value": _stringify(summary.get("market_cap_adjusted_hype_computed", True)),
            "notes": "Attention-to-size ratio, not normalized to sum to 1.",
        },
    ]

    if not chunk_summaries:
        rows.append(
            {
                "section": "acquisition",
                "metric": "GDELT chunk summaries supplied",
                "value": "false",
                "notes": "Optional acquisition-summary details were not supplied.",
            }
        )
        return pd.DataFrame(rows)

    candidate_files = sum(_candidate_file_count(item) for item in chunk_summaries)
    files_processed = sum(
        _chunk_number(item, "files_processed") for item in chunk_summaries
    )
    files_missing = sum(
        _chunk_number(item, "files_missing") for item in chunk_summaries
    )
    files_failed = sum(_chunk_number(item, "files_failed") for item in chunk_summaries)
    matched_rows = sum(_chunk_number(item, "matched_rows") for item in chunk_summaries)
    unique_urls = sum(_chunk_number(item, "unique_urls") for item in chunk_summaries)
    missing_file_ratio = files_missing / candidate_files if candidate_files else None

    rows.extend(
        [
            {
                "section": "acquisition",
                "metric": "GDELT chunk summaries supplied",
                "value": "true",
                "notes": f"{len(chunk_summaries)} chunk summary file(s).",
            },
            {
                "section": "acquisition",
                "metric": "candidate files",
                "value": _stringify(candidate_files),
                "notes": "Sum of uncapped candidate files when available.",
            },
            {
                "section": "acquisition",
                "metric": "files processed",
                "value": _stringify(files_processed),
                "notes": "Successful GDELT raw files processed.",
            },
            {
                "section": "acquisition",
                "metric": "files missing",
                "value": _stringify(files_missing),
                "notes": "HTTP 404 or missing raw archive files.",
            },
            {
                "section": "acquisition",
                "metric": "files failed",
                "value": _stringify(files_failed),
                "notes": "Non-missing processing failures.",
            },
            {
                "section": "acquisition",
                "metric": "missing-file ratio",
                "value": _stringify(missing_file_ratio),
                "notes": "files missing divided by candidate files.",
            },
            {
                "section": "acquisition",
                "metric": "matched rows",
                "value": _stringify(matched_rows),
                "notes": "Diagnostic matched-row count from chunk summaries.",
            },
            {
                "section": "acquisition",
                "metric": "unique URLs",
                "value": _stringify(unique_urls),
                "notes": "Chunk-level unique URL diagnostics.",
            },
        ]
    )
    return pd.DataFrame(rows)


def build_news_acquisition_summary(
    chunk_summaries: list[dict[str, Any]],
) -> pd.DataFrame:
    """Build per-chunk and combined GDELT acquisition diagnostics."""

    rows: list[dict[str, Any]] = []
    for index, item in enumerate(chunk_summaries, start=1):
        candidate_files = _candidate_file_count(item)
        files_processed = _chunk_number(item, "files_processed")
        files_missing = _chunk_number(item, "files_missing")
        files_failed = _chunk_number(item, "files_failed")
        rows.append(
            {
                "chunk": f"chunk_{index}",
                "start_date": item.get("start_date", ""),
                "end_date": item.get("end_date", ""),
                "candidate_files": candidate_files,
                "files_processed": files_processed,
                "files_missing": files_missing,
                "files_failed": files_failed,
                "matched_rows": _chunk_number(item, "matched_rows"),
                "unique_urls": _chunk_number(item, "unique_urls"),
                "missing_file_ratio": (
                    files_missing / candidate_files if candidate_files else None
                ),
                "completed": item.get("completed", ""),
                "worker_backend": item.get("worker_backend", ""),
                "workers": item.get("workers", ""),
            }
        )

    if rows:
        frame = pd.DataFrame(rows)
        numeric_columns = [
            "candidate_files",
            "files_processed",
            "files_missing",
            "files_failed",
            "matched_rows",
            "unique_urls",
        ]
        totals = {
            "chunk": "combined",
            "start_date": frame["start_date"].min(),
            "end_date": frame["end_date"].max(),
            **{column: frame[column].sum() for column in numeric_columns},
            "completed": frame["completed"].astype(str).str.lower().eq("true").all(),
            "worker_backend": "mixed"
            if frame["worker_backend"].nunique() > 1
            else frame["worker_backend"].iloc[0],
            "workers": "mixed"
            if frame["workers"].nunique() > 1
            else frame["workers"].iloc[0],
        }
        totals["missing_file_ratio"] = (
            totals["files_missing"] / totals["candidate_files"]
            if totals["candidate_files"]
            else None
        )
        return pd.concat([frame, pd.DataFrame([totals])], ignore_index=True)

    return pd.DataFrame(
        [
            {
                "chunk": "not_supplied",
                "start_date": "",
                "end_date": "",
                "candidate_files": 0,
                "files_processed": 0,
                "files_missing": 0,
                "files_failed": 0,
                "matched_rows": 0,
                "unique_urls": 0,
                "missing_file_ratio": None,
                "completed": "",
                "worker_backend": "",
                "workers": "",
            }
        ]
    )


def build_weekly_news_summary(weekly_summary: pd.DataFrame) -> pd.DataFrame:
    """Build the curated weekly news and Hype diagnostic table."""

    frame = weekly_summary.copy()
    denominator = frame["nonzero_stock_count"] + frame["zero_stock_count"]
    frame["zero_stock_ratio"] = frame["zero_stock_count"] / denominator
    columns = [
        "week_index",
        "week_start",
        "week_end",
        "weekly_total_news_count_unique_urls",
        "nonzero_stock_count",
        "zero_stock_count",
        "zero_stock_ratio",
        "ticker_with_max_raw_hype",
        "max_raw_hype",
        "ticker_with_max_market_cap_adjusted_hype",
        "max_market_cap_adjusted_hype",
        "raw_hype_sum",
        "market_cap_weight_sum",
    ]
    return frame[_ordered_columns(frame, columns)].sort_values("week_index")


def build_weekly_hype_summary(weekly_summary: pd.DataFrame) -> pd.DataFrame:
    """Build the curated weekly Hype summary table."""

    columns = [
        "week_index",
        "week_start",
        "week_end",
        "is_missing_hype_week",
        "raw_hype_sum",
        "market_cap_weight_sum",
        "ticker_with_max_raw_hype",
        "max_raw_hype",
        "ticker_with_max_market_cap_adjusted_hype",
        "max_market_cap_adjusted_hype",
    ]
    return weekly_summary[_ordered_columns(weekly_summary, columns)].sort_values(
        "week_index"
    )


def build_pooled_stock_tables(
    pooled_stock_summary: pd.DataFrame,
    *,
    top_n: int,
) -> dict[str, pd.DataFrame]:
    """Build pooled stock-level tables used in the report."""

    table_specs = {
        "top_stock_news_counts": (
            "total_news_count_unique_urls",
            [
                "ticker",
                "official_chinese_name",
                "official_english_name",
                "industry",
                "total_news_count_unique_urls",
                "nonzero_week_count",
                "zero_week_count",
                "pooled_raw_hype",
                "pooled_market_cap_weight",
            ],
        ),
        "top_pooled_raw_hype_stocks": (
            "pooled_raw_hype",
            [
                "ticker",
                "official_chinese_name",
                "official_english_name",
                "industry",
                "total_news_count_unique_urls",
                "pooled_raw_hype",
                "pooled_market_cap_weight",
                "pooled_attention_size_imbalance",
            ],
        ),
        "top_pooled_market_cap_adjusted_hype_stocks": (
            "pooled_market_cap_adjusted_hype",
            [
                "ticker",
                "official_chinese_name",
                "official_english_name",
                "industry",
                "total_news_count_unique_urls",
                "pooled_raw_hype",
                "pooled_market_cap_weight",
                "pooled_market_cap_adjusted_hype",
            ],
        ),
        "top_pooled_attention_size_imbalance_stocks": (
            "absolute_pooled_attention_size_imbalance",
            [
                "ticker",
                "official_chinese_name",
                "official_english_name",
                "industry",
                "total_news_count_unique_urls",
                "pooled_raw_hype",
                "pooled_market_cap_weight",
                "pooled_attention_size_imbalance",
                "pooled_market_cap_adjusted_hype",
            ],
        ),
    }
    pooled = pooled_stock_summary.copy()
    pooled["absolute_pooled_attention_size_imbalance"] = pooled[
        "pooled_attention_size_imbalance"
    ].abs()
    tables: dict[str, pd.DataFrame] = {}
    for name, (metric, columns) in table_specs.items():
        table = _top_stocks(pooled, metric=metric, top_n=top_n)
        tables[name] = table[_ordered_columns(table, columns)]
    return tables


def build_zero_news_summary(stock_summary: pd.DataFrame) -> pd.DataFrame:
    """Build a stock-level zero-news diagnostic table."""

    frame = stock_summary.copy()
    week_denominator = frame["zero_week_count"] + frame["nonzero_week_count"]
    frame["zero_week_ratio"] = frame["zero_week_count"] / week_denominator
    columns = [
        *_metadata_columns(frame),
        "zero_week_count",
        "nonzero_week_count",
        "zero_week_ratio",
        "total_news_count_unique_urls",
    ]
    return (
        frame[_ordered_columns(frame, columns)]
        .sort_values(
            ["zero_week_count", "total_news_count_unique_urls", "ticker"],
            ascending=[False, True, True],
            kind="stable",
        )
        .reset_index(drop=True)
    )


def build_data_source_summary(
    *,
    market_inputs: MarketReportInputs,
    hype_summary: dict[str, Any],
    chunk_summaries: list[dict[str, Any]],
) -> pd.DataFrame:
    """Summarize local data sources used by the notebook-ready artifacts."""

    chunk_count = len(chunk_summaries)
    matched_rows = sum(_chunk_number(item, "matched_rows") for item in chunk_summaries)
    return pd.DataFrame(
        [
            {
                "source": "TEJ daily market panel",
                "period": (
                    f"{market_inputs.market_background_start} to "
                    f"{market_inputs.market_background_end}"
                ),
                "frequency": "trading day",
                "fields": "close, shares_outstanding, market_cap, volume, daily weights",
                "use": "one-year market background and market structure",
            },
            {
                "source": "TEJ adjusted return data",
                "period": (
                    f"{market_inputs.market_background_start} to "
                    f"{market_inputs.market_background_end}"
                ),
                "frequency": "trading day",
                "fields": "adjusted close, simple return, log return",
                "use": "equal-weight return proxy, weekly returns, realized volatility",
            },
            {
                "source": "TEJ weekly market-cap weights",
                "period": (
                    f"{market_inputs.market_background_start} to "
                    f"{market_inputs.market_background_end}"
                ),
                "frequency": "Saturday-to-Friday week label",
                "fields": "weight_date, market_cap, weekly_market_cap_weight",
                "use": "existing Hype size denominator convention",
            },
            {
                "source": "TEJ top-50 universe and company metadata",
                "period": "constituent date 2025-03-31",
                "frequency": "fixed universe",
                "fields": "ticker, Chinese name, English name, industry",
                "use": "stock labels and sector aggregation",
            },
            {
                "source": "GDELT manual-v5 news data",
                "period": (
                    f"{hype_summary.get('pilot_start_date', '')} to "
                    f"{hype_summary.get('pilot_end_date', '')}"
                ),
                "frequency": "15-minute raw GKG files aggregated weekly",
                "fields": "stock-day unique document counts, matched-row diagnostics",
                "use": (
                    f"8-week Hype attention counts from {chunk_count} chunks; "
                    f"diagnostic matched rows={_stringify(matched_rows)}"
                ),
            },
            {
                "source": "Goal 3C Hype panel",
                "period": (
                    f"{hype_summary.get('pilot_start_date', '')} to "
                    f"{hype_summary.get('pilot_end_date', '')}"
                ),
                "frequency": "weekly, Saturday-to-Friday",
                "fields": "raw_hype, market_cap_adjusted_hype, weekly weights",
                "use": "main 8-week Hype analysis and notebook-ready figures",
            },
        ]
    )


def build_tej_market_validation_summary(
    market_inputs: MarketReportInputs,
) -> pd.DataFrame:
    """Build a compact TEJ market validation summary from local validation JSON."""

    validation = market_inputs.validation_summary
    counts = validation.get("counts", {})
    checks = validation.get("checks", {})
    failed_checks = validation.get("failed_checks", [])
    status = "passed" if not failed_checks and all(checks.values()) else "failed"
    rows = [
        ("validation", "validation_status", status, "Derived from failed_checks."),
        (
            "coverage",
            "daily_ticker_count",
            counts.get("daily_ticker_count"),
            "Expected selected universe size is 50.",
        ),
        (
            "coverage",
            "trading_date_count",
            counts.get("trading_date_count"),
            "One-year TEJ market background trading dates.",
        ),
        (
            "coverage",
            "daily_market_panel_rows",
            counts.get("daily_market_panel_rows"),
            "Ticker-date rows in the processed TEJ daily panel.",
        ),
        (
            "coverage",
            "weekly_count",
            counts.get("weekly_count"),
            "Weekly market-cap weight dates.",
        ),
        (
            "coverage",
            "weekly_market_cap_weight_rows",
            counts.get("weekly_market_cap_weight_rows"),
            "Ticker-week rows in weekly market weights.",
        ),
        (
            "date_range",
            "daily_min_date",
            counts.get("daily_min_date"),
            "Observed first TEJ trading date.",
        ),
        (
            "date_range",
            "daily_max_date",
            counts.get("daily_max_date"),
            "Observed last TEJ trading date.",
        ),
    ]
    return pd.DataFrame(
        [
            {
                "section": section,
                "metric": metric,
                "value": _stringify(value),
                "notes": notes,
            }
            for section, metric, value, notes in rows
        ]
    )


def build_universe_summary(market_inputs: MarketReportInputs) -> pd.DataFrame:
    """Build one-row-per-stock market structure summary."""

    daily = market_inputs.daily_market_panel.sort_values(["ticker", "date"]).copy()
    grouped = daily.groupby("ticker", as_index=False).agg(
        mean_market_cap=("market_cap", "mean"),
        mean_daily_market_cap_weight=("daily_market_cap_weight", "mean"),
        first_market_cap=("market_cap", "first"),
        last_market_cap=("market_cap", "last"),
        first_daily_market_cap_weight=("daily_market_cap_weight", "first"),
        last_daily_market_cap_weight=("daily_market_cap_weight", "last"),
    )
    metadata = market_inputs.universe[
        [
            "ticker",
            "official_chinese_name",
            "official_english_name",
            "industry",
        ]
    ].copy()
    frame = metadata.merge(grouped, on="ticker", how="left", validate="one_to_one")
    return frame.sort_values(
        ["mean_market_cap", "ticker"],
        ascending=[False, True],
        kind="stable",
    ).reset_index(drop=True)


def build_sector_market_structure_summary(
    universe_summary: pd.DataFrame,
) -> pd.DataFrame:
    """Aggregate market structure by TEJ industry."""

    total_stocks = len(universe_summary)
    frame = (
        universe_summary.groupby("industry", as_index=False)
        .agg(
            stock_count=("ticker", "nunique"),
            total_mean_daily_market_cap_weight=(
                "mean_daily_market_cap_weight",
                "sum",
            ),
            mean_daily_market_cap_weight=("mean_daily_market_cap_weight", "mean"),
            total_mean_market_cap=("mean_market_cap", "sum"),
            average_market_cap=("mean_market_cap", "mean"),
        )
        .sort_values(
            ["total_mean_daily_market_cap_weight", "industry"],
            ascending=[False, True],
            kind="stable",
        )
    )
    frame["share_of_universe_stocks"] = frame["stock_count"] / total_stocks
    return frame.reset_index(drop=True)


def _equal_weight_daily_returns(adjusted_returns: pd.DataFrame) -> pd.DataFrame:
    return (
        adjusted_returns.groupby("date", as_index=False)["simple_return"]
        .mean()
        .rename(columns={"simple_return": "equal_weight_simple_return"})
        .sort_values("date", kind="stable")
        .reset_index(drop=True)
    )


def _return_statistics(
    returns: pd.Series,
    *,
    sample_label: str,
) -> dict[str, Any]:
    clean = returns.dropna()
    cumulative = (1.0 + clean).prod() - 1.0 if not clean.empty else math.nan
    return {
        "sample": sample_label,
        "trading_days": int(len(clean)),
        "mean_daily_return": clean.mean(),
        "daily_volatility": clean.std(ddof=1),
        "annualized_volatility": clean.std(ddof=1) * math.sqrt(252),
        "skewness": clean.skew(),
        "kurtosis": clean.kurt(),
        "min": clean.min(),
        "max": clean.max(),
        "quantile_5pct": clean.quantile(0.05),
        "quantile_95pct": clean.quantile(0.95),
        "cumulative_return": cumulative,
    }


def build_basic_return_statistics(
    market_inputs: MarketReportInputs,
) -> pd.DataFrame:
    """Compare equal-weight return statistics for full sample and Hype window."""

    ew_returns = _equal_weight_daily_returns(market_inputs.adjusted_returns)
    start = pd.Timestamp(market_inputs.market_background_start)
    end = pd.Timestamp(market_inputs.market_background_end)
    hype_start = pd.Timestamp(market_inputs.hype_trading_start)
    hype_end = pd.Timestamp(market_inputs.hype_trading_end)
    full = ew_returns.loc[ew_returns["date"].between(start, end)]
    hype = ew_returns.loc[ew_returns["date"].between(hype_start, hype_end)]
    return pd.DataFrame(
        [
            _return_statistics(
                full["equal_weight_simple_return"],
                sample_label="full_market_background",
            ),
            _return_statistics(
                hype["equal_weight_simple_return"],
                sample_label="hype_trading_window",
            ),
        ]
    )


def build_weekly_stock_market_metrics(
    *,
    adjusted_returns: pd.DataFrame,
    hype_panel: pd.DataFrame,
) -> pd.DataFrame:
    """Build contemporaneous weekly stock returns and realized volatility."""

    weeks = (
        hype_panel[["week_index", "week_start", "week_end"]]
        .drop_duplicates()
        .sort_values("week_index", kind="stable")
    )
    returns = adjusted_returns.copy()
    rows: list[pd.DataFrame] = []
    for _, week in weeks.iterrows():
        start = pd.Timestamp(week["week_start"])
        end = pd.Timestamp(week["week_end"])
        weekly = returns.loc[returns["date"].between(start, end)].copy()
        if weekly.empty:
            continue
        weekly["week_index"] = int(week["week_index"])
        weekly["week_start"] = str(week["week_start"])
        weekly["week_end"] = str(week["week_end"])
        rows.append(weekly)
    if not rows:
        raise HypeReportError("No TEJ return rows overlap the Hype weeks.")
    expanded = pd.concat(rows, ignore_index=True)
    metrics = (
        expanded.groupby(["ticker", "week_index", "week_start", "week_end"])
        .agg(
            weekly_return=(
                "simple_return",
                lambda values: (1.0 + values.dropna()).prod() - 1.0,
            ),
            weekly_realized_volatility=(
                "log_return",
                lambda values: math.sqrt(float((values.dropna() ** 2).sum())),
            ),
            trading_days=("date", "nunique"),
        )
        .reset_index()
    )
    return metrics.sort_values(["week_index", "ticker"], kind="stable")


def build_hype_market_panel(
    *,
    hype_panel: pd.DataFrame,
    market_inputs: MarketReportInputs,
) -> pd.DataFrame:
    """Merge Hype panel rows with contemporaneous weekly return diagnostics."""

    panel = hype_panel.copy()
    panel["ticker"] = _ticker_text(panel["ticker"])
    metrics = build_weekly_stock_market_metrics(
        adjusted_returns=market_inputs.adjusted_returns,
        hype_panel=panel,
    )
    merged = panel.merge(
        metrics[
            [
                "ticker",
                "week_index",
                "weekly_return",
                "weekly_realized_volatility",
                "trading_days",
            ]
        ],
        on=["ticker", "week_index"],
        how="left",
        validate="one_to_one",
    )
    return merged.sort_values(["week_index", "ticker"], kind="stable")


def _correlation_row(
    *,
    frame: pd.DataFrame,
    variable: str,
    target: str,
) -> dict[str, Any]:
    clean = frame[[variable, target]].dropna()
    return {
        "variable": variable,
        "target": target,
        "pearson_correlation": clean[variable].corr(clean[target], method="pearson"),
        "spearman_correlation": clean[variable].corr(clean[target], method="spearman"),
        "n_observations": int(len(clean)),
        "interpretation_note": (
            "Contemporaneous descriptive correlation only; not a predictive test."
        ),
    }


def build_hype_return_volatility_correlation_summary(
    hype_market_panel: pd.DataFrame,
) -> pd.DataFrame:
    """Build contemporaneous Hype, return, and volatility correlations."""

    variables = [
        "raw_hype",
        "market_cap_adjusted_hype",
        "news_count_unique_urls",
    ]
    targets = ["weekly_return", "weekly_realized_volatility"]
    rows = [
        _correlation_row(frame=hype_market_panel, variable=variable, target=target)
        for variable in variables
        for target in targets
    ]
    return pd.DataFrame(rows)


def build_key_stock_case_study_summary(
    *,
    hype_market_panel: pd.DataFrame,
    pooled_stock_summary: pd.DataFrame,
    key_tickers: Iterable[str],
) -> pd.DataFrame:
    """Build weekly case-study rows for selected stocks."""

    tickers = [str(ticker) for ticker in key_tickers]
    frame = hype_market_panel.loc[hype_market_panel["ticker"].isin(tickers)].copy()
    frame = frame.merge(
        pooled_stock_summary[
            [
                "ticker",
                "total_news_count_unique_urls",
                "pooled_raw_hype",
                "pooled_market_cap_weight",
                "pooled_market_cap_adjusted_hype",
            ]
        ],
        on="ticker",
        how="left",
        validate="many_to_one",
    )
    columns = [
        "ticker",
        "official_chinese_name",
        "official_english_name",
        "industry",
        "total_news_count_unique_urls",
        "pooled_raw_hype",
        "pooled_market_cap_weight",
        "pooled_market_cap_adjusted_hype",
        "week_index",
        "week_start",
        "week_end",
        "news_count_unique_urls",
        "raw_hype",
        "market_cap_adjusted_hype",
        "weekly_market_cap_weight",
        "weekly_return",
        "weekly_realized_volatility",
        "trading_days",
    ]
    return frame[_ordered_columns(frame, columns)].sort_values(
        ["ticker", "week_index"],
        kind="stable",
    )


def build_sector_weekly_hype_summary(hype_panel: pd.DataFrame) -> pd.DataFrame:
    """Aggregate stock-week Hype rows to industry-week rows."""

    frame = hype_panel.copy()
    if "industry" not in frame.columns:
        raise HypeReportError("Hype panel must include industry for sector tables.")
    grouped = (
        frame.groupby(["industry", "week_index", "week_start", "week_end"])
        .agg(
            sector_news_count=("news_count_unique_urls", "sum"),
            weekly_total_news_count_unique_urls=(
                "weekly_total_news_count_unique_urls",
                "first",
            ),
            sector_market_cap_weight=("weekly_market_cap_weight", "sum"),
            stock_count=("ticker", "nunique"),
            nonzero_stock_count=(
                "news_count_unique_urls",
                lambda values: int((values > 0).sum()),
            ),
        )
        .reset_index()
    )
    grouped["sector_raw_hype"] = (
        grouped["sector_news_count"] / grouped["weekly_total_news_count_unique_urls"]
    )
    grouped["sector_market_cap_adjusted_hype"] = (
        grouped["sector_raw_hype"] / grouped["sector_market_cap_weight"]
    )
    return grouped.sort_values(["week_index", "industry"], kind="stable").reset_index(
        drop=True
    )


def _industry_parts(industry: Any) -> tuple[str, str]:
    text = " ".join(str(industry).split())
    if not text:
        return "", ""
    parts = text.split(maxsplit=1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def build_sector_pooled_hype_summary(
    *,
    hype_panel: pd.DataFrame,
    market_inputs: MarketReportInputs | None = None,
) -> pd.DataFrame:
    """Build pooled 8-week sector-level Hype summary rows."""

    frame = hype_panel.copy()
    frame["ticker"] = _ticker_text(frame["ticker"])
    frame["_market_cap_pool_value"] = _market_cap_pool_values(
        hype_panel=frame,
        market_inputs=market_inputs,
    )
    total_news = frame["news_count_unique_urls"].sum()
    total_market_cap_pool = frame["_market_cap_pool_value"].sum()
    sector_weekly = build_sector_weekly_hype_summary(frame)
    grouped = (
        frame.groupby("industry", as_index=False)
        .agg(
            stock_count=("ticker", "nunique"),
            total_news_count=("news_count_unique_urls", "sum"),
            pooled_market_cap_pool_value=("_market_cap_pool_value", "sum"),
        )
        .merge(
            sector_weekly.groupby("industry", as_index=False).agg(
                nonzero_week_count=(
                    "sector_news_count",
                    lambda values: int((values > 0).sum()),
                )
            ),
            on="industry",
            how="left",
            validate="one_to_one",
        )
    )
    grouped["pooled_sector_raw_hype"] = grouped["total_news_count"] / total_news
    grouped["pooled_sector_market_cap_weight"] = (
        grouped["pooled_market_cap_pool_value"] / total_market_cap_pool
    )
    grouped["pooled_sector_market_cap_adjusted_hype"] = (
        grouped["pooled_sector_raw_hype"] / grouped["pooled_sector_market_cap_weight"]
    )
    grouped["pooled_sector_attention_size_imbalance"] = (
        grouped["pooled_sector_raw_hype"] - grouped["pooled_sector_market_cap_weight"]
    )
    parts = grouped["industry"].map(_industry_parts)
    grouped["industry_code"] = [item[0] for item in parts]
    grouped["industry_chinese_label"] = [item[1] for item in parts]
    columns = [
        "industry",
        "industry_code",
        "industry_chinese_label",
        "stock_count",
        "total_news_count",
        "pooled_sector_raw_hype",
        "pooled_sector_market_cap_weight",
        "pooled_sector_market_cap_adjusted_hype",
        "pooled_sector_attention_size_imbalance",
        "nonzero_week_count",
    ]
    return (
        grouped[columns]
        .sort_values(
            ["pooled_sector_raw_hype", "industry"],
            ascending=[False, True],
            kind="stable",
        )
        .reset_index(drop=True)
    )


def build_tej_industry_label_mapping(
    sector_pooled: pd.DataFrame,
) -> pd.DataFrame:
    """Build TEJ industry code and Chinese-label mapping table."""

    columns = [
        "industry_code",
        "industry_chinese_label",
        "industry",
        "stock_count",
        "pooled_sector_raw_hype",
        "pooled_sector_market_cap_weight",
        "pooled_sector_market_cap_adjusted_hype",
    ]
    frame = sector_pooled[_ordered_columns(sector_pooled, columns)].rename(
        columns={"industry": "full_original_industry_label"}
    )
    return frame.sort_values(
        ["industry_code", "full_original_industry_label"],
        kind="stable",
    ).reset_index(drop=True)


def build_top_pooled_sector_market_cap_adjusted_hype(
    sector_pooled: pd.DataFrame,
    *,
    top_n: int,
) -> pd.DataFrame:
    """Build top pooled sector attention-to-size table."""

    columns = [
        "industry",
        "industry_code",
        "industry_chinese_label",
        "stock_count",
        "total_news_count",
        "pooled_sector_raw_hype",
        "pooled_sector_market_cap_weight",
        "pooled_sector_market_cap_adjusted_hype",
        "pooled_sector_attention_size_imbalance",
    ]
    return (
        sector_pooled.sort_values(
            ["pooled_sector_market_cap_adjusted_hype", "industry"],
            ascending=[False, True],
            kind="stable",
        )
        .head(top_n)[_ordered_columns(sector_pooled, columns)]
        .reset_index(drop=True)
    )


def build_market_quant_tables(
    *,
    inputs: HypeReportInputs,
    market_inputs: MarketReportInputs,
    key_tickers: Iterable[str],
    top_n: int,
) -> dict[str, pd.DataFrame]:
    """Build notebook-ready Goal 4B market and sector tables."""

    universe_summary = build_universe_summary(market_inputs)
    sector_market = build_sector_market_structure_summary(universe_summary)
    hype_market_panel = build_hype_market_panel(
        hype_panel=inputs.panel,
        market_inputs=market_inputs,
    )
    pooled_stock_summary = build_stock_pooled_hype_summary(
        hype_panel=inputs.panel,
        market_inputs=market_inputs,
    )
    sector_weekly = build_sector_weekly_hype_summary(inputs.panel)
    sector_pooled = build_sector_pooled_hype_summary(
        hype_panel=inputs.panel,
        market_inputs=market_inputs,
    )
    return {
        "data_source_summary": build_data_source_summary(
            market_inputs=market_inputs,
            hype_summary=inputs.summary,
            chunk_summaries=inputs.chunk_summaries,
        ),
        "tej_market_validation_summary": build_tej_market_validation_summary(
            market_inputs
        ),
        "universe_summary": universe_summary,
        "sector_market_structure_summary": sector_market,
        "basic_return_statistics_full_vs_hype_window": build_basic_return_statistics(
            market_inputs
        ),
        "hype_return_volatility_correlation_summary": (
            build_hype_return_volatility_correlation_summary(hype_market_panel)
        ),
        "key_stock_case_study_summary": build_key_stock_case_study_summary(
            hype_market_panel=hype_market_panel,
            pooled_stock_summary=pooled_stock_summary,
            key_tickers=key_tickers,
        ),
        "sector_pooled_hype_summary": sector_pooled,
        "top_pooled_sector_market_cap_adjusted_hype": (
            build_top_pooled_sector_market_cap_adjusted_hype(
                sector_pooled,
                top_n=top_n,
            )
        ),
        "tej_industry_label_mapping": build_tej_industry_label_mapping(sector_pooled),
        "sector_weekly_hype_summary": sector_weekly,
    }


def methodology_notes_markdown() -> str:
    """Return concise report-ready methodology notes for the pilot artifacts."""

    return "\n".join(
        [
            "# Methodology Notes",
            "",
            "- This is a Taiwan-market weekly adaptation, not an exact full-year "
            "replication.",
            "- N_{i,w} is operationalized as the sum of stock-day unique GDELT "
            "document counts within week w.",
            "- The current pilot does not perform full ticker-week cross-day URL "
            "deduplication.",
            "- matched_rows is diagnostic only.",
            "- GDELT captures global media/entity attention, not pure Taiwan local "
            "financial-news attention.",
            "- market_cap_adjusted_hype is an attention-to-size ratio and is not "
            "normalized to sum to 1.",
            "- Cross-sectional report rankings use pooled 8-week Hype: total "
            "stock news divided by total pilot news, with pooled market-cap "
            "weight from aligned weekly TEJ market caps.",
            "- Equal-week arithmetic mean Hype is not used for stock or sector "
            "cross-sectional ranking because it does not generally equal pooled "
            "news share over the pilot window.",
            "- Weekly Hype is retained for time-path heatmaps, case studies, and "
            "contemporaneous descriptive return / volatility comparisons.",
            "- No forecasting, backtesting, portfolio optimization, or investment "
            "advice is produced.",
            "",
        ]
    )


def build_report_tables(
    *,
    inputs: HypeReportInputs,
    results_dir: Path,
    top_n: int,
    market_inputs: MarketReportInputs | None = None,
    key_tickers: Iterable[str] = DEFAULT_KEY_TICKERS,
) -> tuple[dict[str, tuple[Path, Path]], Path]:
    """Write required report tables under the validated results directory."""

    results_dir.mkdir(parents=True, exist_ok=True)
    pooled_stock_summary = build_stock_pooled_hype_summary(
        hype_panel=inputs.panel,
        market_inputs=market_inputs,
    )
    tables = {
        "pipeline_validation_summary": build_data_pipeline_summary(
            summary=inputs.summary,
            chunk_summaries=inputs.chunk_summaries,
        ),
        "news_acquisition_summary": build_news_acquisition_summary(
            inputs.chunk_summaries
        ),
        "weekly_news_totals": build_weekly_news_summary(inputs.weekly_summary),
        "weekly_hype_summary": build_weekly_hype_summary(inputs.weekly_summary),
        "stock_pooled_hype_summary": pooled_stock_summary,
        **build_pooled_stock_tables(pooled_stock_summary, top_n=top_n),
        "zero_news_stock_summary": build_zero_news_summary(inputs.stock_summary),
    }
    if market_inputs is not None:
        tables.update(
            build_market_quant_tables(
                inputs=inputs,
                market_inputs=market_inputs,
                key_tickers=key_tickers,
                top_n=top_n,
            )
        )
    table_paths = {
        name: _write_table_pair(frame, output_dir=results_dir, name=name)
        for name, frame in tables.items()
    }
    notes_path = results_dir / "methodology_notes.md"
    notes_path.write_text(methodology_notes_markdown(), encoding="utf-8")
    return table_paths, notes_path


def _truncate_label(value: str, *, max_length: int = 42) -> str:
    text = " ".join(str(value).split())
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "."


def _figure_safe_label(value: Any) -> str:
    """Return a Matplotlib-default-font-safe label for figure text."""

    text = " ".join(str(value).split())
    if text.isascii():
        return text
    ascii_text = "".join(character for character in text if character.isascii()).strip()
    return ascii_text or text


def _stock_label(row: pd.Series) -> str:
    ticker = str(row.get("ticker", "")).strip()
    english = str(row.get("official_english_name", "")).strip()
    chinese = str(row.get("official_chinese_name", "")).strip()
    name = english or chinese
    if not name:
        return ticker
    return f"{ticker} - {_truncate_label(name)}"


def _stock_label_lookup(stock_summary: pd.DataFrame) -> dict[str, str]:
    return {
        str(row["ticker"]): _stock_label(row) for _, row in stock_summary.iterrows()
    }


def _week_label(week_index: Any, week_end: Any) -> str:
    return f"W{int(week_index)}\n{pd.Timestamp(week_end).strftime('%m-%d')}"


def _week_labels(panel: pd.DataFrame) -> list[str]:
    weeks = (
        panel[["week_index", "week_end"]]
        .drop_duplicates()
        .sort_values("week_index", kind="stable")
    )
    return [_week_label(row.week_index, row.week_end) for _, row in weeks.iterrows()]


def _style_axis_numbers(axis: Any) -> None:
    from matplotlib.ticker import ScalarFormatter

    formatter = ScalarFormatter(useOffset=False)
    formatter.set_scientific(False)
    axis.set_major_formatter(formatter)


def _save_figure(fig: Any, path: Path, *, dpi: int) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")


def render_report_figures(
    *,
    panel: pd.DataFrame,
    weekly_summary: pd.DataFrame,
    stock_summary: pd.DataFrame,
    pooled_stock_summary: pd.DataFrame,
    figures_dir: Path,
    top_n: int,
    figure_dpi: int,
) -> tuple[dict[str, Path], list[FigureSpec]]:
    """Render the required Matplotlib PNG figures."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures_dir.mkdir(parents=True, exist_ok=True)
    figure_paths: dict[str, Path] = {}
    specs: list[FigureSpec] = []
    label_lookup = _stock_label_lookup(pooled_stock_summary)

    weekly = weekly_summary.sort_values("week_index", kind="stable")
    week_labels = [
        _week_label(row.week_index, row.week_end) for _, row in weekly.iterrows()
    ]
    title = "Weekly Total News Count, Taiwan Hype Index Pilot"
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.bar(week_labels, weekly["weekly_total_news_count_unique_urls"])
    ax.set_title(title)
    ax.set_xlabel("Week end")
    ax.set_ylabel("Unique URL count")
    _style_axis_numbers(ax.yaxis)
    path = figures_dir / "weekly_news_counts.png"
    _save_figure(fig, path, dpi=figure_dpi)
    plt.close(fig)
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="bar",
            purpose="Show total pilot news-count volume by week.",
            input_rows_used=len(weekly),
            dpi=figure_dpi,
            x_label="Week end",
            y_label="Unique URL count",
            stock_label_count=0,
        )
    )

    top_total = _top_stocks(
        pooled_stock_summary,
        metric="total_news_count_unique_urls",
        top_n=top_n,
    )
    title = f"Top {top_n} Stocks by Total News Count"
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    labels = [_stock_label(row) for _, row in top_total.iterrows()]
    ax.barh(labels, top_total["total_news_count_unique_urls"])
    ax.invert_yaxis()
    ax.set_title(title)
    ax.set_xlabel("Total unique URL count")
    ax.set_ylabel("Stock")
    _style_axis_numbers(ax.xaxis)
    path = figures_dir / "top_stock_news_counts.png"
    _save_figure(fig, path, dpi=figure_dpi)
    plt.close(fig)
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="horizontal_bar",
            purpose="Rank stocks by total pilot news attention.",
            input_rows_used=len(top_total),
            dpi=figure_dpi,
            x_label="Total unique URL count",
            y_label="Stock",
            stock_label_count=len(top_total),
        )
    )

    top_raw = _top_stocks(
        pooled_stock_summary,
        metric="pooled_raw_hype",
        top_n=top_n,
    )
    title = f"Top {top_n} Stocks by Pooled Raw Hype"
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    labels = [_stock_label(row) for _, row in top_raw.iterrows()]
    ax.barh(labels, top_raw["pooled_raw_hype"])
    ax.invert_yaxis()
    ax.set_title(title)
    ax.set_xlabel("pooled_raw_hype")
    ax.set_ylabel("Stock")
    _style_axis_numbers(ax.xaxis)
    path = figures_dir / "top_pooled_raw_hype_stocks.png"
    _save_figure(fig, path, dpi=figure_dpi)
    plt.close(fig)
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="horizontal_bar",
            purpose="Rank stocks by pooled 8-week raw Hype share.",
            input_rows_used=len(top_raw),
            dpi=figure_dpi,
            x_label="pooled_raw_hype",
            y_label="Stock",
            stock_label_count=len(top_raw),
        )
    )

    raw_heatmap_tickers = top_total["ticker"].astype(str).tolist()
    title = f"Raw Hype Heatmap for Top {top_n} News-Count Stocks"
    path, input_rows = _render_heatmap(
        plt=plt,
        panel=panel,
        tickers=raw_heatmap_tickers,
        label_lookup=label_lookup,
        value_column="raw_hype",
        title=title,
        colorbar_label="raw_hype",
        output_path=figures_dir / "raw_hype_heatmap_top_stocks.png",
        figure_dpi=figure_dpi,
    )
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="heatmap",
            purpose="Compare weekly raw Hype shares for high-news stocks.",
            input_rows_used=input_rows,
            dpi=figure_dpi,
            x_label="Week end",
            y_label="Stock",
            stock_label_count=len(raw_heatmap_tickers),
        )
    )

    top_adjusted = _top_stocks(
        pooled_stock_summary,
        metric="pooled_market_cap_adjusted_hype",
        top_n=top_n,
    )
    adjusted_heatmap_tickers = top_adjusted["ticker"].astype(str).tolist()
    title = f"Market-Cap-Adjusted Hype Heatmap for Top {top_n} Stocks"
    path, input_rows = _render_heatmap(
        plt=plt,
        panel=panel,
        tickers=adjusted_heatmap_tickers,
        label_lookup=label_lookup,
        value_column="market_cap_adjusted_hype",
        title=title,
        colorbar_label="market_cap_adjusted_hype",
        output_path=figures_dir / "market_cap_adjusted_hype_heatmap_top_stocks.png",
        figure_dpi=figure_dpi,
    )
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="heatmap",
            purpose=(
                "Compare weekly attention-to-size ratios for stocks with high "
                "pooled market-cap-adjusted Hype."
            ),
            input_rows_used=input_rows,
            dpi=figure_dpi,
            x_label="Week end",
            y_label="Stock",
            stock_label_count=len(adjusted_heatmap_tickers),
        )
    )

    title = "Pooled Raw Hype vs Pooled Market-Cap Weight"
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    x = pooled_stock_summary["pooled_market_cap_weight"]
    y = pooled_stock_summary["pooled_raw_hype"]
    ax.scatter(x, y, alpha=0.78)
    line_max = max(float(x.max()), float(y.max())) if len(pooled_stock_summary) else 1.0
    ax.plot([0, line_max], [0, line_max], color="0.45", linewidth=1)
    ax.text(line_max, line_max, "y=x", ha="right", va="bottom", fontsize=9)
    ax.set_title(title)
    ax.set_xlabel("pooled_market_cap_weight")
    ax.set_ylabel("pooled_raw_hype")
    _style_axis_numbers(ax.xaxis)
    _style_axis_numbers(ax.yaxis)
    annotate = _top_stocks(
        pooled_stock_summary,
        metric="total_news_count_unique_urls",
        top_n=min(5, top_n),
    )
    for _, row in annotate.iterrows():
        ax.annotate(
            str(row["ticker"]),
            (row["pooled_market_cap_weight"], row["pooled_raw_hype"]),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=8,
        )
    path = figures_dir / "pooled_raw_hype_vs_pooled_market_cap_weight_scatter.png"
    _save_figure(fig, path, dpi=figure_dpi)
    plt.close(fig)
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="scatter",
            purpose=(
                "Show whether pooled news-attention share is above or below "
                "pooled market-cap weight."
            ),
            input_rows_used=len(pooled_stock_summary),
            dpi=figure_dpi,
            x_label="pooled_market_cap_weight",
            y_label="pooled_raw_hype",
            stock_label_count=len(annotate),
        )
    )

    title = "Pooled Raw Hype vs Pooled Market-Cap Weight, Lower-Left Zoom"
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    zoom = pooled_stock_summary.loc[
        pooled_stock_summary["ticker"].astype(str).ne("2330")
    ].copy()
    if zoom.empty:
        zoom = pooled_stock_summary.copy()
    x_zoom = zoom["pooled_market_cap_weight"]
    y_zoom = zoom["pooled_raw_hype"]
    ax.scatter(x_zoom, y_zoom, alpha=0.78)
    x_limit = max(float(x_zoom.quantile(0.95)) * 1.15, float(x_zoom.max()))
    y_limit = max(float(y_zoom.quantile(0.95)) * 1.15, float(y_zoom.max()))
    line_max = max(x_limit, y_limit)
    ax.plot([0, line_max], [0, line_max], color="0.45", linewidth=1)
    ax.set_xlim(left=0, right=x_limit * 1.05 if x_limit else 1.0)
    ax.set_ylim(bottom=0, top=y_limit * 1.05 if y_limit else 1.0)
    ax.set_title(title)
    ax.set_xlabel("pooled_market_cap_weight")
    ax.set_ylabel("pooled_raw_hype")
    _style_axis_numbers(ax.xaxis)
    _style_axis_numbers(ax.yaxis)
    annotate = _top_stocks(
        zoom,
        metric="total_news_count_unique_urls",
        top_n=min(5, top_n),
    )
    for _, row in annotate.iterrows():
        ax.annotate(
            str(row["ticker"]),
            (row["pooled_market_cap_weight"], row["pooled_raw_hype"]),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=8,
        )
    path = figures_dir / "pooled_raw_hype_vs_pooled_market_cap_weight_scatter_zoom.png"
    _save_figure(fig, path, dpi=figure_dpi)
    plt.close(fig)
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="scatter",
            purpose=(
                "Make the lower-left attention-versus-size cluster readable "
                "without changing the full-scale scatter."
            ),
            input_rows_used=len(zoom),
            dpi=figure_dpi,
            x_label="pooled_market_cap_weight",
            y_label="pooled_raw_hype",
            stock_label_count=len(annotate),
        )
    )

    imbalance = pooled_stock_summary.copy()
    imbalance["absolute_pooled_attention_size_imbalance"] = imbalance[
        "pooled_attention_size_imbalance"
    ].abs()
    top_imbalance = (
        imbalance.sort_values(
            ["absolute_pooled_attention_size_imbalance", "ticker"],
            ascending=[False, True],
            kind="stable",
        )
        .head(top_n)
        .sort_values("pooled_attention_size_imbalance", kind="stable")
    )
    title = f"Top {top_n} Pooled Attention-Size Imbalances"
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    labels = [_stock_label(row) for _, row in top_imbalance.iterrows()]
    colors = [
        "tab:blue" if value >= 0 else "tab:orange"
        for value in top_imbalance["pooled_attention_size_imbalance"]
    ]
    ax.barh(labels, top_imbalance["pooled_attention_size_imbalance"], color=colors)
    ax.axvline(0, color="0.35", linewidth=1)
    ax.set_title(title)
    ax.set_xlabel("pooled_raw_hype minus pooled_market_cap_weight")
    ax.set_ylabel("Stock")
    _style_axis_numbers(ax.xaxis)
    path = figures_dir / "pooled_attention_size_imbalance_top_stocks.png"
    _save_figure(fig, path, dpi=figure_dpi)
    plt.close(fig)
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="horizontal_bar",
            purpose="Rank stocks by the largest pooled attention-size imbalance.",
            input_rows_used=len(top_imbalance),
            dpi=figure_dpi,
            x_label="pooled_raw_hype minus pooled_market_cap_weight",
            y_label="Stock",
            stock_label_count=len(top_imbalance),
        )
    )

    title = f"Top {top_n} Stocks by Pooled Market-Cap-Adjusted Hype"
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    labels = [_stock_label(row) for _, row in top_adjusted.iterrows()]
    ax.barh(labels, top_adjusted["pooled_market_cap_adjusted_hype"])
    ax.invert_yaxis()
    ax.set_title(title)
    ax.set_xlabel("pooled_market_cap_adjusted_hype")
    ax.set_ylabel("Stock")
    _style_axis_numbers(ax.xaxis)
    path = figures_dir / "top_pooled_market_cap_adjusted_hype_stocks.png"
    _save_figure(fig, path, dpi=figure_dpi)
    plt.close(fig)
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="horizontal_bar",
            purpose="Rank stocks by pooled attention-to-size ratio.",
            input_rows_used=len(top_adjusted),
            dpi=figure_dpi,
            x_label="pooled_market_cap_adjusted_hype",
            y_label="Stock",
            stock_label_count=len(top_adjusted),
        )
    )

    zero_news = (
        stock_summary.sort_values(
            ["zero_week_count", "total_news_count_unique_urls", "ticker"],
            ascending=[False, True, True],
            kind="stable",
        )
        .head(top_n)
        .reset_index(drop=True)
    )
    title = f"Top {top_n} Stocks by Zero-News Weeks"
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    labels = [_stock_label(row) for _, row in zero_news.iterrows()]
    ax.barh(labels, zero_news["zero_week_count"])
    ax.invert_yaxis()
    ax.set_title(title)
    ax.set_xlabel("Zero-news stock-weeks")
    ax.set_ylabel("Stock")
    _style_axis_numbers(ax.xaxis)
    path = figures_dir / "zero_news_stock_weeks.png"
    _save_figure(fig, path, dpi=figure_dpi)
    plt.close(fig)
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="horizontal_bar",
            purpose="Show stocks with the most zero-news weeks in the pilot.",
            input_rows_used=len(zero_news),
            dpi=figure_dpi,
            x_label="Zero-news stock-weeks",
            y_label="Stock",
            stock_label_count=len(zero_news),
        )
    )

    return figure_paths, specs


def _render_heatmap(
    *,
    plt: Any,
    panel: pd.DataFrame,
    tickers: list[str],
    label_lookup: dict[str, str],
    value_column: str,
    title: str,
    colorbar_label: str,
    output_path: Path,
    figure_dpi: int,
) -> tuple[Path, int]:
    filtered = panel.loc[panel["ticker"].astype(str).isin(tickers)].copy()
    row_labels = [label_lookup.get(ticker, ticker) for ticker in tickers]
    filtered["_row_label"] = filtered["ticker"].astype(str).map(label_lookup)
    filtered["_week_label"] = filtered.apply(
        lambda row: _week_label(row["week_index"], row["week_end"]),
        axis=1,
    )
    pivot = filtered.pivot(
        index="_row_label",
        columns="_week_label",
        values=value_column,
    )
    pivot = pivot.reindex(row_labels)
    pivot = pivot.reindex(_week_labels(panel), axis=1)
    fig, ax = plt.subplots(figsize=(11.4, 6.2))
    image = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto")
    ax.set_title(title)
    ax.set_xlabel("Week end")
    ax.set_ylabel("Stock")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, fontsize=8, rotation=0, ha="center")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([_figure_safe_label(value) for value in pivot.index], fontsize=8)
    colorbar = fig.colorbar(image, ax=ax)
    colorbar.set_label(colorbar_label)
    fig.subplots_adjust(bottom=0.18)
    _save_figure(fig, output_path, dpi=figure_dpi)
    plt.close(fig)
    return output_path, len(filtered)


def _shade_hype_window(ax: Any, market_inputs: MarketReportInputs) -> None:
    ax.axvspan(
        pd.Timestamp(market_inputs.hype_trading_start),
        pd.Timestamp(market_inputs.hype_trading_end),
        color="0.9",
        alpha=0.65,
        zorder=0,
    )


def _annotate_key_points(
    *,
    ax: Any,
    frame: pd.DataFrame,
    key_tickers: Iterable[str],
    x_column: str,
    y_column: str,
) -> int:
    count = 0
    for ticker in key_tickers:
        rows = frame.loc[frame["ticker"].astype(str).eq(str(ticker))].dropna(
            subset=[x_column, y_column]
        )
        if rows.empty:
            continue
        row = rows.loc[rows[y_column].abs().idxmax()]
        ax.annotate(
            str(ticker),
            (row[x_column], row[y_column]),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=8,
        )
        count += 1
    return count


def _selected_sector_label_codes(
    sector_pooled: pd.DataFrame,
    *,
    max_labels: int = 4,
) -> list[str]:
    """Select a small deterministic set of sector outlier labels for figures."""

    if sector_pooled.empty or max_labels <= 0:
        return []

    selections: list[str] = []

    def add_extreme(metric: str, *, ascending: bool) -> None:
        if metric not in sector_pooled.columns or len(selections) >= max_labels:
            return
        ordered = sector_pooled.sort_values(
            [metric, "industry_code"],
            ascending=[ascending, True],
            kind="stable",
        )
        for code in ordered["industry_code"].astype(str):
            if code not in selections:
                selections.append(code)
                break

    add_extreme("pooled_sector_market_cap_weight", ascending=False)
    add_extreme("pooled_sector_attention_size_imbalance", ascending=False)
    add_extreme("pooled_sector_attention_size_imbalance", ascending=True)
    add_extreme("pooled_sector_market_cap_adjusted_hype", ascending=False)
    return selections[:max_labels]


def _annotate_selected_sectors(
    *,
    ax: Any,
    frame: pd.DataFrame,
    label_codes: Iterable[str],
) -> int:
    offsets = [(6, 6), (6, -12), (-28, 8), (-28, -14)]
    count = 0
    for label_code in label_codes:
        rows = frame.loc[frame["industry_code"].astype(str).eq(str(label_code))]
        if rows.empty:
            continue
        row = rows.iloc[0]
        offset = offsets[count % len(offsets)]
        ax.annotate(
            _figure_safe_label(row["industry_code"]),
            (
                row["pooled_sector_market_cap_weight"],
                row["pooled_sector_raw_hype"],
            ),
            xytext=offset,
            textcoords="offset points",
            fontsize=8,
        )
        count += 1
    return count


def _render_sector_heatmap(
    *,
    plt: Any,
    sector_weekly: pd.DataFrame,
    output_path: Path,
    figure_dpi: int,
) -> tuple[Path, int]:
    sector_order = (
        sector_weekly.groupby("industry")["sector_news_count"]
        .sum()
        .sort_values(ascending=False, kind="stable")
        .index.tolist()
    )
    frame = sector_weekly.copy()
    frame["_week_label"] = frame.apply(
        lambda row: _week_label(row["week_index"], row["week_end"]),
        axis=1,
    )
    pivot = frame.pivot(
        index="industry",
        columns="_week_label",
        values="sector_market_cap_adjusted_hype",
    ).reindex(sector_order)
    week_order = [
        _week_label(row.week_index, row.week_end)
        for _, row in frame[["week_index", "week_end"]]
        .drop_duplicates()
        .sort_values("week_index", kind="stable")
        .iterrows()
    ]
    pivot = pivot.reindex(week_order, axis=1)
    fig, ax = plt.subplots(figsize=(11.4, max(6.2, 0.45 * len(pivot.index) + 2)))
    image = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto")
    title = "Sector Market-Cap-Adjusted Hype by Week"
    ax.set_title(title)
    ax.set_xlabel("Week end")
    ax.set_ylabel("Industry")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, fontsize=8)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([_figure_safe_label(value) for value in pivot.index], fontsize=8)
    colorbar = fig.colorbar(image, ax=ax)
    colorbar.set_label("sector_market_cap_adjusted_hype")
    fig.subplots_adjust(bottom=0.18)
    _save_figure(fig, output_path, dpi=figure_dpi)
    plt.close(fig)
    return output_path, len(frame)


def render_market_quant_figures(
    *,
    market_inputs: MarketReportInputs,
    inputs: HypeReportInputs,
    figures_dir: Path,
    key_tickers: Iterable[str],
    figure_dpi: int,
) -> tuple[dict[str, Path], list[FigureSpec]]:
    """Render Goal 4B market, sector, and case-study figures."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures_dir.mkdir(parents=True, exist_ok=True)
    key_tickers = [str(ticker) for ticker in key_tickers]
    figure_paths: dict[str, Path] = {}
    specs: list[FigureSpec] = []
    universe_summary = build_universe_summary(market_inputs)
    sector_market = build_sector_market_structure_summary(universe_summary)
    hype_market_panel = build_hype_market_panel(
        hype_panel=inputs.panel,
        market_inputs=market_inputs,
    )
    sector_weekly = build_sector_weekly_hype_summary(inputs.panel)
    sector_pooled = build_sector_pooled_hype_summary(
        hype_panel=inputs.panel,
        market_inputs=market_inputs,
    )
    ew_returns = _equal_weight_daily_returns(market_inputs.adjusted_returns)
    ew_returns["cumulative_return"] = (
        1.0 + ew_returns["equal_weight_simple_return"]
    ).cumprod() - 1.0
    ew_returns["rolling_volatility_20d"] = ew_returns[
        "equal_weight_simple_return"
    ].rolling(20).std() * math.sqrt(252)

    title = "Sector Stock Count"
    fig, ax = plt.subplots(figsize=(9.5, 5.8))
    plot_frame = sector_market.sort_values("stock_count", kind="stable")
    ax.barh(plot_frame["industry"].map(_figure_safe_label), plot_frame["stock_count"])
    ax.set_title(title)
    ax.set_xlabel("Stock count")
    ax.set_ylabel("Industry")
    _style_axis_numbers(ax.xaxis)
    path = figures_dir / "sector_stock_count.png"
    _save_figure(fig, path, dpi=figure_dpi)
    plt.close(fig)
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="horizontal_bar",
            purpose="Show industry composition of the fixed top-50 universe.",
            input_rows_used=len(plot_frame),
            dpi=figure_dpi,
            x_label="Stock count",
            y_label="Industry",
            stock_label_count=0,
        )
    )

    title = "Sector Mean Market-Cap Weight"
    fig, ax = plt.subplots(figsize=(9.5, 5.8))
    plot_frame = sector_market.sort_values(
        "total_mean_daily_market_cap_weight", kind="stable"
    )
    ax.barh(
        plot_frame["industry"].map(_figure_safe_label),
        plot_frame["total_mean_daily_market_cap_weight"],
    )
    ax.set_title(title)
    ax.set_xlabel("Total mean daily market-cap weight")
    ax.set_ylabel("Industry")
    _style_axis_numbers(ax.xaxis)
    path = figures_dir / "sector_market_cap_weight.png"
    _save_figure(fig, path, dpi=figure_dpi)
    plt.close(fig)
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="horizontal_bar",
            purpose="Show market-cap concentration by industry.",
            input_rows_used=len(plot_frame),
            dpi=figure_dpi,
            x_label="Total mean daily market-cap weight",
            y_label="Industry",
        )
    )

    title = "Equal-Weight Cumulative Return with Hype Window"
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    ax.plot(ew_returns["date"], ew_returns["cumulative_return"])
    _shade_hype_window(ax, market_inputs)
    ax.set_title(title)
    ax.set_xlabel("Trading date")
    ax.set_ylabel("Cumulative return")
    _style_axis_numbers(ax.yaxis)
    path = figures_dir / "equal_weight_cumulative_return_hype_window.png"
    _save_figure(fig, path, dpi=figure_dpi)
    plt.close(fig)
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="line",
            purpose="Show one-year equal-weight market proxy with the Hype window shaded.",
            input_rows_used=len(ew_returns),
            dpi=figure_dpi,
            x_label="Trading date",
            y_label="Cumulative return",
        )
    )

    title = "Equal-Weight 20-Day Rolling Volatility with Hype Window"
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    ax.plot(ew_returns["date"], ew_returns["rolling_volatility_20d"])
    _shade_hype_window(ax, market_inputs)
    ax.set_title(title)
    ax.set_xlabel("Trading date")
    ax.set_ylabel("Annualized 20-day rolling volatility")
    _style_axis_numbers(ax.yaxis)
    path = figures_dir / "equal_weight_rolling_volatility_20d_hype_window.png"
    _save_figure(fig, path, dpi=figure_dpi)
    plt.close(fig)
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="line",
            purpose="Show one-year rolling volatility with the Hype window shaded.",
            input_rows_used=len(ew_returns),
            dpi=figure_dpi,
            x_label="Trading date",
            y_label="Annualized 20-day rolling volatility",
        )
    )

    title = "Raw Hype vs Weekly Return"
    fig, ax = plt.subplots(figsize=(8.8, 5.8))
    ax.scatter(
        hype_market_panel["raw_hype"], hype_market_panel["weekly_return"], alpha=0.55
    )
    label_count = _annotate_key_points(
        ax=ax,
        frame=hype_market_panel,
        key_tickers=key_tickers,
        x_column="raw_hype",
        y_column="weekly_return",
    )
    ax.set_title(title)
    ax.set_xlabel("raw_hype")
    ax.set_ylabel("Weekly simple return")
    _style_axis_numbers(ax.xaxis)
    _style_axis_numbers(ax.yaxis)
    path = figures_dir / "hype_vs_weekly_return_scatter.png"
    _save_figure(fig, path, dpi=figure_dpi)
    plt.close(fig)
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="scatter",
            purpose="Show contemporaneous descriptive relation between raw Hype and returns.",
            input_rows_used=len(hype_market_panel),
            dpi=figure_dpi,
            x_label="raw_hype",
            y_label="Weekly simple return",
            stock_label_count=label_count,
        )
    )

    title = "Raw Hype vs Weekly Realized Volatility"
    fig, ax = plt.subplots(figsize=(8.8, 5.8))
    ax.scatter(
        hype_market_panel["raw_hype"],
        hype_market_panel["weekly_realized_volatility"],
        alpha=0.55,
    )
    label_count = _annotate_key_points(
        ax=ax,
        frame=hype_market_panel,
        key_tickers=key_tickers,
        x_column="raw_hype",
        y_column="weekly_realized_volatility",
    )
    ax.set_title(title)
    ax.set_xlabel("raw_hype")
    ax.set_ylabel("Weekly realized volatility")
    _style_axis_numbers(ax.xaxis)
    _style_axis_numbers(ax.yaxis)
    path = figures_dir / "hype_vs_weekly_volatility_scatter.png"
    _save_figure(fig, path, dpi=figure_dpi)
    plt.close(fig)
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="scatter",
            purpose="Show contemporaneous descriptive relation between raw Hype and volatility.",
            input_rows_used=len(hype_market_panel),
            dpi=figure_dpi,
            x_label="raw_hype",
            y_label="Weekly realized volatility",
            stock_label_count=label_count,
        )
    )

    title = "Market-Cap-Adjusted Hype vs Weekly Return"
    fig, ax = plt.subplots(figsize=(8.8, 5.8))
    ax.scatter(
        hype_market_panel["market_cap_adjusted_hype"],
        hype_market_panel["weekly_return"],
        alpha=0.55,
    )
    label_count = _annotate_key_points(
        ax=ax,
        frame=hype_market_panel,
        key_tickers=key_tickers,
        x_column="market_cap_adjusted_hype",
        y_column="weekly_return",
    )
    ax.set_title(title)
    ax.set_xlabel("market_cap_adjusted_hype")
    ax.set_ylabel("Weekly simple return")
    _style_axis_numbers(ax.xaxis)
    _style_axis_numbers(ax.yaxis)
    path = figures_dir / "cap_adjusted_hype_vs_weekly_return_scatter.png"
    _save_figure(fig, path, dpi=figure_dpi)
    plt.close(fig)
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="scatter",
            purpose=(
                "Show contemporaneous descriptive relation between weekly "
                "market-cap-adjusted Hype and returns."
            ),
            input_rows_used=len(hype_market_panel),
            dpi=figure_dpi,
            x_label="market_cap_adjusted_hype",
            y_label="Weekly simple return",
            stock_label_count=label_count,
        )
    )

    title = "Market-Cap-Adjusted Hype vs Weekly Realized Volatility"
    fig, ax = plt.subplots(figsize=(8.8, 5.8))
    ax.scatter(
        hype_market_panel["market_cap_adjusted_hype"],
        hype_market_panel["weekly_realized_volatility"],
        alpha=0.55,
    )
    label_count = _annotate_key_points(
        ax=ax,
        frame=hype_market_panel,
        key_tickers=key_tickers,
        x_column="market_cap_adjusted_hype",
        y_column="weekly_realized_volatility",
    )
    ax.set_title(title)
    ax.set_xlabel("market_cap_adjusted_hype")
    ax.set_ylabel("Weekly realized volatility")
    _style_axis_numbers(ax.xaxis)
    _style_axis_numbers(ax.yaxis)
    path = figures_dir / "cap_adjusted_hype_vs_weekly_volatility_scatter.png"
    _save_figure(fig, path, dpi=figure_dpi)
    plt.close(fig)
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="scatter",
            purpose=(
                "Show contemporaneous descriptive relation between weekly "
                "market-cap-adjusted Hype and realized volatility."
            ),
            input_rows_used=len(hype_market_panel),
            dpi=figure_dpi,
            x_label="market_cap_adjusted_hype",
            y_label="Weekly realized volatility",
            stock_label_count=label_count,
        )
    )

    title = "Pooled Sector Raw Hype vs Pooled Market-Cap Weight"
    fig, ax = plt.subplots(figsize=(8.8, 5.8))
    x = sector_pooled["pooled_sector_market_cap_weight"]
    y = sector_pooled["pooled_sector_raw_hype"]
    ax.scatter(x, y, alpha=0.78)
    line_max = max(float(x.max()), float(y.max())) if len(sector_pooled) else 1.0
    ax.plot([0, line_max], [0, line_max], color="0.45", linewidth=1)
    ax.margins(0.14)
    label_count = _annotate_selected_sectors(
        ax=ax,
        frame=sector_pooled,
        label_codes=_selected_sector_label_codes(sector_pooled),
    )
    ax.set_title(title)
    ax.set_xlabel("pooled_sector_market_cap_weight")
    ax.set_ylabel("pooled_sector_raw_hype")
    _style_axis_numbers(ax.xaxis)
    _style_axis_numbers(ax.yaxis)
    path = (
        figures_dir / "pooled_sector_raw_hype_vs_pooled_market_cap_weight_scatter.png"
    )
    _save_figure(fig, path, dpi=figure_dpi)
    plt.close(fig)
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="scatter",
            purpose="Compare pooled sector news-attention share with pooled sector size.",
            input_rows_used=len(sector_pooled),
            dpi=figure_dpi,
            x_label="pooled_sector_market_cap_weight",
            y_label="pooled_sector_raw_hype",
            stock_label_count=label_count,
        )
    )

    title = "Pooled Sector Raw Hype vs Pooled Market-Cap Weight, Lower-Weight Zoom"
    fig, ax = plt.subplots(figsize=(8.8, 5.8))
    sector_zoom = sector_pooled.loc[
        sector_pooled["industry_code"].astype(str).ne("M23G")
    ].copy()
    if sector_zoom.empty:
        sector_zoom = sector_pooled.copy()
    x_zoom = sector_zoom["pooled_sector_market_cap_weight"]
    y_zoom = sector_zoom["pooled_sector_raw_hype"]
    ax.scatter(x_zoom, y_zoom, alpha=0.78)
    x_limit = max(float(x_zoom.max()) * 1.12, 0.01) if len(sector_zoom) else 1.0
    y_limit = max(float(y_zoom.max()) * 1.12, 0.01) if len(sector_zoom) else 1.0
    line_max = max(x_limit, y_limit)
    ax.plot([0, line_max], [0, line_max], color="0.45", linewidth=1)
    ax.set_xlim(left=0, right=x_limit)
    ax.set_ylim(bottom=0, top=y_limit)
    label_count = _annotate_selected_sectors(
        ax=ax,
        frame=sector_zoom,
        label_codes=_selected_sector_label_codes(sector_zoom, max_labels=3),
    )
    ax.set_title(title)
    ax.set_xlabel("pooled_sector_market_cap_weight")
    ax.set_ylabel("pooled_sector_raw_hype")
    _style_axis_numbers(ax.xaxis)
    _style_axis_numbers(ax.yaxis)
    path = (
        figures_dir
        / "pooled_sector_raw_hype_vs_pooled_market_cap_weight_scatter_zoom.png"
    )
    _save_figure(fig, path, dpi=figure_dpi)
    plt.close(fig)
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="scatter",
            purpose="Make lower-weight sector attention-versus-size points readable.",
            input_rows_used=len(sector_zoom),
            dpi=figure_dpi,
            x_label="pooled_sector_market_cap_weight",
            y_label="pooled_sector_raw_hype",
            stock_label_count=label_count,
        )
    )

    title = "Pooled Sector Market-Cap-Adjusted Hype Ranking"
    fig, ax = plt.subplots(figsize=(9.5, 5.8))
    plot_frame = sector_pooled.sort_values(
        "pooled_sector_market_cap_adjusted_hype",
        kind="stable",
    )
    ax.barh(
        plot_frame["industry_code"].map(_figure_safe_label),
        plot_frame["pooled_sector_market_cap_adjusted_hype"],
    )
    ax.set_title(title)
    ax.set_xlabel("pooled_sector_market_cap_adjusted_hype")
    ax.set_ylabel("Industry code")
    _style_axis_numbers(ax.xaxis)
    path = figures_dir / "pooled_sector_market_cap_adjusted_hype_ranking.png"
    _save_figure(fig, path, dpi=figure_dpi)
    plt.close(fig)
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="horizontal_bar",
            purpose="Rank industries by pooled sector attention-to-size ratio.",
            input_rows_used=len(plot_frame),
            dpi=figure_dpi,
            x_label="pooled_sector_market_cap_adjusted_hype",
            y_label="Industry code",
        )
    )

    title = "Pooled Sector Attention-Size Imbalance"
    fig, ax = plt.subplots(figsize=(9.5, 5.8))
    plot_frame = sector_pooled.sort_values(
        "pooled_sector_attention_size_imbalance",
        kind="stable",
    )
    colors = [
        "tab:blue" if value >= 0 else "tab:orange"
        for value in plot_frame["pooled_sector_attention_size_imbalance"]
    ]
    ax.barh(
        plot_frame["industry_code"].map(_figure_safe_label),
        plot_frame["pooled_sector_attention_size_imbalance"],
        color=colors,
    )
    ax.axvline(0, color="0.35", linewidth=1)
    ax.set_title(title)
    ax.set_xlabel("pooled_sector_raw_hype minus pooled_sector_market_cap_weight")
    ax.set_ylabel("Industry code")
    _style_axis_numbers(ax.xaxis)
    path = figures_dir / "pooled_sector_attention_size_imbalance.png"
    _save_figure(fig, path, dpi=figure_dpi)
    plt.close(fig)
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title=title,
            chart_type="horizontal_bar",
            purpose="Show pooled sector attention share minus pooled sector size.",
            input_rows_used=len(plot_frame),
            dpi=figure_dpi,
            x_label="pooled_sector_raw_hype minus pooled_sector_market_cap_weight",
            y_label="Industry code",
        )
    )

    path, input_rows = _render_sector_heatmap(
        plt=plt,
        sector_weekly=sector_weekly,
        output_path=figures_dir / "sector_market_cap_adjusted_hype_heatmap.png",
        figure_dpi=figure_dpi,
    )
    figure_paths[path.name] = path
    specs.append(
        FigureSpec(
            filename=path.name,
            title="Sector Market-Cap-Adjusted Hype by Week",
            chart_type="heatmap",
            purpose="Compare weekly sector-level attention-to-size ratios.",
            input_rows_used=input_rows,
            dpi=figure_dpi,
            x_label="Week end",
            y_label="Industry",
        )
    )

    for ticker in key_tickers:
        rows = hype_market_panel.loc[hype_market_panel["ticker"].astype(str).eq(ticker)]
        if rows.empty:
            continue
        rows = rows.sort_values("week_index", kind="stable")
        labels = [
            _week_label(row.week_index, row.week_end) for _, row in rows.iterrows()
        ]
        title = f"Key Stock Case Study: {ticker}"
        fig, axes = plt.subplots(5, 1, figsize=(10.4, 11.0), sharex=True)
        axes[0].bar(labels, rows["news_count_unique_urls"])
        axes[0].set_ylabel("News count")
        axes[1].plot(labels, rows["raw_hype"], marker="o", label="raw_hype")
        axes[1].plot(
            labels,
            rows["weekly_market_cap_weight"],
            marker="o",
            label="weekly_market_cap_weight",
        )
        axes[1].set_ylabel("Weekly share")
        axes[1].legend(fontsize=8)
        axes[2].plot(labels, rows["market_cap_adjusted_hype"], marker="o")
        axes[2].axhline(1.0, color="0.45", linewidth=1)
        axes[2].set_ylabel("Cap-adjusted Hype")
        axes[3].plot(labels, rows["weekly_return"], marker="o")
        axes[3].set_ylabel("Weekly return")
        axes[4].plot(labels, rows["weekly_realized_volatility"], marker="o")
        axes[4].set_ylabel("Realized volatility")
        axes[4].set_xlabel("Week end")
        for axis in axes:
            axis.tick_params(axis="x", labelsize=8)
            _style_axis_numbers(axis.yaxis)
        fig.suptitle(title)
        path = figures_dir / f"key_stock_case_study_{ticker}.png"
        _save_figure(fig, path, dpi=figure_dpi)
        plt.close(fig)
        figure_paths[path.name] = path
        specs.append(
            FigureSpec(
                filename=path.name,
                title=title,
                chart_type="small_multiple",
                purpose=(
                    "Show weekly attention, size, attention-to-size, return, "
                    "and volatility for a key stock."
                ),
                input_rows_used=len(rows),
                dpi=figure_dpi,
                x_label="Week end",
                y_label=(
                    "News count / Hype share / cap-adjusted Hype / weekly "
                    "return / realized volatility"
                ),
            )
        )

    return figure_paths, specs


def _read_png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise HypeReportError(f"Figure is not a readable PNG: {path}.")
    width = int.from_bytes(header[16:20], byteorder="big")
    height = int.from_bytes(header[20:24], byteorder="big")
    return width, height


def _figure_status(
    *,
    spec: FigureSpec,
    path: Path,
    figures_dir: Path,
    top_n: int,
) -> tuple[str, list[str], int | None, int | None, int]:
    errors: list[str] = []
    width_px: int | None = None
    height_px: int | None = None
    file_size = 0
    figures_resolved = figures_dir.resolve(strict=False)
    path_resolved = path.resolve(strict=False)
    if not (
        path_resolved == figures_resolved or figures_resolved in path_resolved.parents
    ):
        errors.append("figure is outside the figures directory")
    if not path.is_file():
        errors.append("file is missing")
    else:
        file_size = path.stat().st_size
        if file_size <= 0:
            errors.append("file is empty")
        try:
            width_px, height_px = _read_png_size(path)
        except HypeReportError as exc:
            errors.append(str(exc))
        if width_px is not None and width_px < MIN_FIGURE_WIDTH_PX:
            errors.append(f"width_px is below {MIN_FIGURE_WIDTH_PX}")
        if height_px is not None and height_px < MIN_FIGURE_HEIGHT_PX:
            errors.append(f"height_px is below {MIN_FIGURE_HEIGHT_PX}")
    if not spec.title.strip():
        errors.append("title is empty")
    if spec.require_axis_labels and (
        not spec.x_label.strip() or not spec.y_label.strip()
    ):
        errors.append("axis label is empty")
    if (
        spec.chart_type in {"horizontal_bar", "heatmap"}
        and spec.stock_label_count > top_n
    ):
        errors.append("stock label count exceeds top_n")
    return (
        "passed" if not errors else "failed: " + "; ".join(errors),
        errors,
        width_px,
        height_px,
        file_size,
    )


def validate_figure_outputs(
    *,
    figures_dir: Path,
    specs: list[FigureSpec],
    top_n: int,
    required_filenames: Iterable[str] = REQUIRED_FIGURE_FILENAMES,
) -> pd.DataFrame:
    """Build and validate objective visual-QA manifest rows."""

    records: list[dict[str, Any]] = []
    all_errors: list[str] = []
    required = set(required_filenames)
    observed = {spec.filename for spec in specs}
    missing_specs = sorted(required - observed)
    if missing_specs:
        all_errors.append("missing figure specs: " + ", ".join(missing_specs))

    for spec in specs:
        path = figures_dir / spec.filename
        status, errors, width_px, height_px, file_size = _figure_status(
            spec=spec,
            path=path,
            figures_dir=figures_dir,
            top_n=top_n,
        )
        if errors:
            all_errors.append(f"{spec.filename}: {status}")
        records.append(
            {
                "filename": spec.filename,
                "title": spec.title,
                "chart_type": spec.chart_type,
                "purpose": spec.purpose,
                "width_px": width_px,
                "height_px": height_px,
                "dpi": spec.dpi,
                "file_size_bytes": file_size,
                "input_rows_used": spec.input_rows_used,
                "visual_quality_status": status,
            }
        )
    manifest = pd.DataFrame(records)
    if all_errors:
        raise HypeReportError("Objective figure QA failed: " + " | ".join(all_errors))
    return manifest


def write_figure_manifest(
    *,
    manifest: pd.DataFrame,
    specs: list[FigureSpec],
    figures_dir: Path,
    required_filenames: Iterable[str] = REQUIRED_FIGURE_FILENAMES,
) -> tuple[Path, Path, Path]:
    """Write the figure manifest CSV/JSON and a Markdown figure index."""

    manifest_csv = figures_dir / "figure_index.csv"
    manifest_json = figures_dir / "figure_visual_qa_manifest.json"
    index_md = figures_dir / "figure_index.md"
    manifest.to_csv(manifest_csv, index=False)
    records = manifest.to_dict(orient="records")
    manifest_json.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    spec_by_name = {spec.filename: spec for spec in specs}
    lines = [
        "# Pilot 8-Week Hype Index Figure Index",
        "",
        "Objective visual QA passed for the generated PNG figures. Human review "
        "should still inspect readability, label density, and report fit.",
        "",
    ]
    for filename in required_filenames:
        spec = spec_by_name[filename]
        lines.extend(
            [
                f"## {spec.title}",
                "",
                f"Purpose: {spec.purpose}",
                "",
                f"![{spec.title}]({filename})",
                "",
            ]
        )
    index_md.write_text("\n".join(lines), encoding="utf-8")
    return manifest_csv, manifest_json, index_md


def write_artifact_manifest(
    *,
    results_dir: Path,
    figures_dir: Path,
    table_paths: dict[str, tuple[Path, Path]],
    methodology_notes: Path,
    figure_paths: dict[str, Path],
    figure_manifest_csv: Path,
    figure_manifest_json: Path,
    figure_index_md: Path,
    inputs: HypeReportInputs,
    market_inputs: MarketReportInputs | None,
    top_n: int,
    figure_dpi: int,
) -> Path:
    """Write a deterministic manifest for report artifact provenance."""

    manifest_path = results_dir / "artifact_manifest.json"
    table_names = sorted(table_paths)
    figure_names = sorted(figure_paths)
    goal4b_tables = [name for name in GOAL4B_TABLE_NAMES if name in table_paths]
    goal4b_figures = [
        name for name in GOAL4B_MARKET_FIGURE_FILENAMES if name in figure_paths
    ]
    revised_figures = [
        name
        for name in [
            "raw_hype_heatmap_top_stocks.png",
            "market_cap_adjusted_hype_heatmap_top_stocks.png",
            "pooled_raw_hype_vs_pooled_market_cap_weight_scatter.png",
            "pooled_raw_hype_vs_pooled_market_cap_weight_scatter_zoom.png",
            "pooled_attention_size_imbalance_top_stocks.png",
        ]
        if name in figure_paths
    ]
    payload = {
        "artifact_set": "taiwan_hype_index_pilot_8w_manual_v5",
        "reporting_layer": "Goal 4A + Goal 4B + Goal 4C"
        if market_inputs is not None
        else "Goal 4A",
        "cross_sectional_hype_reporting": "pooled_only",
        "mean_hype_cross_sectional_artifacts_deprecated": True,
        "reporting_layers": [
            {
                "goal": "Goal 4A",
                "description": "Hype report artifacts from existing Goal 3C outputs.",
                "tables": [name for name in GOAL4A_TABLE_NAMES if name in table_paths],
                "figures": [
                    name for name in REQUIRED_FIGURE_FILENAMES if name in figure_paths
                ],
            },
            {
                "goal": "Goal 4B",
                "description": (
                    "Notebook-ready market quant, sector aggregation, and "
                    "descriptive return / volatility artifacts."
                ),
                "tables": goal4b_tables,
                "figures": goal4b_figures,
                "revised_figures": revised_figures,
            },
            {
                "goal": "Goal 4C",
                "description": (
                    "Pooled-only stock and sector cross-sectional Hype reporting; "
                    "weekly Hype retained for dynamics and descriptive return / "
                    "volatility alignment."
                ),
                "tables": [
                    name
                    for name in [
                        "stock_pooled_hype_summary",
                        "top_pooled_raw_hype_stocks",
                        "top_pooled_market_cap_adjusted_hype_stocks",
                        "top_pooled_attention_size_imbalance_stocks",
                        "sector_pooled_hype_summary",
                        "top_pooled_sector_market_cap_adjusted_hype",
                        "tej_industry_label_mapping",
                    ]
                    if name in table_paths
                ],
                "figures": [
                    name
                    for name in [
                        "top_pooled_raw_hype_stocks.png",
                        "top_pooled_market_cap_adjusted_hype_stocks.png",
                        "pooled_raw_hype_vs_pooled_market_cap_weight_scatter.png",
                        "pooled_raw_hype_vs_pooled_market_cap_weight_scatter_zoom.png",
                        "pooled_attention_size_imbalance_top_stocks.png",
                        "pooled_sector_raw_hype_vs_pooled_market_cap_weight_scatter.png",
                        "pooled_sector_raw_hype_vs_pooled_market_cap_weight_scatter_zoom.png",
                        "pooled_sector_market_cap_adjusted_hype_ranking.png",
                        "pooled_sector_attention_size_imbalance.png",
                    ]
                    if name in figure_paths
                ],
            },
        ],
        "results_dir": str(results_dir),
        "figures_dir": str(figures_dir),
        "top_n": top_n,
        "figure_dpi": figure_dpi,
        "goal_3_recomputation_performed": False,
        "live_gdelt_downloads_run": False,
        "notebook_created": False,
        "hype_summary_validation_status": inputs.summary.get("validation_status"),
        "hype_panel_rows": int(len(inputs.panel)),
        "weekly_summary_rows": int(len(inputs.weekly_summary)),
        "stock_summary_rows": int(len(inputs.stock_summary)),
        "chunk_summary_count": len(inputs.chunk_summaries),
        "market_quant_included": market_inputs is not None,
        "market_background_period": {
            "start": None
            if market_inputs is None
            else market_inputs.market_background_start,
            "end": None
            if market_inputs is None
            else market_inputs.market_background_end,
        },
        "hype_trading_comparison_period": {
            "start": None
            if market_inputs is None
            else market_inputs.hype_trading_start,
            "end": None if market_inputs is None else market_inputs.hype_trading_end,
        },
        "tables": {
            name: {
                "csv": str(csv_path),
                "markdown": str(md_path),
            }
            for name, (csv_path, md_path) in sorted(table_paths.items())
        },
        "table_names": table_names,
        "methodology_notes": str(methodology_notes),
        "figures": {name: str(path) for name, path in sorted(figure_paths.items())},
        "figure_names": figure_names,
        "figure_index_csv": str(figure_manifest_csv),
        "figure_visual_qa_manifest_json": str(figure_manifest_json),
        "figure_index_markdown": str(figure_index_md),
    }
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def build_hype_report_artifacts(
    *,
    hype_panel_file: str | Path = DEFAULT_HYPE_PANEL_FILE,
    weekly_summary_file: str | Path = DEFAULT_WEEKLY_SUMMARY_FILE,
    stock_summary_file: str | Path = DEFAULT_STOCK_SUMMARY_FILE,
    hype_summary_json: str | Path = DEFAULT_HYPE_SUMMARY_JSON,
    chunk_summary_json: Iterable[str | Path] = (),
    include_market_quant: bool = False,
    daily_market_panel_file: str | Path = DEFAULT_DAILY_MARKET_PANEL_FILE,
    weekly_market_weights_file: str | Path = DEFAULT_WEEKLY_MARKET_WEIGHTS_FILE,
    universe_file: str | Path = DEFAULT_UNIVERSE_FILE,
    company_metadata_file: str | Path = DEFAULT_COMPANY_METADATA_FILE,
    tej_validation_json: str | Path = DEFAULT_TEJ_VALIDATION_JSON,
    raw_tej_return_file: str | Path = DEFAULT_RAW_TEJ_RETURN_FILE,
    market_background_start: str = DEFAULT_MARKET_BACKGROUND_START,
    market_background_end: str = DEFAULT_MARKET_BACKGROUND_END,
    hype_trading_start: str = DEFAULT_HYPE_TRADING_START,
    hype_trading_end: str = DEFAULT_HYPE_TRADING_END,
    key_tickers: Iterable[str] = DEFAULT_KEY_TICKERS,
    results_dir: str | Path = DEFAULT_RESULTS_DIR,
    figures_dir: str | Path = DEFAULT_FIGURES_DIR,
    top_n: int = DEFAULT_TOP_N,
    figure_dpi: int = DEFAULT_FIGURE_DPI,
    repo_root: Path = Path.cwd(),
) -> HypeReportArtifactPaths:
    """Build all Goal 4A report-ready tables, figures, and visual QA files."""

    if top_n <= 0:
        raise HypeReportError("top_n must be positive.")
    if figure_dpi < DEFAULT_FIGURE_DPI:
        raise HypeReportError(f"figure_dpi must be at least {DEFAULT_FIGURE_DPI}.")

    resolved_results_dir = validate_results_dir(results_dir, repo_root=repo_root)
    resolved_figures_dir = validate_figures_dir(figures_dir, repo_root=repo_root)
    inputs = load_hype_report_inputs(
        hype_panel_file=hype_panel_file,
        weekly_summary_file=weekly_summary_file,
        stock_summary_file=stock_summary_file,
        hype_summary_json=hype_summary_json,
        chunk_summary_json=chunk_summary_json,
        repo_root=repo_root,
    )
    market_inputs = (
        load_market_report_inputs(
            daily_market_panel_file=daily_market_panel_file,
            weekly_market_weights_file=weekly_market_weights_file,
            universe_file=universe_file,
            company_metadata_file=company_metadata_file,
            tej_validation_json=tej_validation_json,
            raw_tej_return_file=raw_tej_return_file,
            market_background_start=market_background_start,
            market_background_end=market_background_end,
            hype_trading_start=hype_trading_start,
            hype_trading_end=hype_trading_end,
            repo_root=repo_root,
        )
        if include_market_quant
        else None
    )
    key_tickers = [str(ticker) for ticker in key_tickers]
    cleanup_deprecated_report_artifacts(
        results_dir=resolved_results_dir,
        figures_dir=resolved_figures_dir,
    )
    pooled_stock_summary = build_stock_pooled_hype_summary(
        hype_panel=inputs.panel,
        market_inputs=market_inputs,
    )

    table_paths, methodology_notes = build_report_tables(
        inputs=inputs,
        results_dir=resolved_results_dir,
        top_n=top_n,
        market_inputs=market_inputs,
        key_tickers=key_tickers,
    )
    figure_paths, specs = render_report_figures(
        panel=inputs.panel,
        weekly_summary=inputs.weekly_summary,
        stock_summary=inputs.stock_summary,
        pooled_stock_summary=pooled_stock_summary,
        figures_dir=resolved_figures_dir,
        top_n=top_n,
        figure_dpi=figure_dpi,
    )
    required_figures = list(REQUIRED_FIGURE_FILENAMES)
    if market_inputs is not None:
        market_figure_paths, market_specs = render_market_quant_figures(
            market_inputs=market_inputs,
            inputs=inputs,
            figures_dir=resolved_figures_dir,
            key_tickers=key_tickers,
            figure_dpi=figure_dpi,
        )
        figure_paths.update(market_figure_paths)
        specs.extend(market_specs)
        required_figures.extend(GOAL4B_MARKET_FIGURE_FILENAMES)
    manifest = validate_figure_outputs(
        figures_dir=resolved_figures_dir,
        specs=specs,
        top_n=top_n,
        required_filenames=required_figures,
    )
    manifest_csv, manifest_json, index_md = write_figure_manifest(
        manifest=manifest,
        specs=specs,
        figures_dir=resolved_figures_dir,
        required_filenames=required_figures,
    )
    artifact_manifest = write_artifact_manifest(
        results_dir=resolved_results_dir,
        figures_dir=resolved_figures_dir,
        table_paths=table_paths,
        methodology_notes=methodology_notes,
        figure_paths=figure_paths,
        figure_manifest_csv=manifest_csv,
        figure_manifest_json=manifest_json,
        figure_index_md=index_md,
        inputs=inputs,
        market_inputs=market_inputs,
        top_n=top_n,
        figure_dpi=figure_dpi,
    )

    written_paths: list[Path] = [
        methodology_notes,
        artifact_manifest,
        manifest_csv,
        manifest_json,
        index_md,
        *figure_paths.values(),
    ]
    for csv_path, md_path in table_paths.values():
        written_paths.extend([csv_path, md_path])
    if any(path.suffix == ".ipynb" for path in written_paths):
        raise HypeReportError("Report artifact builder created a notebook.")

    return HypeReportArtifactPaths(
        results_dir=resolved_results_dir,
        figures_dir=resolved_figures_dir,
        table_paths=table_paths,
        methodology_notes=methodology_notes,
        figure_paths=figure_paths,
        figure_manifest_csv=manifest_csv,
        figure_manifest_json=manifest_json,
        figure_index_md=index_md,
        artifact_manifest=artifact_manifest,
    )
