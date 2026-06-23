from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import pytest

from quant_finance_project.reporting.hype_report import (
    DEFAULT_KEY_TICKERS,
    FigureSpec,
    HypeReportError,
    build_hype_report_artifacts,
    validate_figure_outputs,
)


REQUIRED_TABLES = [
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
REQUIRED_FIGURES = [
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
MARKET_TABLES = [
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
MARKET_FIGURES = [
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


def _panel_rows() -> list[dict[str, object]]:
    return [
        {
            "stock_id": "AAA",
            "ticker": "AAA",
            "official_chinese_name": "Alpha Taiwan",
            "official_english_name": "Alpha Co",
            "industry": "Tech",
            "week_index": 1,
            "week_start": "2025-04-05",
            "week_end": "2025-04-11",
            "news_count_unique_urls": 2,
            "matched_rows": 2,
            "weekly_total_news_count_unique_urls": 3,
            "weekly_market_cap_weight": 0.5,
            "raw_hype": 2 / 3,
            "market_cap_adjusted_hype": (2 / 3) / 0.5,
        },
        {
            "stock_id": "BBB",
            "ticker": "BBB",
            "official_chinese_name": "Beta Taiwan",
            "official_english_name": "Beta Co",
            "industry": "Finance",
            "week_index": 1,
            "week_start": "2025-04-05",
            "week_end": "2025-04-11",
            "news_count_unique_urls": 1,
            "matched_rows": 1,
            "weekly_total_news_count_unique_urls": 3,
            "weekly_market_cap_weight": 0.25,
            "raw_hype": 1 / 3,
            "market_cap_adjusted_hype": (1 / 3) / 0.25,
        },
        {
            "stock_id": "CCC",
            "ticker": "CCC",
            "official_chinese_name": "Gamma Taiwan",
            "official_english_name": "Gamma Co",
            "industry": "Materials",
            "week_index": 1,
            "week_start": "2025-04-05",
            "week_end": "2025-04-11",
            "news_count_unique_urls": 0,
            "matched_rows": 0,
            "weekly_total_news_count_unique_urls": 3,
            "weekly_market_cap_weight": 0.25,
            "raw_hype": 0,
            "market_cap_adjusted_hype": 0,
        },
        {
            "stock_id": "AAA",
            "ticker": "AAA",
            "official_chinese_name": "Alpha Taiwan",
            "official_english_name": "Alpha Co",
            "industry": "Tech",
            "week_index": 2,
            "week_start": "2025-04-12",
            "week_end": "2025-04-18",
            "news_count_unique_urls": 0,
            "matched_rows": 0,
            "weekly_total_news_count_unique_urls": 4,
            "weekly_market_cap_weight": 0.25,
            "raw_hype": 0,
            "market_cap_adjusted_hype": 0,
        },
        {
            "stock_id": "BBB",
            "ticker": "BBB",
            "official_chinese_name": "Beta Taiwan",
            "official_english_name": "Beta Co",
            "industry": "Finance",
            "week_index": 2,
            "week_start": "2025-04-12",
            "week_end": "2025-04-18",
            "news_count_unique_urls": 2,
            "matched_rows": 2,
            "weekly_total_news_count_unique_urls": 4,
            "weekly_market_cap_weight": 0.25,
            "raw_hype": 0.5,
            "market_cap_adjusted_hype": 2.0,
        },
        {
            "stock_id": "CCC",
            "ticker": "CCC",
            "official_chinese_name": "Gamma Taiwan",
            "official_english_name": "Gamma Co",
            "industry": "Materials",
            "week_index": 2,
            "week_start": "2025-04-12",
            "week_end": "2025-04-18",
            "news_count_unique_urls": 2,
            "matched_rows": 2,
            "weekly_total_news_count_unique_urls": 4,
            "weekly_market_cap_weight": 0.5,
            "raw_hype": 0.5,
            "market_cap_adjusted_hype": 1.0,
        },
    ]


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _write_hype_inputs_from_panel(
    *,
    tmp_path: Path,
    panel: pd.DataFrame,
    summary: dict[str, object],
    chunk_summaries: list[dict[str, object]],
) -> dict[str, Path]:
    inputs = tmp_path / "inputs"
    inputs.mkdir(exist_ok=True)
    panel_path = inputs / "hype_panel.csv"
    panel.to_csv(panel_path, index=False)

    weekly_summary = (
        panel.groupby(["week_index", "week_start", "week_end"], as_index=False)
        .agg(
            weekly_total_news_count_unique_urls=(
                "weekly_total_news_count_unique_urls",
                "first",
            ),
            nonzero_stock_count=(
                "news_count_unique_urls",
                lambda values: int((values > 0).sum()),
            ),
            zero_stock_count=(
                "news_count_unique_urls",
                lambda values: int((values == 0).sum()),
            ),
            max_raw_hype=("raw_hype", "max"),
            max_market_cap_adjusted_hype=("market_cap_adjusted_hype", "max"),
            raw_hype_sum=("raw_hype", "sum"),
            market_cap_weight_sum=("weekly_market_cap_weight", "sum"),
        )
        .sort_values("week_index", kind="stable")
    )
    for column, metric in [
        ("ticker_with_max_raw_hype", "raw_hype"),
        ("ticker_with_max_market_cap_adjusted_hype", "market_cap_adjusted_hype"),
    ]:
        tickers = []
        for week_index in weekly_summary["week_index"]:
            week_rows = panel.loc[panel["week_index"].eq(week_index)]
            tickers.append(
                week_rows.sort_values([metric, "ticker"], ascending=[False, True]).iloc[
                    0
                ]["ticker"]
            )
        weekly_summary[column] = tickers
    weekly_summary["is_missing_hype_week"] = False
    weekly_path = inputs / "weekly_summary.csv"
    weekly_summary.to_csv(weekly_path, index=False)

    stock_summary = (
        panel.groupby(
            [
                "stock_id",
                "ticker",
                "official_chinese_name",
                "official_english_name",
                "industry",
            ],
            as_index=False,
        )
        .agg(
            total_news_count_unique_urls=("news_count_unique_urls", "sum"),
            nonzero_week_count=(
                "news_count_unique_urls",
                lambda values: int((values > 0).sum()),
            ),
            zero_week_count=(
                "news_count_unique_urls",
                lambda values: int((values == 0).sum()),
            ),
            mean_raw_hype=("raw_hype", "mean"),
            max_raw_hype=("raw_hype", "max"),
            mean_market_cap_adjusted_hype=("market_cap_adjusted_hype", "mean"),
            max_market_cap_adjusted_hype=("market_cap_adjusted_hype", "max"),
            mean_weekly_market_cap_weight=("weekly_market_cap_weight", "mean"),
        )
        .sort_values("ticker")
    )
    stock_path = inputs / "stock_summary.csv"
    stock_summary.to_csv(stock_path, index=False)

    summary_path = inputs / "summary.json"
    _write_json(summary_path, summary)
    chunk_paths = []
    for index, chunk in enumerate(chunk_summaries, start=1):
        path = inputs / f"chunk_{index}_summary.json"
        _write_json(path, chunk)
        chunk_paths.append(path)
    return {
        "panel": panel_path,
        "weekly": weekly_path,
        "stock": stock_path,
        "summary": summary_path,
        **{f"chunk_{index}": path for index, path in enumerate(chunk_paths, start=1)},
    }


def _write_inputs(tmp_path: Path) -> dict[str, Path]:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    panel = pd.DataFrame(_panel_rows())
    panel_path = inputs / "hype_panel.csv"
    panel.to_csv(panel_path, index=False)

    weekly_summary = pd.DataFrame(
        [
            {
                "week_index": 1,
                "week_start": "2025-04-05",
                "week_end": "2025-04-11",
                "weekly_total_news_count_unique_urls": 3,
                "nonzero_stock_count": 2,
                "zero_stock_count": 1,
                "is_missing_hype_week": False,
                "max_raw_hype": 2 / 3,
                "ticker_with_max_raw_hype": "AAA",
                "max_market_cap_adjusted_hype": (2 / 3) / 0.5,
                "ticker_with_max_market_cap_adjusted_hype": "AAA",
                "raw_hype_sum": 1.0,
                "market_cap_weight_sum": 1.0,
            },
            {
                "week_index": 2,
                "week_start": "2025-04-12",
                "week_end": "2025-04-18",
                "weekly_total_news_count_unique_urls": 4,
                "nonzero_stock_count": 2,
                "zero_stock_count": 1,
                "is_missing_hype_week": False,
                "max_raw_hype": 0.5,
                "ticker_with_max_raw_hype": "BBB",
                "max_market_cap_adjusted_hype": 2.0,
                "ticker_with_max_market_cap_adjusted_hype": "BBB",
                "raw_hype_sum": 1.0,
                "market_cap_weight_sum": 1.0,
            },
        ]
    )
    weekly_path = inputs / "weekly_summary.csv"
    weekly_summary.to_csv(weekly_path, index=False)

    stock_summary = (
        panel.groupby(
            [
                "stock_id",
                "ticker",
                "official_chinese_name",
                "official_english_name",
                "industry",
            ],
            as_index=False,
        )
        .agg(
            total_news_count_unique_urls=("news_count_unique_urls", "sum"),
            nonzero_week_count=(
                "news_count_unique_urls",
                lambda values: (values > 0).sum(),
            ),
            zero_week_count=(
                "news_count_unique_urls",
                lambda values: (values == 0).sum(),
            ),
            mean_raw_hype=("raw_hype", "mean"),
            max_raw_hype=("raw_hype", "max"),
            mean_market_cap_adjusted_hype=("market_cap_adjusted_hype", "mean"),
            max_market_cap_adjusted_hype=("market_cap_adjusted_hype", "max"),
            mean_weekly_market_cap_weight=("weekly_market_cap_weight", "mean"),
        )
        .sort_values("ticker")
    )
    stock_path = inputs / "stock_summary.csv"
    stock_summary.to_csv(stock_path, index=False)

    summary_path = inputs / "summary.json"
    _write_json(
        summary_path,
        {
            "pilot_start_date": "2025-04-05",
            "pilot_end_date": "2025-04-18",
            "week_count": 2,
            "universe_size": 3,
            "expected_rows": 6,
            "actual_rows": 6,
            "count_definition": "sum_of_stock_day_unique_document_counts",
            "main_news_count_column": "news_count_unique_urls",
            "matched_rows_role": "diagnostic_only",
            "cross_day_url_deduplicated": False,
            "hype_index_computed": True,
            "market_cap_adjusted_hype_computed": True,
            "validation_status": "passed",
        },
    )

    chunk_1 = inputs / "chunk_1_summary.json"
    chunk_2 = inputs / "chunk_2_summary.json"
    _write_json(
        chunk_1,
        {
            "candidate_file_count_uncapped": 10,
            "files_processed": 9,
            "files_missing": 1,
            "files_failed": 0,
            "matched_rows": 7,
            "unique_urls": 6,
        },
    )
    _write_json(
        chunk_2,
        {
            "candidate_file_count_uncapped": 20,
            "files_processed": 19,
            "files_missing": 1,
            "files_failed": 0,
            "matched_rows": 8,
            "unique_urls": 7,
        },
    )

    return {
        "panel": panel_path,
        "weekly": weekly_path,
        "stock": stock_path,
        "summary": summary_path,
        "chunk_1": chunk_1,
        "chunk_2": chunk_2,
    }


def _build_report(tmp_path: Path):
    pytest.importorskip("matplotlib")
    inputs = _write_inputs(tmp_path)
    return build_hype_report_artifacts(
        hype_panel_file=inputs["panel"],
        weekly_summary_file=inputs["weekly"],
        stock_summary_file=inputs["stock"],
        hype_summary_json=inputs["summary"],
        chunk_summary_json=[inputs["chunk_1"], inputs["chunk_2"]],
        results_dir=tmp_path / "report/results/pilot_8w",
        figures_dir=tmp_path / "report/figures/pilot_8w",
        top_n=2,
        figure_dpi=160,
        repo_root=tmp_path,
    )


def _goal4b_panel_rows() -> list[dict[str, object]]:
    stocks = [
        ("2330", "台積電", "Taiwan Semiconductor Manufacturing", "Semiconductor"),
        ("2454", "聯發科", "MediaTek", "Semiconductor"),
        ("2317", "鴻海", "Hon Hai Precision", "Electronics"),
        ("2357", "華碩", "ASUS", "Computer"),
    ]
    weeks = [
        (1, "2025-04-05", "2025-04-11", [5, 2, 2, 1], [0.50, 0.20, 0.20, 0.10]),
        (2, "2025-04-12", "2025-04-18", [3, 2, 2, 1], [0.45, 0.25, 0.20, 0.10]),
    ]
    rows: list[dict[str, object]] = []
    for week_index, week_start, week_end, counts, weights in weeks:
        total = sum(counts)
        for (ticker, chinese, english, industry), count, weight in zip(
            stocks,
            counts,
            weights,
            strict=True,
        ):
            raw_hype = count / total
            rows.append(
                {
                    "stock_id": ticker,
                    "ticker": ticker,
                    "official_chinese_name": chinese,
                    "official_english_name": english,
                    "industry": industry,
                    "week_index": week_index,
                    "week_start": week_start,
                    "week_end": week_end,
                    "news_count_unique_urls": count,
                    "matched_rows": count,
                    "weekly_total_news_count_unique_urls": total,
                    "weekly_market_cap_weight": weight,
                    "raw_hype": raw_hype,
                    "market_cap_adjusted_hype": raw_hype / weight,
                }
            )
    return rows


def _write_goal4b_inputs(tmp_path: Path) -> dict[str, Path]:
    panel = pd.DataFrame(_goal4b_panel_rows())
    hype_paths = _write_hype_inputs_from_panel(
        tmp_path=tmp_path,
        panel=panel,
        summary={
            "pilot_start_date": "2025-04-05",
            "pilot_end_date": "2025-04-18",
            "week_count": 2,
            "universe_size": 4,
            "expected_rows": 8,
            "actual_rows": 8,
            "count_definition": "sum_of_stock_day_unique_document_counts",
            "main_news_count_column": "news_count_unique_urls",
            "matched_rows_role": "diagnostic_only",
            "cross_day_url_deduplicated": False,
            "hype_index_computed": True,
            "market_cap_adjusted_hype_computed": True,
            "validation_status": "passed",
        },
        chunk_summaries=[
            {
                "start_date": "2025-04-05",
                "end_date": "2025-04-18",
                "candidate_file_count_uncapped": 20,
                "files_processed": 20,
                "files_missing": 0,
                "files_failed": 0,
                "matched_rows": 18,
                "unique_urls": 15,
                "completed": True,
            }
        ],
    )

    market_dir = tmp_path / "data"
    market_dir.mkdir()
    tickers = list(DEFAULT_KEY_TICKERS)
    universe = panel[
        [
            "stock_id",
            "ticker",
            "official_chinese_name",
            "official_english_name",
            "industry",
        ]
    ].drop_duplicates()
    universe["constituent_source"] = "synthetic"
    universe["constituent_as_of_date"] = "2025-03-31"
    universe["notes"] = "synthetic fixture"
    universe_path = market_dir / "top50_universe.csv"
    universe.to_csv(universe_path, index=False)

    metadata = universe.copy()
    metadata["exchange"] = "TSE"
    metadata["status"] = "Current"
    metadata_path = market_dir / "company_metadata.csv"
    metadata.to_csv(metadata_path, index=False)

    dates = pd.bdate_range("2025-04-01", "2025-04-30")
    daily_rows = []
    raw_rows = []
    base_caps = {
        "2330": 500.0,
        "2454": 220.0,
        "2317": 160.0,
        "2357": 90.0,
    }
    for date_index, date in enumerate(dates):
        caps = {
            ticker: base_caps[ticker] * (1 + 0.002 * date_index) for ticker in tickers
        }
        cap_total = sum(caps.values())
        for ticker_index, ticker in enumerate(tickers):
            simple_return = 0.001 * (ticker_index + 1) + 0.0001 * date_index
            log_return = math.log1p(simple_return)
            daily_rows.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "stock_id": ticker,
                    "ticker": ticker,
                    "close": 100 + date_index + ticker_index,
                    "shares_outstanding": 1000,
                    "market_cap": caps[ticker],
                    "volume": 1000,
                    "traded_value": 100000,
                    "market_cap_weight_from_tej": caps[ticker] / cap_total,
                    "daily_market_cap_weight": caps[ticker] / cap_total,
                }
            )
            raw_rows.append(
                {
                    "證券代碼": f"{ticker} synthetic",
                    "年月日": date.strftime("%Y%m%d"),
                    "證期會代碼": ticker,
                    "收盤價(元)": 100 + date_index + ticker_index,
                    "報酬率％": simple_return * 100,
                    "報酬率-Ln": log_return * 100,
                    "成交量(千股)": 1,
                    "成交值(千元)": 1,
                    "週轉率％": 0.1,
                }
            )
    daily_path = market_dir / "daily_market_panel.csv"
    pd.DataFrame(daily_rows).to_csv(daily_path, index=False)
    raw_path = market_dir / "raw_tej_returns.csv"
    pd.DataFrame(raw_rows).to_csv(raw_path, sep=";", encoding="big5", index=False)

    weekly_rows = []
    for week_end in ["2025-04-11", "2025-04-18"]:
        week_date = pd.Timestamp(week_end)
        day_caps = [
            row for row in daily_rows if row["date"] == week_date.strftime("%Y-%m-%d")
        ]
        total = sum(row["market_cap"] for row in day_caps)
        for row in day_caps:
            weekly_rows.append(
                {
                    "week_end": week_end,
                    "weight_date": week_end,
                    "stock_id": row["stock_id"],
                    "ticker": row["ticker"],
                    "market_cap": row["market_cap"],
                    "weekly_market_cap_weight": row["market_cap"] / total,
                }
            )
    weekly_weights_path = market_dir / "weekly_market_cap_weights.csv"
    pd.DataFrame(weekly_rows).to_csv(weekly_weights_path, index=False)

    validation_path = market_dir / "validation_summary.json"
    _write_json(
        validation_path,
        {
            "counts": {
                "daily_ticker_count": 4,
                "trading_date_count": len(dates),
                "daily_market_panel_rows": len(daily_rows),
                "weekly_count": 2,
                "weekly_market_cap_weight_rows": len(weekly_rows),
                "daily_min_date": "2025-04-01",
                "daily_max_date": "2025-04-30",
            },
            "checks": {"synthetic_check": True},
            "failed_checks": [],
        },
    )
    return {
        **hype_paths,
        "daily_market": daily_path,
        "weekly_weights": weekly_weights_path,
        "universe": universe_path,
        "metadata": metadata_path,
        "validation": validation_path,
        "raw_returns": raw_path,
    }


def test_build_report_artifacts_writes_required_tables_and_figures(
    tmp_path: Path,
) -> None:
    paths = _build_report(tmp_path)

    for name in REQUIRED_TABLES:
        csv_path, md_path = paths.table_paths[name]
        assert csv_path.is_file()
        assert md_path.is_file()
        assert csv_path.stat().st_size > 0
        assert md_path.stat().st_size > 0
    assert paths.methodology_notes.is_file()
    assert "not an exact full-year replication" in paths.methodology_notes.read_text()
    pooled_stock = pd.read_csv(paths.results_dir / "stock_pooled_hype_summary.csv")
    assert {
        "pooled_raw_hype",
        "pooled_market_cap_weight",
        "pooled_market_cap_adjusted_hype",
        "pooled_attention_size_imbalance",
    }.issubset(pooled_stock.columns)
    assert "mean_raw_hype" not in pooled_stock.columns
    assert "mean_market_cap_adjusted_hype" not in pooled_stock.columns

    for filename in REQUIRED_FIGURES:
        figure_path = paths.figures_dir / filename
        assert figure_path.is_file()
        assert figure_path.stat().st_size > 0

    manifest = pd.read_csv(paths.figure_manifest_csv)
    assert set(manifest["filename"]) == set(REQUIRED_FIGURES)
    assert manifest["visual_quality_status"].eq("passed").all()
    assert (manifest["width_px"] >= 1000).all()
    assert (manifest["height_px"] >= 600).all()
    assert paths.figure_manifest_csv.name == "figure_index.csv"
    assert paths.figure_manifest_json.name == "figure_visual_qa_manifest.json"
    assert paths.figure_manifest_json.is_file()
    assert paths.figure_index_md.is_file()
    assert paths.artifact_manifest.is_file()

    pipeline_summary = pd.read_csv(
        paths.results_dir / "pipeline_validation_summary.csv"
    )
    candidate_files = pipeline_summary.loc[
        pipeline_summary["metric"].eq("candidate files"),
        "value",
    ].iloc[0]
    assert int(candidate_files) == 30
    acquisition_summary = pd.read_csv(
        paths.results_dir / "news_acquisition_summary.csv"
    )
    combined_matched = acquisition_summary.loc[
        acquisition_summary["chunk"].eq("combined"),
        "matched_rows",
    ].iloc[0]
    assert int(combined_matched) == 15

    assert not list(paths.results_dir.rglob("*.ipynb"))
    assert not list(paths.figures_dir.rglob("*.ipynb"))
    assert not (tmp_path / "data/raw").exists()
    assert not (tmp_path / "data/processed").exists()


def test_build_report_artifacts_removes_deprecated_mean_outputs(
    tmp_path: Path,
) -> None:
    pytest.importorskip("matplotlib")
    inputs = _write_inputs(tmp_path)
    results_dir = tmp_path / "report/results/pilot_8w"
    figures_dir = tmp_path / "report/figures/pilot_8w"
    results_dir.mkdir(parents=True)
    figures_dir.mkdir(parents=True)
    stale_table = results_dir / "top_raw_hype_stocks.csv"
    stale_figure = figures_dir / "top_mean_raw_hype.png"
    stale_return_figure = figures_dir / "return_distribution_full_vs_hype_window.png"
    stale_table.write_text("stale\n", encoding="utf-8")
    stale_figure.write_bytes(b"stale")
    stale_return_figure.write_bytes(b"stale")

    build_hype_report_artifacts(
        hype_panel_file=inputs["panel"],
        weekly_summary_file=inputs["weekly"],
        stock_summary_file=inputs["stock"],
        hype_summary_json=inputs["summary"],
        chunk_summary_json=[inputs["chunk_1"], inputs["chunk_2"]],
        results_dir=results_dir,
        figures_dir=figures_dir,
        top_n=2,
        figure_dpi=160,
        repo_root=tmp_path,
    )

    assert not stale_table.exists()
    assert not stale_figure.exists()
    assert not stale_return_figure.exists()


def test_build_report_artifacts_writes_goal4b_market_quant_outputs(
    tmp_path: Path,
) -> None:
    pytest.importorskip("matplotlib")
    inputs = _write_goal4b_inputs(tmp_path)

    paths = build_hype_report_artifacts(
        hype_panel_file=inputs["panel"],
        weekly_summary_file=inputs["weekly"],
        stock_summary_file=inputs["stock"],
        hype_summary_json=inputs["summary"],
        chunk_summary_json=[inputs["chunk_1"]],
        include_market_quant=True,
        daily_market_panel_file=inputs["daily_market"],
        weekly_market_weights_file=inputs["weekly_weights"],
        universe_file=inputs["universe"],
        company_metadata_file=inputs["metadata"],
        tej_validation_json=inputs["validation"],
        raw_tej_return_file=inputs["raw_returns"],
        market_background_start="2025-04-01",
        market_background_end="2025-04-30",
        hype_trading_start="2025-04-07",
        hype_trading_end="2025-04-18",
        results_dir=tmp_path / "report/results/pilot_8w",
        figures_dir=tmp_path / "report/figures/pilot_8w",
        top_n=2,
        figure_dpi=160,
        repo_root=tmp_path,
    )

    for name in MARKET_TABLES:
        csv_path, md_path = paths.table_paths[name]
        assert csv_path.is_file()
        assert md_path.is_file()

    for filename in [*REQUIRED_FIGURES, *MARKET_FIGURES]:
        figure_path = paths.figures_dir / filename
        assert figure_path.is_file()
        assert figure_path.stat().st_size > 0

    correlation = pd.read_csv(
        paths.results_dir / "hype_return_volatility_correlation_summary.csv"
    )
    assert set(correlation["target"]) == {
        "weekly_return",
        "weekly_realized_volatility",
    }
    assert correlation["interpretation_note"].str.contains("not a predictive").all()

    case_study = pd.read_csv(paths.results_dir / "key_stock_case_study_summary.csv")
    assert set(case_study["ticker"].astype(str)) == set(DEFAULT_KEY_TICKERS)
    assert case_study["week_end"].max() == "2025-04-18"
    assert {
        "pooled_raw_hype",
        "pooled_market_cap_weight",
        "pooled_market_cap_adjusted_hype",
    }.issubset(case_study.columns)
    sector_pooled = pd.read_csv(paths.results_dir / "sector_pooled_hype_summary.csv")
    assert {
        "industry_code",
        "pooled_sector_raw_hype",
        "pooled_sector_market_cap_weight",
        "pooled_sector_market_cap_adjusted_hype",
    }.issubset(sector_pooled.columns)
    industry_mapping = pd.read_csv(paths.results_dir / "tej_industry_label_mapping.csv")
    assert "full_original_industry_label" in industry_mapping.columns

    manifest = json.loads(paths.artifact_manifest.read_text(encoding="utf-8"))
    assert manifest["market_quant_included"] is True
    assert manifest["reporting_layer"] == "Goal 4A + Goal 4B + Goal 4C"
    assert manifest["cross_sectional_hype_reporting"] == "pooled_only"
    goal4b = [
        layer for layer in manifest["reporting_layers"] if layer["goal"] == "Goal 4B"
    ][0]
    assert set(MARKET_TABLES).issubset(goal4b["tables"])
    assert (
        "pooled_raw_hype_vs_pooled_market_cap_weight_scatter_zoom.png"
        in goal4b["revised_figures"]
    )
    goal4c = [
        layer for layer in manifest["reporting_layers"] if layer["goal"] == "Goal 4C"
    ][0]
    assert "stock_pooled_hype_summary" in goal4c["tables"]
    assert (
        "pooled_sector_raw_hype_vs_pooled_market_cap_weight_scatter.png"
        in goal4c["figures"]
    )


def test_build_report_artifacts_records_missing_optional_chunk_summaries(
    tmp_path: Path,
) -> None:
    pytest.importorskip("matplotlib")
    inputs = _write_inputs(tmp_path)

    paths = build_hype_report_artifacts(
        hype_panel_file=inputs["panel"],
        weekly_summary_file=inputs["weekly"],
        stock_summary_file=inputs["stock"],
        hype_summary_json=inputs["summary"],
        results_dir=tmp_path / "report/results/pilot_8w",
        figures_dir=tmp_path / "report/figures/pilot_8w",
        top_n=2,
        figure_dpi=160,
        repo_root=tmp_path,
    )

    pipeline_summary = pd.read_csv(
        paths.results_dir / "pipeline_validation_summary.csv"
    )
    supplied = pipeline_summary.loc[
        pipeline_summary["metric"].eq("GDELT chunk summaries supplied"),
        "value",
    ].iloc[0]
    assert supplied is False or str(supplied).lower() == "false"


def test_visual_qa_fails_for_too_small_generated_figures(tmp_path: Path) -> None:
    figures_dir = tmp_path / "report/figures/pilot_8w"
    figures_dir.mkdir(parents=True)
    tiny_png_header = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR" + (1).to_bytes(4, "big") + (1).to_bytes(4, "big")
    )
    specs = []
    for filename in REQUIRED_FIGURES:
        (figures_dir / filename).write_bytes(tiny_png_header)
        specs.append(
            FigureSpec(
                filename=filename,
                title="Synthetic title",
                chart_type="bar",
                purpose="Synthetic purpose.",
                input_rows_used=1,
                dpi=160,
                x_label="x",
                y_label="y",
            )
        )

    with pytest.raises(HypeReportError, match="Objective figure QA failed"):
        validate_figure_outputs(figures_dir=figures_dir, specs=specs, top_n=2)


def test_output_paths_are_restricted_to_report_directories(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)

    with pytest.raises(HypeReportError, match="Results directory"):
        build_hype_report_artifacts(
            hype_panel_file=inputs["panel"],
            weekly_summary_file=inputs["weekly"],
            stock_summary_file=inputs["stock"],
            hype_summary_json=inputs["summary"],
            results_dir=tmp_path / "data/processed/report",
            figures_dir=tmp_path / "report/figures/pilot_8w",
            repo_root=tmp_path,
        )

    with pytest.raises(HypeReportError, match="Figures directory"):
        build_hype_report_artifacts(
            hype_panel_file=inputs["panel"],
            weekly_summary_file=inputs["weekly"],
            stock_summary_file=inputs["stock"],
            hype_summary_json=inputs["summary"],
            results_dir=tmp_path / "report/results/pilot_8w",
            figures_dir=tmp_path / "data/processed/figures",
            repo_root=tmp_path,
        )


def test_report_builder_requires_existing_hype_outputs(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    raw_like_panel = pd.read_csv(inputs["panel"]).drop(
        columns=["raw_hype", "market_cap_adjusted_hype"]
    )
    raw_like_path = tmp_path / "inputs/raw_like_panel.csv"
    raw_like_panel.to_csv(raw_like_path, index=False)

    with pytest.raises(HypeReportError, match="missing required column"):
        build_hype_report_artifacts(
            hype_panel_file=raw_like_path,
            weekly_summary_file=inputs["weekly"],
            stock_summary_file=inputs["stock"],
            hype_summary_json=inputs["summary"],
            results_dir=tmp_path / "report/results/pilot_8w",
            figures_dir=tmp_path / "report/figures/pilot_8w",
            repo_root=tmp_path,
        )
