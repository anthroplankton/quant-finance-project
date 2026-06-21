from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from quant_finance_project.news.weekly_counts import (
    FORBIDDEN_HYPE_COLUMNS,
    WeeklyCountAggregationError,
    assign_week,
    build_gdelt_weekly_counts,
    build_weekly_bins,
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


def _write_chunk(
    path: Path,
    *,
    rows: list[dict[str, str | int]],
    start_date: str = "2025-04-05",
    end_date: str = "2025-04-11",
    summary_overrides: dict[str, object] | None = None,
    drop_summary_fields: set[str] | None = None,
) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    summary = {
        "start_date": start_date,
        "end_date": end_date,
        "completed": True,
        "files_failed": 0,
        "missing_file_threshold_exceeded": False,
        "disk_limit_exceeded": False,
        "max_download_mb_exceeded": False,
        "candidate_file_count_capped": 96,
        "candidate_file_count_uncapped": 96,
        "files_processed": 96,
        "files_missing": 0,
        "matched_rows": sum(int(row["matched_rows"]) for row in rows),
        "unique_urls": sum(int(row["unique_urls"]) for row in rows),
        "missing_file_ratio": 0,
    }
    if summary_overrides:
        summary.update(summary_overrides)
    if drop_summary_fields:
        for field in drop_summary_fields:
            summary.pop(field, None)
    (path / "probe_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    pd.DataFrame(rows, columns=["date", "matched_ticker", "matched_rows", "unique_urls"]).to_csv(
        path / "stock_day_counts.csv",
        index=False,
    )
    return path


def test_weekly_bin_assignment_for_8_week_window() -> None:
    bins = build_weekly_bins("2025-04-05", "2025-05-30")

    assert len(bins) == 8
    assert assign_week("2025-04-05", bins) == (
        1,
        "2025-04-05",
        "2025-04-11",
    )
    assert assign_week("2025-04-11", bins) == (
        1,
        "2025-04-05",
        "2025-04-11",
    )
    assert assign_week("2025-04-12", bins) == (
        2,
        "2025-04-12",
        "2025-04-18",
    )
    assert assign_week("2025-05-30", bins) == (
        8,
        "2025-05-24",
        "2025-05-30",
    )


def test_weekly_aggregation_zero_fills_synthetic_universe(tmp_path: Path) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    chunk = _write_chunk(
        tmp_path / "chunk_a",
        start_date="2025-04-05",
        end_date="2025-04-18",
        rows=[
            {
                "date": "2025-04-05",
                "matched_ticker": "2330",
                "matched_rows": 2,
                "unique_urls": 1,
            },
            {
                "date": "2025-04-11",
                "matched_ticker": "2330",
                "matched_rows": 3,
                "unique_urls": 3,
            },
            {
                "date": "2025-04-12",
                "matched_ticker": "2454",
                "matched_rows": 4,
                "unique_urls": 4,
            },
        ],
    )

    stock_week, weekly_totals, coverage, summary, paths = build_gdelt_weekly_counts(
        input_dirs=[chunk],
        universe_file=universe,
        output_dir="data/processed/news/weekly_counts",
        pilot_start_date="2025-04-05",
        pilot_end_date="2025-04-18",
        repo_root=tmp_path,
    )

    assert paths is not None
    assert len(stock_week) == 6
    assert summary["expected_rows"] == 6
    assert summary["actual_rows"] == 6
    assert summary["zero_stock_week_rows"] == 4
    assert summary["zero_stock_week_ratio"] == pytest.approx(4 / 6)
    assert summary["total_news_count_unique_urls"] == 8
    assert summary["total_matched_rows"] == 9
    assert set(weekly_totals["news_count_unique_urls"]) == {4}
    assert len(coverage) == 3

    tsmc_week_1 = stock_week.loc[
        (stock_week["ticker"] == "2330") & (stock_week["week_index"] == 1)
    ].iloc[0]
    assert tsmc_week_1["news_count_unique_urls"] == 4
    assert tsmc_week_1["matched_rows"] == 5
    assert tsmc_week_1["active_news_days"] == 2

    hon_hai_week_2 = stock_week.loc[
        (stock_week["ticker"] == "2317") & (stock_week["week_index"] == 2)
    ].iloc[0]
    assert hon_hai_week_2["news_count_unique_urls"] == 0
    assert hon_hai_week_2["matched_rows"] == 0
    assert hon_hai_week_2["active_news_days"] == 0

    forbidden = FORBIDDEN_HYPE_COLUMNS & set(stock_week.columns)
    assert forbidden == set()


def test_capped_probe_summary_fails_before_zero_fill(tmp_path: Path) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    chunk = _write_chunk(
        tmp_path / "chunk_a",
        rows=[
            {
                "date": "2025-04-05",
                "matched_ticker": "2330",
                "matched_rows": 1,
                "unique_urls": 1,
            }
        ],
        summary_overrides={
            "candidate_file_count_capped": 8,
            "candidate_file_count_uncapped": 96,
            "files_processed": 8,
            "files_missing": 0,
            "files_failed": 0,
        },
    )

    with pytest.raises(WeeklyCountAggregationError, match="is capped"):
        build_gdelt_weekly_counts(
            input_dirs=[chunk],
            universe_file=universe,
            output_dir="data/processed/news/weekly_counts",
            pilot_start_date="2025-04-05",
            pilot_end_date="2025-04-11",
            repo_root=tmp_path,
            write_files=False,
        )


def test_incomplete_file_grid_fails_before_zero_fill(tmp_path: Path) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    chunk = _write_chunk(
        tmp_path / "chunk_a",
        rows=[
            {
                "date": "2025-04-05",
                "matched_ticker": "2330",
                "matched_rows": 1,
                "unique_urls": 1,
            }
        ],
        summary_overrides={
            "candidate_file_count_capped": 96,
            "candidate_file_count_uncapped": 96,
            "files_processed": 95,
            "files_missing": 0,
            "files_failed": 0,
        },
    )

    with pytest.raises(WeeklyCountAggregationError, match="incomplete GDELT file-grid"):
        build_gdelt_weekly_counts(
            input_dirs=[chunk],
            universe_file=universe,
            output_dir="data/processed/news/weekly_counts",
            pilot_start_date="2025-04-05",
            pilot_end_date="2025-04-11",
            repo_root=tmp_path,
            write_files=False,
        )


def test_valid_file_grid_with_missing_files_passes(tmp_path: Path) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    chunk = _write_chunk(
        tmp_path / "chunk_a",
        rows=[
            {
                "date": "2025-04-05",
                "matched_ticker": "2330",
                "matched_rows": 1,
                "unique_urls": 1,
            }
        ],
        summary_overrides={
            "candidate_file_count_capped": 96,
            "candidate_file_count_uncapped": 96,
            "files_processed": 94,
            "files_missing": 2,
            "files_failed": 0,
            "missing_file_ratio": 2 / 96,
        },
    )

    stock_week, _, _, summary, _ = build_gdelt_weekly_counts(
        input_dirs=[chunk],
        universe_file=universe,
        output_dir="data/processed/news/weekly_counts",
        pilot_start_date="2025-04-05",
        pilot_end_date="2025-04-11",
        repo_root=tmp_path,
        write_files=False,
    )

    assert len(stock_week) == 3
    assert summary["input_chunk_summaries"][0]["files_missing"] == 2
    assert summary["validation_status"] == "passed"


def test_missing_file_grid_summary_field_fails_closed(tmp_path: Path) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    chunk = _write_chunk(
        tmp_path / "chunk_a",
        rows=[
            {
                "date": "2025-04-05",
                "matched_ticker": "2330",
                "matched_rows": 1,
                "unique_urls": 1,
            }
        ],
        drop_summary_fields={"candidate_file_count_uncapped"},
    )

    with pytest.raises(
        WeeklyCountAggregationError,
        match="missing required field candidate_file_count_uncapped",
    ):
        build_gdelt_weekly_counts(
            input_dirs=[chunk],
            universe_file=universe,
            output_dir="data/processed/news/weekly_counts",
            pilot_start_date="2025-04-05",
            pilot_end_date="2025-04-11",
            repo_root=tmp_path,
            write_files=False,
        )


def test_empty_count_file_with_positive_summary_matches_fails(
    tmp_path: Path,
) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    chunk = _write_chunk(
        tmp_path / "chunk_a",
        rows=[],
        summary_overrides={
            "matched_rows": 3,
            "unique_urls": 2,
        },
    )

    with pytest.raises(
        WeeklyCountAggregationError,
        match=r"input directory .*chunk_a.*empty.*matched_rows=3.*sum=0",
    ):
        build_gdelt_weekly_counts(
            input_dirs=[chunk],
            universe_file=universe,
            output_dir="data/processed/news/weekly_counts",
            pilot_start_date="2025-04-05",
            pilot_end_date="2025-04-11",
            repo_root=tmp_path,
            write_files=False,
        )


def test_empty_count_file_with_zero_summary_matches_passes(tmp_path: Path) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    chunk = _write_chunk(
        tmp_path / "chunk_a",
        rows=[],
        summary_overrides={
            "matched_rows": 0,
            "unique_urls": 0,
        },
    )

    stock_week, weekly_totals, _, summary, _ = build_gdelt_weekly_counts(
        input_dirs=[chunk],
        universe_file=universe,
        output_dir="data/processed/news/weekly_counts",
        pilot_start_date="2025-04-05",
        pilot_end_date="2025-04-11",
        repo_root=tmp_path,
        write_files=False,
    )

    assert len(stock_week) == 3
    assert weekly_totals["news_count_unique_urls"].tolist() == [0]
    assert summary["validation_status"] == "passed"


def test_count_file_matched_rows_less_than_summary_fails(tmp_path: Path) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    chunk = _write_chunk(
        tmp_path / "chunk_a",
        rows=[
            {
                "date": "2025-04-05",
                "matched_ticker": "2330",
                "matched_rows": 1,
                "unique_urls": 1,
            }
        ],
        summary_overrides={
            "matched_rows": 2,
            "unique_urls": 1,
        },
    )

    with pytest.raises(
        WeeklyCountAggregationError,
        match=r"summary matched_rows=2.*stock_day_counts matched_rows sum=1",
    ):
        build_gdelt_weekly_counts(
            input_dirs=[chunk],
            universe_file=universe,
            output_dir="data/processed/news/weekly_counts",
            pilot_start_date="2025-04-05",
            pilot_end_date="2025-04-11",
            repo_root=tmp_path,
            write_files=False,
        )


def test_count_file_matched_rows_greater_than_summary_fails(tmp_path: Path) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    chunk = _write_chunk(
        tmp_path / "chunk_a",
        rows=[
            {
                "date": "2025-04-05",
                "matched_ticker": "2330",
                "matched_rows": 3,
                "unique_urls": 1,
            }
        ],
        summary_overrides={
            "matched_rows": 2,
            "unique_urls": 1,
        },
    )

    with pytest.raises(
        WeeklyCountAggregationError,
        match=r"summary matched_rows=2.*stock_day_counts matched_rows sum=3",
    ):
        build_gdelt_weekly_counts(
            input_dirs=[chunk],
            universe_file=universe,
            output_dir="data/processed/news/weekly_counts",
            pilot_start_date="2025-04-05",
            pilot_end_date="2025-04-11",
            repo_root=tmp_path,
            write_files=False,
        )


def test_count_file_matched_rows_equal_summary_passes(tmp_path: Path) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    chunk = _write_chunk(
        tmp_path / "chunk_a",
        rows=[
            {
                "date": "2025-04-05",
                "matched_ticker": "2330",
                "matched_rows": 1,
                "unique_urls": 1,
            },
            {
                "date": "2025-04-06",
                "matched_ticker": "2454",
                "matched_rows": 2,
                "unique_urls": 1,
            },
        ],
        summary_overrides={
            "matched_rows": 3,
            "unique_urls": 2,
        },
    )

    stock_week, _, _, summary, _ = build_gdelt_weekly_counts(
        input_dirs=[chunk],
        universe_file=universe,
        output_dir="data/processed/news/weekly_counts",
        pilot_start_date="2025-04-05",
        pilot_end_date="2025-04-11",
        repo_root=tmp_path,
        write_files=False,
    )

    assert int(stock_week["matched_rows"].sum()) == 3
    assert summary["validation_status"] == "passed"


def test_missing_summary_matched_rows_fails_closed(tmp_path: Path) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    chunk = _write_chunk(
        tmp_path / "chunk_a",
        rows=[
            {
                "date": "2025-04-05",
                "matched_ticker": "2330",
                "matched_rows": 1,
                "unique_urls": 1,
            }
        ],
        drop_summary_fields={"matched_rows"},
    )

    with pytest.raises(
        WeeklyCountAggregationError,
        match="missing required field matched_rows",
    ):
        build_gdelt_weekly_counts(
            input_dirs=[chunk],
            universe_file=universe,
            output_dir="data/processed/news/weekly_counts",
            pilot_start_date="2025-04-05",
            pilot_end_date="2025-04-11",
            repo_root=tmp_path,
            write_files=False,
        )


def test_positive_summary_unique_urls_with_zero_count_unique_urls_fails(
    tmp_path: Path,
) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    chunk = _write_chunk(
        tmp_path / "chunk_a",
        rows=[
            {
                "date": "2025-04-05",
                "matched_ticker": "2330",
                "matched_rows": 1,
                "unique_urls": 0,
            }
        ],
        summary_overrides={
            "matched_rows": 1,
            "unique_urls": 1,
        },
    )

    with pytest.raises(
        WeeklyCountAggregationError,
        match=r"summary unique_urls=1.*stock_day_counts unique_urls sum=0",
    ):
        build_gdelt_weekly_counts(
            input_dirs=[chunk],
            universe_file=universe,
            output_dir="data/processed/news/weekly_counts",
            pilot_start_date="2025-04-05",
            pilot_end_date="2025-04-11",
            repo_root=tmp_path,
            write_files=False,
        )


def test_company_level_unique_url_sum_can_exceed_summary_unique_urls(
    tmp_path: Path,
) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    chunk = _write_chunk(
        tmp_path / "chunk_a",
        rows=[
            {
                "date": "2025-04-05",
                "matched_ticker": "2330",
                "matched_rows": 1,
                "unique_urls": 1,
            },
            {
                "date": "2025-04-05",
                "matched_ticker": "2454",
                "matched_rows": 1,
                "unique_urls": 1,
            },
        ],
        summary_overrides={
            "matched_rows": 2,
            "unique_urls": 1,
        },
    )

    stock_week, _, _, summary, _ = build_gdelt_weekly_counts(
        input_dirs=[chunk],
        universe_file=universe,
        output_dir="data/processed/news/weekly_counts",
        pilot_start_date="2025-04-05",
        pilot_end_date="2025-04-11",
        repo_root=tmp_path,
        write_files=False,
    )

    assert int(stock_week["news_count_unique_urls"].sum()) == 2
    assert summary["input_chunk_summaries"][0]["unique_urls"] == 1
    assert summary["validation_status"] == "passed"


def test_stock_day_after_own_chunk_range_fails_validation(tmp_path: Path) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    chunk = _write_chunk(
        tmp_path / "chunk_a",
        start_date="2025-04-05",
        end_date="2025-05-02",
        rows=[
            {
                "date": "2025-05-03",
                "matched_ticker": "2330",
                "matched_rows": 1,
                "unique_urls": 1,
            }
        ],
    )

    with pytest.raises(
        WeeklyCountAggregationError,
        match="2025-05-03.*2025-04-05 to 2025-05-02",
    ):
        build_gdelt_weekly_counts(
            input_dirs=[chunk],
            universe_file=universe,
            output_dir="data/processed/news/weekly_counts",
            pilot_start_date="2025-04-05",
            pilot_end_date="2025-05-30",
            repo_root=tmp_path,
            write_files=False,
        )


def test_stock_day_before_own_chunk_range_fails_validation(tmp_path: Path) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    chunk = _write_chunk(
        tmp_path / "chunk_b",
        start_date="2025-05-03",
        end_date="2025-05-30",
        rows=[
            {
                "date": "2025-05-02",
                "matched_ticker": "2454",
                "matched_rows": 1,
                "unique_urls": 1,
            }
        ],
    )

    with pytest.raises(
        WeeklyCountAggregationError,
        match="2025-05-02.*2025-05-03 to 2025-05-30",
    ):
        build_gdelt_weekly_counts(
            input_dirs=[chunk],
            universe_file=universe,
            output_dir="data/processed/news/weekly_counts",
            pilot_start_date="2025-04-05",
            pilot_end_date="2025-05-30",
            repo_root=tmp_path,
            write_files=False,
        )


def test_stock_day_rows_inside_own_chunk_ranges_pass_validation(
    tmp_path: Path,
) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    first = _write_chunk(
        tmp_path / "chunk_a",
        start_date="2025-04-05",
        end_date="2025-05-02",
        rows=[
            {
                "date": "2025-05-02",
                "matched_ticker": "2330",
                "matched_rows": 1,
                "unique_urls": 1,
            }
        ],
    )
    second = _write_chunk(
        tmp_path / "chunk_b",
        start_date="2025-05-03",
        end_date="2025-05-30",
        rows=[
            {
                "date": "2025-05-03",
                "matched_ticker": "2454",
                "matched_rows": 1,
                "unique_urls": 1,
            }
        ],
    )

    stock_week, weekly_totals, _, summary, _ = build_gdelt_weekly_counts(
        input_dirs=[first, second],
        universe_file=universe,
        output_dir="data/processed/news/weekly_counts",
        pilot_start_date="2025-04-05",
        pilot_end_date="2025-05-30",
        repo_root=tmp_path,
        write_files=False,
    )

    assert len(stock_week) == 24
    assert len(weekly_totals) == 8
    assert summary["validation_status"] == "passed"


def test_missing_second_chunk_coverage_fails_before_zero_fill(tmp_path: Path) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    first = _write_chunk(
        tmp_path / "chunk_a",
        start_date="2025-04-05",
        end_date="2025-05-02",
        rows=[
            {
                "date": "2025-04-05",
                "matched_ticker": "2330",
                "matched_rows": 1,
                "unique_urls": 1,
            }
        ],
    )

    with pytest.raises(
        WeeklyCountAggregationError,
        match="Missing chunk coverage from 2025-05-03 to 2025-05-30",
    ):
        build_gdelt_weekly_counts(
            input_dirs=[first],
            universe_file=universe,
            output_dir="data/processed/news/weekly_counts",
            pilot_start_date="2025-04-05",
            pilot_end_date="2025-05-30",
            repo_root=tmp_path,
            write_files=False,
        )


def test_one_day_gap_between_chunks_fails_validation(tmp_path: Path) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    first = _write_chunk(
        tmp_path / "chunk_a",
        start_date="2025-04-05",
        end_date="2025-05-02",
        rows=[
            {
                "date": "2025-04-05",
                "matched_ticker": "2330",
                "matched_rows": 1,
                "unique_urls": 1,
            }
        ],
    )
    second = _write_chunk(
        tmp_path / "chunk_b",
        start_date="2025-05-04",
        end_date="2025-05-30",
        rows=[
            {
                "date": "2025-05-04",
                "matched_ticker": "2454",
                "matched_rows": 1,
                "unique_urls": 1,
            }
        ],
    )

    with pytest.raises(
        WeeklyCountAggregationError,
        match="Missing chunk coverage from 2025-05-03 to 2025-05-03",
    ):
        build_gdelt_weekly_counts(
            input_dirs=[first, second],
            universe_file=universe,
            output_dir="data/processed/news/weekly_counts",
            pilot_start_date="2025-04-05",
            pilot_end_date="2025-05-30",
            repo_root=tmp_path,
            write_files=False,
        )


def test_overlapping_chunk_coverage_fails_validation(tmp_path: Path) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    first = _write_chunk(
        tmp_path / "chunk_a",
        start_date="2025-04-05",
        end_date="2025-05-03",
        rows=[
            {
                "date": "2025-04-05",
                "matched_ticker": "2330",
                "matched_rows": 1,
                "unique_urls": 1,
            }
        ],
    )
    second = _write_chunk(
        tmp_path / "chunk_b",
        start_date="2025-05-03",
        end_date="2025-05-30",
        rows=[
            {
                "date": "2025-05-03",
                "matched_ticker": "2454",
                "matched_rows": 1,
                "unique_urls": 1,
            }
        ],
    )

    with pytest.raises(WeeklyCountAggregationError, match="Overlapping"):
        build_gdelt_weekly_counts(
            input_dirs=[first, second],
            universe_file=universe,
            output_dir="data/processed/news/weekly_counts",
            pilot_start_date="2025-04-05",
            pilot_end_date="2025-05-30",
            repo_root=tmp_path,
            write_files=False,
        )


@pytest.mark.parametrize(
    ("start_date", "end_date"),
    [
        ("2025-04-04", "2025-05-30"),
        ("2025-04-05", "2025-05-31"),
    ],
)
def test_chunk_coverage_outside_pilot_window_fails_validation(
    tmp_path: Path,
    start_date: str,
    end_date: str,
) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    chunk = _write_chunk(
        tmp_path / "chunk_a",
        start_date=start_date,
        end_date=end_date,
        rows=[
            {
                "date": "2025-04-05",
                "matched_ticker": "2330",
                "matched_rows": 1,
                "unique_urls": 1,
            }
        ],
    )

    with pytest.raises(WeeklyCountAggregationError, match="outside pilot window"):
        build_gdelt_weekly_counts(
            input_dirs=[chunk],
            universe_file=universe,
            output_dir="data/processed/news/weekly_counts",
            pilot_start_date="2025-04-05",
            pilot_end_date="2025-05-30",
            repo_root=tmp_path,
            write_files=False,
        )


def test_contiguous_8_week_chunk_coverage_succeeds(tmp_path: Path) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    first = _write_chunk(
        tmp_path / "chunk_a",
        start_date="2025-04-05",
        end_date="2025-05-02",
        rows=[
            {
                "date": "2025-04-05",
                "matched_ticker": "2330",
                "matched_rows": 1,
                "unique_urls": 1,
            }
        ],
    )
    second = _write_chunk(
        tmp_path / "chunk_b",
        start_date="2025-05-03",
        end_date="2025-05-30",
        rows=[
            {
                "date": "2025-05-30",
                "matched_ticker": "2454",
                "matched_rows": 1,
                "unique_urls": 1,
            }
        ],
    )

    stock_week, weekly_totals, _, summary, _ = build_gdelt_weekly_counts(
        input_dirs=[second, first],
        universe_file=universe,
        output_dir="data/processed/news/weekly_counts",
        pilot_start_date="2025-04-05",
        pilot_end_date="2025-05-30",
        repo_root=tmp_path,
        write_files=False,
    )

    assert len(stock_week) == 24
    assert len(weekly_totals) == 8
    assert summary["validation_status"] == "passed"
    assert summary["expected_rows"] == 24
    assert summary["actual_rows"] == 24


def test_duplicate_or_overlapping_stock_day_rows_fail_validation(
    tmp_path: Path,
) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    chunk = _write_chunk(
        tmp_path / "chunk_a",
        rows=[
            {
                "date": "2025-04-05",
                "matched_ticker": "2330",
                "matched_rows": 1,
                "unique_urls": 1,
            },
            {
                "date": "2025-04-05",
                "matched_ticker": "2330",
                "matched_rows": 2,
                "unique_urls": 2,
            }
        ],
    )

    with pytest.raises(WeeklyCountAggregationError, match="Duplicate"):
        build_gdelt_weekly_counts(
            input_dirs=[chunk],
            universe_file=universe,
            output_dir="data/processed/news/weekly_counts",
            pilot_start_date="2025-04-05",
            pilot_end_date="2025-04-11",
            repo_root=tmp_path,
            write_files=False,
        )


def test_unknown_matched_ticker_fails_validation(tmp_path: Path) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    chunk = _write_chunk(
        tmp_path / "chunk_a",
        rows=[
            {
                "date": "2025-04-05",
                "matched_ticker": "9999",
                "matched_rows": 1,
                "unique_urls": 1,
            }
        ],
    )

    with pytest.raises(WeeklyCountAggregationError, match="outside the universe"):
        build_gdelt_weekly_counts(
            input_dirs=[chunk],
            universe_file=universe,
            output_dir="data/processed/news/weekly_counts",
            pilot_start_date="2025-04-05",
            pilot_end_date="2025-04-11",
            repo_root=tmp_path,
            write_files=False,
        )


@pytest.mark.parametrize(
    ("summary_overrides", "message"),
    [
        ({"completed": False}, "completed=true"),
        ({"files_failed": 1}, "files_failed=1"),
    ],
)
def test_bad_probe_summary_fails_validation(
    tmp_path: Path,
    summary_overrides: dict[str, object],
    message: str,
) -> None:
    universe = _write_universe(tmp_path / "data/processed/tej/top50.csv")
    chunk = _write_chunk(
        tmp_path / "chunk_a",
        rows=[
            {
                "date": "2025-04-05",
                "matched_ticker": "2330",
                "matched_rows": 1,
                "unique_urls": 1,
            }
        ],
        summary_overrides=summary_overrides,
    )

    with pytest.raises(WeeklyCountAggregationError, match=message):
        build_gdelt_weekly_counts(
            input_dirs=[chunk],
            universe_file=universe,
            output_dir="data/processed/news/weekly_counts",
            pilot_start_date="2025-04-05",
            pilot_end_date="2025-04-11",
            repo_root=tmp_path,
            write_files=False,
        )
