from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from quant_finance_project.hype.index import HypeIndexError, build_hype_indices


def _input_rows() -> list[dict[str, str | int | float]]:
    return [
        {
            "stock_id": "AAA",
            "ticker": "AAA",
            "official_chinese_name": "甲公司",
            "official_english_name": "Alpha Co",
            "industry": "Tech",
            "week_index": 1,
            "week_start": "2025-04-05",
            "week_end": "2025-04-11",
            "weight_date": "2025-04-11",
            "news_count_unique_urls": 2,
            "matched_rows": 2,
            "active_news_days": 1,
            "weekly_total_news_count_unique_urls": 3,
            "weekly_market_cap_weight": 0.5,
        },
        {
            "stock_id": "BBB",
            "ticker": "BBB",
            "official_chinese_name": "乙公司",
            "official_english_name": "Beta Co",
            "industry": "Finance",
            "week_index": 1,
            "week_start": "2025-04-05",
            "week_end": "2025-04-11",
            "weight_date": "2025-04-11",
            "news_count_unique_urls": 1,
            "matched_rows": 1,
            "active_news_days": 1,
            "weekly_total_news_count_unique_urls": 3,
            "weekly_market_cap_weight": 0.25,
        },
        {
            "stock_id": "CCC",
            "ticker": "CCC",
            "official_chinese_name": "丙公司",
            "official_english_name": "Gamma Co",
            "industry": "Materials",
            "week_index": 1,
            "week_start": "2025-04-05",
            "week_end": "2025-04-11",
            "weight_date": "2025-04-11",
            "news_count_unique_urls": 0,
            "matched_rows": 0,
            "active_news_days": 0,
            "weekly_total_news_count_unique_urls": 3,
            "weekly_market_cap_weight": 0.25,
        },
        {
            "stock_id": "AAA",
            "ticker": "AAA",
            "official_chinese_name": "甲公司",
            "official_english_name": "Alpha Co",
            "industry": "Tech",
            "week_index": 2,
            "week_start": "2025-04-12",
            "week_end": "2025-04-18",
            "weight_date": "2025-04-18",
            "news_count_unique_urls": 0,
            "matched_rows": 0,
            "active_news_days": 0,
            "weekly_total_news_count_unique_urls": 4,
            "weekly_market_cap_weight": 0.25,
        },
        {
            "stock_id": "BBB",
            "ticker": "BBB",
            "official_chinese_name": "乙公司",
            "official_english_name": "Beta Co",
            "industry": "Finance",
            "week_index": 2,
            "week_start": "2025-04-12",
            "week_end": "2025-04-18",
            "weight_date": "2025-04-18",
            "news_count_unique_urls": 2,
            "matched_rows": 2,
            "active_news_days": 1,
            "weekly_total_news_count_unique_urls": 4,
            "weekly_market_cap_weight": 0.25,
        },
        {
            "stock_id": "CCC",
            "ticker": "CCC",
            "official_chinese_name": "丙公司",
            "official_english_name": "Gamma Co",
            "industry": "Materials",
            "week_index": 2,
            "week_start": "2025-04-12",
            "week_end": "2025-04-18",
            "weight_date": "2025-04-18",
            "news_count_unique_urls": 2,
            "matched_rows": 2,
            "active_news_days": 1,
            "weekly_total_news_count_unique_urls": 4,
            "weekly_market_cap_weight": 0.5,
        },
    ]


def _write_input_panel(
    tmp_path: Path,
    rows: list[dict[str, object]] | None = None,
) -> Path:
    path = tmp_path / "data/processed/hype_index/input_panel.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows if rows is not None else _input_rows()).to_csv(path, index=False)
    return path


def _build(tmp_path: Path, *, rows=None, write_files=False):
    input_panel = _write_input_panel(tmp_path, rows)
    return build_hype_indices(
        input_panel_file=input_panel,
        output_dir="data/processed/hype_index/test_indices",
        pilot_start_date="2025-04-05",
        pilot_end_date="2025-04-18",
        repo_root=tmp_path,
        write_files=write_files,
    )


def _run_build_hype_indices_main(argv: list[str]) -> int:
    script_path = Path(__file__).resolve().parents[1] / "scripts/build_hype_indices.py"
    spec = importlib.util.spec_from_file_location(
        "build_hype_indices_script",
        script_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return int(module.main(argv))


def test_valid_hype_indices_match_hand_computed_values(tmp_path: Path) -> None:
    panel, weekly, stock, summary, paths = _build(tmp_path, write_files=True)

    assert paths is not None
    assert len(panel) == 6
    assert len(weekly) == 2
    assert len(stock) == 3
    assert summary["validation_status"] == "passed"
    assert summary["hype_index_computed"] is True
    assert summary["market_cap_adjusted_hype_computed"] is True

    aaa_week_1 = panel.loc[
        panel["ticker"].eq("AAA") & panel["week_index"].eq(1)
    ].iloc[0]
    bbb_week_1 = panel.loc[
        panel["ticker"].eq("BBB") & panel["week_index"].eq(1)
    ].iloc[0]
    ccc_week_1 = panel.loc[
        panel["ticker"].eq("CCC") & panel["week_index"].eq(1)
    ].iloc[0]
    bbb_week_2 = panel.loc[
        panel["ticker"].eq("BBB") & panel["week_index"].eq(2)
    ].iloc[0]

    assert aaa_week_1["raw_hype"] == pytest.approx(2 / 3)
    assert aaa_week_1["market_cap_adjusted_hype"] == pytest.approx((2 / 3) / 0.5)
    assert bbb_week_1["raw_hype"] == pytest.approx(1 / 3)
    assert bbb_week_1["market_cap_adjusted_hype"] == pytest.approx((1 / 3) / 0.25)
    assert ccc_week_1["raw_hype"] == 0
    assert ccc_week_1["market_cap_adjusted_hype"] == 0
    assert bbb_week_2["raw_hype"] == pytest.approx(0.5)
    assert bbb_week_2["market_cap_adjusted_hype"] == pytest.approx(2.0)


def test_invalid_pilot_start_date_raises_hype_index_error(tmp_path: Path) -> None:
    input_panel = _write_input_panel(tmp_path)

    with pytest.raises(HypeIndexError, match="Invalid pilot window"):
        build_hype_indices(
            input_panel_file=input_panel,
            output_dir="data/processed/hype_index/test_indices",
            pilot_start_date="2025-04-06",
            pilot_end_date="2025-04-18",
            repo_root=tmp_path,
            write_files=False,
        )


def test_invalid_pilot_end_date_raises_hype_index_error(tmp_path: Path) -> None:
    input_panel = _write_input_panel(tmp_path)

    with pytest.raises(HypeIndexError, match="Invalid pilot window"):
        build_hype_indices(
            input_panel_file=input_panel,
            output_dir="data/processed/hype_index/test_indices",
            pilot_start_date="2025-04-05",
            pilot_end_date="2025-04-19",
            repo_root=tmp_path,
            write_files=False,
        )


def test_cli_invalid_pilot_window_returns_error_without_traceback(capsys) -> None:
    exit_code = _run_build_hype_indices_main(
        [
            "--pilot-start-date",
            "2025-04-06",
            "--pilot-end-date",
            "2025-05-30",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Error:" in captured.err
    assert "Invalid pilot window" in captured.err
    assert "Traceback" not in captured.err


def test_zero_stock_news_has_zero_hype_values(tmp_path: Path) -> None:
    panel, _, _, _, _ = _build(tmp_path)
    zero_news = panel.loc[panel["news_count_unique_urls"].eq(0)]

    assert not zero_news.empty
    assert zero_news["raw_hype"].eq(0).all()
    assert zero_news["market_cap_adjusted_hype"].eq(0).all()


def test_weekly_raw_hype_sums_to_one(tmp_path: Path) -> None:
    panel, weekly, _, _, _ = _build(tmp_path)

    assert panel.groupby("week_end")["raw_hype"].sum().tolist() == pytest.approx(
        [1.0, 1.0]
    )
    assert weekly["raw_hype_sum"].tolist() == pytest.approx([1.0, 1.0])


def test_weekly_market_cap_weights_must_sum_to_one(tmp_path: Path) -> None:
    rows = _input_rows()
    rows[0] = {**rows[0], "weekly_market_cap_weight": 0.6}

    with pytest.raises(HypeIndexError, match="sum to 1"):
        _build(tmp_path, rows=rows)


def test_weekly_total_news_count_must_match_news_sum(tmp_path: Path) -> None:
    rows = [
        {**row, "weekly_total_news_count_unique_urls": 99}
        if row["week_end"] == "2025-04-11"
        else row
        for row in _input_rows()
    ]

    with pytest.raises(HypeIndexError, match="conflicts"):
        _build(tmp_path, rows=rows)


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("news_count_unique_urls", "1.9"),
        ("matched_rows", 1.5),
        ("active_news_days", "1.1"),
        ("weekly_total_news_count_unique_urls", "3.5"),
    ],
)
def test_fractional_count_fields_fail_before_integer_casting(
    tmp_path: Path,
    field: str,
    bad_value: str | float,
) -> None:
    rows = _input_rows()
    rows[0] = {**rows[0], field: bad_value}

    with pytest.raises(HypeIndexError, match="non-integral"):
        _build(tmp_path, rows=rows)


def test_integer_valued_count_strings_pass_validation(tmp_path: Path) -> None:
    rows = []
    for row in _input_rows():
        converted = row.copy()
        converted["news_count_unique_urls"] = f"{row['news_count_unique_urls']}.0"
        converted["matched_rows"] = str(row["matched_rows"])
        converted["active_news_days"] = f"{row['active_news_days']}.0"
        converted["weekly_total_news_count_unique_urls"] = str(
            row["weekly_total_news_count_unique_urls"]
        )
        rows.append(converted)

    panel, _, _, summary, _ = _build(tmp_path, rows=rows)

    assert summary["validation_status"] == "passed"
    assert panel["news_count_unique_urls"].tolist() == [2, 0, 1, 2, 0, 2]


@pytest.mark.parametrize("bad_value", ["NaN", "inf", "-inf", "", "not-a-number"])
def test_malformed_count_values_fail_validation(
    tmp_path: Path,
    bad_value: str,
) -> None:
    rows = _input_rows()
    rows[0] = {**rows[0], "news_count_unique_urls": bad_value}

    with pytest.raises(HypeIndexError):
        _build(tmp_path, rows=rows)


def test_week_with_zero_total_news_fails_validation(tmp_path: Path) -> None:
    rows = [
        {
            **row,
            "news_count_unique_urls": 0,
            "matched_rows": 0,
            "active_news_days": 0,
            "weekly_total_news_count_unique_urls": 0,
        }
        if row["week_end"] == "2025-04-18"
        else row
        for row in _input_rows()
    ]

    with pytest.raises(HypeIndexError, match="positive"):
        _build(tmp_path, rows=rows)


@pytest.mark.parametrize("bad_weight", [0, -0.1])
def test_zero_or_negative_market_cap_weight_fails_validation(
    tmp_path: Path,
    bad_weight: float,
) -> None:
    rows = _input_rows()
    rows[0] = {**rows[0], "weekly_market_cap_weight": bad_weight}

    with pytest.raises(HypeIndexError, match="nonpositive"):
        _build(tmp_path, rows=rows)


def test_duplicate_ticker_week_rows_fail_validation(tmp_path: Path) -> None:
    rows = [*_input_rows(), _input_rows()[0].copy()]

    with pytest.raises(HypeIndexError, match="duplicate ticker-week"):
        _build(tmp_path, rows=rows)


def test_missing_ticker_week_rows_fail_validation(tmp_path: Path) -> None:
    rows = [
        row
        for row in _input_rows()
        if not (row["ticker"] == "CCC" and row["week_end"] == "2025-04-18")
    ]

    with pytest.raises(HypeIndexError, match="5 rows; expected 6"):
        _build(tmp_path, rows=rows)


def test_no_nan_or_infinite_hype_values_are_produced(tmp_path: Path) -> None:
    panel, _, _, _, _ = _build(tmp_path)

    assert panel["raw_hype"].map(lambda value: value == value).all()
    assert panel["market_cap_adjusted_hype"].map(lambda value: value == value).all()
    assert panel["raw_hype"].map(lambda value: abs(value) < float("inf")).all()
    assert panel["market_cap_adjusted_hype"].map(
        lambda value: abs(value) < float("inf")
    ).all()


def test_market_cap_adjusted_hype_is_not_normalized_to_one(tmp_path: Path) -> None:
    panel, _, _, _, _ = _build(tmp_path)

    adjusted_sums = panel.groupby("week_end")["market_cap_adjusted_hype"].sum()
    assert adjusted_sums.tolist() != pytest.approx([1.0, 1.0])
    assert adjusted_sums.tolist() == pytest.approx([8 / 3, 3.0])


def test_outputs_do_not_create_figure_or_notebook_artifacts(tmp_path: Path) -> None:
    _, _, _, _, paths = _build(tmp_path, write_files=True)

    assert paths is not None
    output_files = [path for path in paths.panel.parent.iterdir() if path.is_file()]
    assert output_files
    assert not any(path.suffix in {".png", ".jpg", ".jpeg", ".svg"} for path in output_files)
    assert not any(path.suffix == ".ipynb" for path in output_files)
