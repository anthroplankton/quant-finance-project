from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from quant_finance_project.hype.input_panel import (
    FORBIDDEN_HYPE_COLUMNS,
    HypeInputPanelError,
    build_hype_input_panel,
)


def _write_universe(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "stock_id": "2330",
                "ticker": "2330",
                "official_chinese_name": "台灣積體電路製造股份有限公司",
                "official_english_name": "Taiwan Semiconductor Manufacturing Co Ltd",
                "industry": "Semiconductors",
            },
            {
                "stock_id": "2454",
                "ticker": "2454",
                "official_chinese_name": "聯發科技股份有限公司",
                "official_english_name": "MediaTek Inc",
                "industry": "Semiconductors",
            },
            {
                "stock_id": "2317",
                "ticker": "2317",
                "official_chinese_name": "鴻海精密工業股份有限公司",
                "official_english_name": "Hon Hai Precision Industry Co Ltd",
                "industry": "Electronics",
            },
        ]
    ).to_csv(path, index=False)
    return path


def _news_rows() -> list[dict[str, str | int]]:
    return [
        {
            "stock_id": "2330",
            "ticker": "2330",
            "official_chinese_name": "台灣積體電路製造股份有限公司",
            "official_english_name": "Taiwan Semiconductor Manufacturing Co Ltd",
            "industry": "Semiconductors",
            "week_index": 1,
            "week_start": "2025-04-05",
            "week_end": "2025-04-11",
            "news_count_unique_urls": 2,
            "matched_rows": 3,
            "active_news_days": 2,
        },
        {
            "stock_id": "2454",
            "ticker": "2454",
            "official_chinese_name": "聯發科技股份有限公司",
            "official_english_name": "MediaTek Inc",
            "industry": "Semiconductors",
            "week_index": 1,
            "week_start": "2025-04-05",
            "week_end": "2025-04-11",
            "news_count_unique_urls": 0,
            "matched_rows": 0,
            "active_news_days": 0,
        },
        {
            "stock_id": "2317",
            "ticker": "2317",
            "official_chinese_name": "鴻海精密工業股份有限公司",
            "official_english_name": "Hon Hai Precision Industry Co Ltd",
            "industry": "Electronics",
            "week_index": 1,
            "week_start": "2025-04-05",
            "week_end": "2025-04-11",
            "news_count_unique_urls": 1,
            "matched_rows": 1,
            "active_news_days": 1,
        },
        {
            "stock_id": "2330",
            "ticker": "2330",
            "official_chinese_name": "台灣積體電路製造股份有限公司",
            "official_english_name": "Taiwan Semiconductor Manufacturing Co Ltd",
            "industry": "Semiconductors",
            "week_index": 2,
            "week_start": "2025-04-12",
            "week_end": "2025-04-18",
            "news_count_unique_urls": 0,
            "matched_rows": 0,
            "active_news_days": 0,
        },
        {
            "stock_id": "2454",
            "ticker": "2454",
            "official_chinese_name": "聯發科技股份有限公司",
            "official_english_name": "MediaTek Inc",
            "industry": "Semiconductors",
            "week_index": 2,
            "week_start": "2025-04-12",
            "week_end": "2025-04-18",
            "news_count_unique_urls": 4,
            "matched_rows": 4,
            "active_news_days": 1,
        },
        {
            "stock_id": "2317",
            "ticker": "2317",
            "official_chinese_name": "鴻海精密工業股份有限公司",
            "official_english_name": "Hon Hai Precision Industry Co Ltd",
            "industry": "Electronics",
            "week_index": 2,
            "week_start": "2025-04-12",
            "week_end": "2025-04-18",
            "news_count_unique_urls": 0,
            "matched_rows": 0,
            "active_news_days": 0,
        },
    ]


def _weight_rows() -> list[dict[str, str | float]]:
    return [
        {
            "week_end": "2025-04-11",
            "weight_date": "2025-04-11",
            "stock_id": "2317",
            "ticker": "2317",
            "market_cap": 200.0,
            "weekly_market_cap_weight": 0.2,
        },
        {
            "week_end": "2025-04-11",
            "weight_date": "2025-04-11",
            "stock_id": "2330",
            "ticker": "2330",
            "market_cap": 500.0,
            "weekly_market_cap_weight": 0.5,
        },
        {
            "week_end": "2025-04-11",
            "weight_date": "2025-04-11",
            "stock_id": "2454",
            "ticker": "2454",
            "market_cap": 300.0,
            "weekly_market_cap_weight": 0.3,
        },
        {
            "week_end": "2025-04-18",
            "weight_date": "2025-04-18",
            "stock_id": "2317",
            "ticker": "2317",
            "market_cap": 250.0,
            "weekly_market_cap_weight": 0.25,
        },
        {
            "week_end": "2025-04-18",
            "weight_date": "2025-04-18",
            "stock_id": "2330",
            "ticker": "2330",
            "market_cap": 500.0,
            "weekly_market_cap_weight": 0.5,
        },
        {
            "week_end": "2025-04-18",
            "weight_date": "2025-04-18",
            "stock_id": "2454",
            "ticker": "2454",
            "market_cap": 250.0,
            "weekly_market_cap_weight": 0.25,
        },
    ]


def _eight_week_news_rows() -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    tickers = ["2317", "2330", "2454"]
    start = date(2025, 4, 5)
    for week_index in range(1, 9):
        week_start = start + timedelta(days=(week_index - 1) * 7)
        week_end = week_start + timedelta(days=6)
        for ticker in tickers:
            has_news = ticker == "2330"
            rows.append(
                {
                    "ticker": ticker,
                    "week_index": week_index,
                    "week_start": week_start.isoformat(),
                    "week_end": week_end.isoformat(),
                    "news_count_unique_urls": 1 if has_news else 0,
                    "matched_rows": 1 if has_news else 0,
                    "active_news_days": 1 if has_news else 0,
                }
            )
    return rows


def _eight_week_weight_rows() -> list[dict[str, str | float]]:
    rows: list[dict[str, str | float]] = []
    weights = {
        "2317": 0.2,
        "2330": 0.5,
        "2454": 0.3,
    }
    start = date(2025, 4, 5)
    for week_index in range(1, 9):
        week_start = start + timedelta(days=(week_index - 1) * 7)
        week_end = week_start + timedelta(days=6)
        for ticker, weight in weights.items():
            rows.append(
                {
                    "week_end": week_end.isoformat(),
                    "weight_date": week_end.isoformat(),
                    "stock_id": ticker,
                    "ticker": ticker,
                    "market_cap": weight * 1000,
                    "weekly_market_cap_weight": weight,
                }
            )
    return rows


def _write_inputs(
    tmp_path: Path,
    *,
    news_rows: list[dict[str, object]] | None = None,
    weight_rows: list[dict[str, object]] | None = None,
) -> tuple[Path, Path, Path]:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    news = tmp_path / "data/processed/news/stock_week.csv"
    weights = tmp_path / "data/processed/tej/weekly_weights.csv"
    news.parent.mkdir(parents=True, exist_ok=True)
    weights.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(news_rows if news_rows is not None else _news_rows()).to_csv(
        news,
        index=False,
    )
    pd.DataFrame(weight_rows if weight_rows is not None else _weight_rows()).to_csv(
        weights,
        index=False,
    )
    return universe, news, weights


def _build(tmp_path: Path, *, news_rows=None, weight_rows=None, write_files=False):
    universe, news, weights = _write_inputs(
        tmp_path,
        news_rows=news_rows,
        weight_rows=weight_rows,
    )
    return build_hype_input_panel(
        news_counts_file=news,
        market_weights_file=weights,
        universe_file=universe,
        output_dir="data/processed/hype_index/test_panel",
        pilot_start_date="2025-04-05",
        pilot_end_date="2025-04-18",
        repo_root=tmp_path,
        write_files=write_files,
    )


def test_synthetic_hype_input_join_writes_expected_panel(tmp_path: Path) -> None:
    panel, weight_summary, summary, paths = _build(tmp_path, write_files=True)

    assert paths is not None
    assert paths.panel.exists()
    assert len(panel) == 6
    assert len(weight_summary) == 2
    assert summary["expected_rows"] == 6
    assert summary["actual_rows"] == 6
    assert summary["week_count"] == 2
    assert summary["universe_size"] == 3
    assert summary["validation_status"] == "passed"
    assert summary["market_cap_weights_joined"] is True
    assert summary["hype_index_computed"] is False
    assert summary["total_news_count_unique_urls"] == 7
    assert panel.groupby("week_end")["weekly_market_cap_weight"].sum().tolist() == (
        pytest.approx([1.0, 1.0])
    )
    assert set(panel["weekly_total_news_count_unique_urls"]) == {3, 4}
    assert sorted(panel["week_index"].unique().tolist()) == [1, 2]
    assert FORBIDDEN_HYPE_COLUMNS & set(panel.columns) == set()


def test_stale_news_week_index_fails_validation(tmp_path: Path) -> None:
    news = [
        {
            **row,
            "week_index": 99,
        }
        if row["week_end"] == "2025-04-18"
        else row
        for row in _news_rows()
    ]

    with pytest.raises(HypeInputPanelError, match="week_index"):
        _build(tmp_path, news_rows=news)


def test_missing_news_week_index_computes_canonical_index(tmp_path: Path) -> None:
    news = [
        {key: value for key, value in row.items() if key != "week_index"}
        for row in _news_rows()
    ]

    panel, _, summary, _ = _build(tmp_path, news_rows=news)

    assert summary["validation_status"] == "passed"
    assert sorted(panel["week_index"].unique().tolist()) == [1, 2]
    assert (
        panel.loc[panel["week_end"].eq("2025-04-11"), "week_index"].unique().tolist()
        == [1]
    )
    assert (
        panel.loc[panel["week_end"].eq("2025-04-18"), "week_index"].unique().tolist()
        == [2]
    )


def test_matching_news_week_index_passes_validation(tmp_path: Path) -> None:
    panel, _, summary, _ = _build(tmp_path)

    assert summary["validation_status"] == "passed"
    assert sorted(panel["week_index"].unique().tolist()) == [1, 2]


def test_output_week_index_is_canonical_for_8_week_pilot(tmp_path: Path) -> None:
    universe, news, weights = _write_inputs(
        tmp_path,
        news_rows=_eight_week_news_rows(),
        weight_rows=_eight_week_weight_rows(),
    )

    panel, _, summary, _ = build_hype_input_panel(
        news_counts_file=news,
        market_weights_file=weights,
        universe_file=universe,
        output_dir="data/processed/hype_index/test_panel",
        pilot_start_date="2025-04-05",
        pilot_end_date="2025-05-30",
        repo_root=tmp_path,
        write_files=False,
    )

    assert len(panel) == 24
    assert summary["week_count"] == 8
    assert summary["validation_status"] == "passed"
    assert sorted(panel["week_index"].unique().tolist()) == list(range(1, 9))
    assert (
        panel.drop_duplicates(["week_end", "week_index"])
        .sort_values("week_index")["week_end"]
        .tolist()
        == [
            "2025-04-11",
            "2025-04-18",
            "2025-04-25",
            "2025-05-02",
            "2025-05-09",
            "2025-05-16",
            "2025-05-23",
            "2025-05-30",
        ]
    )


def test_missing_market_weight_fails_validation(tmp_path: Path) -> None:
    weights = [
        row
        for row in _weight_rows()
        if not (row["ticker"] == "2317" and row["week_end"] == "2025-04-18")
    ]

    with pytest.raises(HypeInputPanelError, match="3 rows per selected week"):
        _build(tmp_path, weight_rows=weights)


def test_duplicate_market_weight_ticker_week_fails_validation(tmp_path: Path) -> None:
    weights = [*_weight_rows(), _weight_rows()[0].copy()]

    with pytest.raises(HypeInputPanelError, match="duplicate ticker-week"):
        _build(tmp_path, weight_rows=weights)


def test_market_weights_not_summing_to_one_fails_validation(tmp_path: Path) -> None:
    weights = _weight_rows()
    weights[0] = {**weights[0], "weekly_market_cap_weight": 0.4}

    with pytest.raises(HypeInputPanelError, match="sum to 1"):
        _build(tmp_path, weight_rows=weights)


def test_weight_date_after_week_end_fails_validation(tmp_path: Path) -> None:
    weights = [
        {
            **row,
            "weight_date": "2025-04-19" if row["week_end"] == "2025-04-18" else row["weight_date"],
        }
        for row in _weight_rows()
    ]

    with pytest.raises(HypeInputPanelError, match="inside the corresponding"):
        _build(tmp_path, weight_rows=weights)


def test_weight_date_earlier_than_week_start_fails_validation(tmp_path: Path) -> None:
    weights = [
        {
            **row,
            "weight_date": "2025-04-04" if row["week_end"] == "2025-04-11" else row["weight_date"],
        }
        for row in _weight_rows()
    ]

    with pytest.raises(HypeInputPanelError, match="inside the corresponding"):
        _build(tmp_path, weight_rows=weights)


def test_friday_holiday_weight_date_thursday_inside_week_passes(tmp_path: Path) -> None:
    weights = [
        {
            **row,
            "weight_date": "2025-04-17" if row["week_end"] == "2025-04-18" else row["weight_date"],
        }
        for row in _weight_rows()
    ]

    panel, weight_summary, summary, _ = _build(tmp_path, weight_rows=weights)

    assert len(panel) == 6
    assert summary["validation_status"] == "passed"
    assert weight_summary.loc[
        weight_summary["week_end"].eq("2025-04-18"),
        "weight_date",
    ].iloc[0] == "2025-04-17"


def test_unknown_ticker_in_market_weights_fails_validation(tmp_path: Path) -> None:
    weights = [
        {
            **row,
            "ticker": "9999",
            "stock_id": "9999",
        }
        if row["ticker"] == "2317"
        else row
        for row in _weight_rows()
    ]

    with pytest.raises(HypeInputPanelError, match="outside the universe"):
        _build(tmp_path, weight_rows=weights)


def test_unknown_ticker_in_news_counts_fails_validation(tmp_path: Path) -> None:
    news = [
        {
            **row,
            "ticker": "9999",
            "stock_id": "9999",
        }
        if row["ticker"] == "2317"
        else row
        for row in _news_rows()
    ]

    with pytest.raises(HypeInputPanelError, match="outside the universe"):
        _build(tmp_path, news_rows=news)


def test_mismatched_week_end_between_news_and_weights_fails_validation(
    tmp_path: Path,
) -> None:
    weights = [
        {
            **row,
            "week_end": "2025-04-25",
            "weight_date": "2025-04-25",
        }
        if row["week_end"] == "2025-04-18"
        else row
        for row in _weight_rows()
    ]

    with pytest.raises(HypeInputPanelError, match="week_end values do not match"):
        _build(tmp_path, weight_rows=weights)


def test_zero_weekly_total_news_count_fails_validation(tmp_path: Path) -> None:
    news = [
        {
            **row,
            "news_count_unique_urls": 0,
            "matched_rows": 0,
            "active_news_days": 0,
        }
        if row["week_end"] == "2025-04-18"
        else row
        for row in _news_rows()
    ]

    with pytest.raises(HypeInputPanelError, match="greater than 0"):
        _build(tmp_path, news_rows=news)


def test_hype_index_columns_are_not_produced(tmp_path: Path) -> None:
    panel, _, summary, _ = _build(tmp_path)

    assert FORBIDDEN_HYPE_COLUMNS & set(panel.columns) == set()
    assert "weekly_total_news_count_unique_urls" in panel.columns
    assert summary["hype_index_computed"] is False
    assert summary["market_cap_weights_joined"] is True
