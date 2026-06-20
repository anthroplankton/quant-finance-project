from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from quant_finance_project.data.tej_market_data import (
    TejBuildConfig,
    TejDataError,
    TejValidationError,
    aggregate_weekly_market_cap_weights,
    build_tej_market_data,
    build_tej_output_paths,
    build_top50_universe,
    build_validation_summary,
    clean_company_metadata,
    clean_daily_market_panel,
    normalize_stock_code,
    parse_tej_dates,
    read_tej_csv,
)


def test_read_tej_csv_handles_cp950_semicolon_and_strips_whitespace(
    tmp_path: Path,
) -> None:
    raw_path = tmp_path / "synthetic_company.csv"
    raw_path.write_text(
        " 股票代號 ; 公司名稱 ; 產業名稱 \n"
        " 0001 測試甲 ; 測試公司甲 ; 電子業 \n",
        encoding="cp950",
    )

    frame = read_tej_csv(raw_path)

    assert list(frame.columns) == ["股票代號", "公司名稱", "產業名稱"]
    assert frame.loc[0, "股票代號"] == "0001 測試甲"
    assert frame.loc[0, "公司名稱"] == "測試公司甲"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1234.TWO", "1234"),
        ("1234.TW", "1234"),
        ("2330 台積電", "2330"),
        ("ABCD", "ABCD"),
    ],
)
def test_normalize_stock_code(raw: str, expected: str) -> None:
    assert normalize_stock_code(raw) == expected


def test_clean_company_metadata_accepts_documented_tejpro_headers() -> None:
    metadata = clean_company_metadata(_synthetic_tejpro_company_frame())
    row = metadata.loc[metadata["ticker"].eq("0001")].iloc[0]

    assert row["ticker"] == "0001"
    assert row["stock_id"] == "0001"
    assert row["exchange"] == "TSE"
    assert row["status"] == "上市"
    assert row["listing_date"].strftime("%Y-%m-%d") == "2020-01-02"
    assert row["tse_industry_code"] == "24"
    assert row["tse_industry"] == "電子工業"
    assert row["tej_industry"] == "半導體業"
    assert row["tej_subindustry"] == "晶圓製造"
    assert row["industry"] == "半導體業"
    assert row["official_chinese_name"] == "測試公司甲股份有限公司"
    assert row["chinese_short_name"] == "測試甲"
    assert row["official_english_name"] == "Synthetic Alpha Corporation"
    assert row["english_short_name"] == "Synthetic Alpha"
    assert row["paid_in_capital"] == pytest.approx(1_000_000_000)


def test_clean_daily_market_panel_computes_daily_and_weekly_ready_weights() -> None:
    raw_market = _synthetic_market_frame()

    daily_panel = clean_daily_market_panel(raw_market)

    daily_sums = daily_panel.groupby("date")["daily_market_cap_weight"].sum()
    assert daily_panel["ticker"].tolist() == ["0001", "0002"] * 3
    assert daily_sums.tolist() == pytest.approx([1.0, 1.0, 1.0])
    assert daily_panel.loc[0, "daily_market_cap_weight"] == pytest.approx(0.25)
    assert daily_panel.loc[0, "shares_outstanding"] == pytest.approx(100)
    assert daily_panel.loc[0, "market_cap"] == pytest.approx(1_000)
    assert daily_panel.loc[0, "volume"] == pytest.approx(10)
    assert daily_panel.loc[0, "traded_value"] == pytest.approx(100)
    assert daily_panel["market_cap_weight_from_tej"].isna().all()


@pytest.mark.parametrize(
    ("raw_date", "expected_date"),
    [
        ("1140401", "2025-04-01"),
        ("20250401", "2025-04-01"),
        ("114/04/01", "2025-04-01"),
    ],
)
def test_parse_tej_dates_handles_compact_and_separated_formats(
    raw_date: str,
    expected_date: str,
) -> None:
    parsed = parse_tej_dates(pd.Series([raw_date]))

    assert parsed.iloc[0].strftime("%Y-%m-%d") == expected_date


@pytest.mark.parametrize(
    "bad_date",
    [
        "not-a-date",
        "1140230",
        "20250230",
        "114/02/30",
    ],
)
def test_clean_daily_market_panel_rejects_invalid_nonempty_dates(
    bad_date: str,
) -> None:
    raw_market = _synthetic_market_frame()
    raw_market.loc[0, "年月日"] = bad_date

    with pytest.raises(TejDataError, match="Invalid TEJ date"):
        clean_daily_market_panel(raw_market)


def test_parse_tej_dates_reports_invalid_compact_dates_as_tej_data_error() -> None:
    with pytest.raises(TejDataError, match="1140230"):
        parse_tej_dates(
            pd.Series(["1140230"]),
            field_name="date",
            raise_on_invalid=True,
        )


def test_clean_daily_market_panel_rejects_missing_required_date() -> None:
    raw_market = _synthetic_market_frame()
    raw_market.loc[0, "年月日"] = ""

    with pytest.raises(TejDataError, match="Missing required TEJ date"):
        clean_daily_market_panel(raw_market)


def test_clean_daily_market_panel_rejects_missing_required_ticker() -> None:
    raw_market = _synthetic_market_frame()
    raw_market.loc[0, "股票代號"] = ""

    with pytest.raises(TejDataError, match="Missing required TEJ ticker"):
        clean_daily_market_panel(raw_market)


def test_clean_daily_market_panel_converts_unit_suffixed_tej_columns() -> None:
    daily_panel = clean_daily_market_panel(_synthetic_unit_suffixed_market_frame())
    row = daily_panel.loc[daily_panel["ticker"].eq("0001")].iloc[0]

    assert row["shares_outstanding"] == pytest.approx(1_500_000)
    assert row["market_cap"] == pytest.approx(3_000_000_000)
    assert row["volume"] == pytest.approx(250_000)
    assert row["traded_value"] == pytest.approx(75_000_000)
    assert row["market_cap_weight_from_tej"] == pytest.approx(0.025)

    summary = build_validation_summary(
        clean_company_metadata(_synthetic_company_frame()),
        daily_panel,
        aggregate_weekly_market_cap_weights(daily_panel),
        expected_ticker_count=2,
        expected_trading_date_count=1,
        expected_start_date="2025-04-01",
        expected_end_date="2025-04-01",
    )
    assert summary["failed_checks"] == []
    assert summary["canonical_units"]["market_cap"] == "TWD"
    assert summary["checks"]["market_cap_matches_close_times_shares"] is True
    assert summary["checks"]["shares_outstanding_is_positive"] is True


def test_default_config_output_filenames_use_default_project_dates(
    tmp_path: Path,
) -> None:
    config = TejBuildConfig(output_dir=tmp_path)

    output_paths = build_tej_output_paths(
        config.output_dir,
        constituent_as_of_date=config.constituent_as_of_date,
        panel_start_date=config.expected_start_date,
        panel_end_date=config.expected_end_date,
    )

    assert output_paths["company_metadata"].name == "company_metadata.csv"
    assert output_paths["top50_universe"].name == "top50_universe_20250331.csv"
    assert (
        output_paths["daily_market_panel"].name
        == "daily_market_panel_20250401_20260331.csv"
    )
    assert (
        output_paths["weekly_market_cap_weights"].name
        == "weekly_market_cap_weights_20250401_20260331.csv"
    )
    assert (
        output_paths["validation_summary"].name
        == "validation_summary_20250401_20260331.json"
    )


def test_build_tej_market_data_writes_outputs_from_synthetic_files(
    tmp_path: Path,
) -> None:
    company_raw = tmp_path / "company.csv"
    market_raw = tmp_path / "market.csv"
    output_dir = tmp_path / "processed"
    _write_semicolon_cp950(_synthetic_company_frame(), company_raw)
    _write_semicolon_cp950(_synthetic_market_frame(), market_raw)

    config = TejBuildConfig(
        company_raw_path=company_raw,
        market_raw_path=market_raw,
        output_dir=output_dir,
        expected_ticker_count=2,
        expected_trading_date_count=3,
        expected_start_date="2025-04-01",
        expected_end_date="2025-04-03",
        constituent_as_of_date="2025-03-30",
    )

    result = build_tej_market_data(config)

    summary = result["validation_summary"]
    assert summary["failed_checks"] == []
    assert summary["checks"]["daily_universe_weights_sum_to_one"] is True
    assert summary["checks"]["weekly_universe_weights_sum_to_one"] is True
    assert summary["checks"]["trading_date_count_matches_expected"] is True
    assert summary["checks"]["every_observed_date_has_expected_ticker_count"] is True
    assert summary["checks"]["every_ticker_has_expected_trading_date_count"] is True
    assert summary["panel_completeness"]["observed_trading_date_count"] == 3

    expected_files = [
        "company_metadata.csv",
        "daily_market_panel_20250401_20250403.csv",
        "top50_universe_20250330.csv",
        "weekly_market_cap_weights_20250401_20250403.csv",
        "validation_summary_20250401_20250403.json",
    ]
    for filename in expected_files:
        assert (output_dir / filename).exists()

    weekly = result["weekly_market_cap_weights"]
    assert weekly["weight_date"].dt.strftime("%Y-%m-%d").unique().tolist() == [
        "2025-04-03"
    ]

    assert not (output_dir / "top50_universe_20250331.csv").exists()
    assert not (
        output_dir / "weekly_market_cap_weights_20250401_20260331.csv"
    ).exists()
    assert not (output_dir / "validation_summary_20250401_20260331.json").exists()

    saved_summary = json.loads(
        (output_dir / "validation_summary_20250401_20250403.json").read_text()
    )
    assert saved_summary["failed_checks"] == []


def test_validation_summary_flags_incomplete_panels() -> None:
    daily_panel = clean_daily_market_panel(_synthetic_market_frame()).iloc[:-1]
    weekly_weights = daily_panel.copy()
    weekly_weights["week_end"] = pd.Timestamp("2025-04-04")
    weekly_weights["weight_date"] = weekly_weights["date"]
    weekly_weights = weekly_weights.rename(
        columns={"daily_market_cap_weight": "weekly_market_cap_weight"}
    )

    summary = build_validation_summary(
        _synthetic_company_frame(),
        daily_panel,
        weekly_weights[
            [
                "week_end",
                "weight_date",
                "stock_id",
                "ticker",
                "market_cap",
                "weekly_market_cap_weight",
            ]
        ],
        expected_ticker_count=2,
        expected_trading_date_count=3,
        expected_start_date="2025-04-01",
        expected_end_date="2025-04-03",
    )

    assert "each_trading_date_has_expected_rows" in summary["failed_checks"]
    assert "every_observed_date_has_expected_ticker_count" in summary["failed_checks"]
    assert "each_ticker_has_same_observation_count" in summary["failed_checks"]
    assert "every_ticker_has_expected_trading_date_count" in summary["failed_checks"]


def test_validation_summary_flags_missing_internal_trading_date() -> None:
    raw_market = _synthetic_market_frame()
    raw_market = raw_market.loc[raw_market["年月日"].ne("2025/04/02")]
    daily_panel = clean_daily_market_panel(raw_market)
    weekly_weights = aggregate_weekly_market_cap_weights(daily_panel)

    summary = build_validation_summary(
        clean_company_metadata(_synthetic_company_frame()),
        daily_panel,
        weekly_weights,
        expected_ticker_count=2,
        expected_trading_date_count=3,
        expected_start_date="2025-04-01",
        expected_end_date="2025-04-03",
    )

    assert "trading_date_count_matches_expected" in summary["failed_checks"]
    assert "every_ticker_has_expected_trading_date_count" in summary["failed_checks"]
    assert summary["panel_completeness"]["expected_trading_date_count"] == 3
    assert summary["panel_completeness"]["observed_trading_date_count"] == 2
    assert (
        summary["panel_completeness"][
            "every_observed_date_has_expected_ticker_count"
        ]
        is True
    )


def test_validation_summary_flags_market_cap_reconstruction_mismatch() -> None:
    daily_panel = clean_daily_market_panel(_synthetic_market_frame())
    daily_panel.loc[0, "market_cap"] = 2_000
    weekly_weights = aggregate_weekly_market_cap_weights(daily_panel)

    summary = build_validation_summary(
        clean_company_metadata(_synthetic_company_frame()),
        daily_panel,
        weekly_weights,
        expected_ticker_count=2,
        expected_trading_date_count=3,
        expected_start_date="2025-04-01",
        expected_end_date="2025-04-03",
    )

    assert "market_cap_matches_close_times_shares" in summary["failed_checks"]
    assert summary["checks"]["market_cap_is_positive"] is True


@pytest.mark.parametrize("bad_close", ["", "0"])
def test_validation_summary_flags_missing_or_zero_close(bad_close: str) -> None:
    raw_market = _synthetic_market_frame()
    raw_market.loc[0, "收盤價"] = bad_close
    daily_panel = clean_daily_market_panel(raw_market)
    weekly_weights = aggregate_weekly_market_cap_weights(daily_panel)

    summary = build_validation_summary(
        clean_company_metadata(_synthetic_company_frame()),
        daily_panel,
        weekly_weights,
        expected_ticker_count=2,
        expected_trading_date_count=3,
        expected_start_date="2025-04-01",
        expected_end_date="2025-04-03",
    )

    assert "close_is_present_and_positive" in summary["failed_checks"]
    assert summary["checks"]["market_cap_is_positive"] is True


@pytest.mark.parametrize(
    ("column", "bad_value", "failed_check"),
    [
        ("市值", "", "market_cap_is_positive"),
        ("市值", "0", "market_cap_is_positive"),
        ("流通在外股數", "", "shares_outstanding_is_positive"),
        ("流通在外股數", "0", "shares_outstanding_is_positive"),
    ],
)
def test_validation_summary_flags_missing_or_zero_market_cap_or_shares(
    column: str,
    bad_value: str,
    failed_check: str,
) -> None:
    raw_market = _synthetic_market_frame()
    raw_market.loc[0, column] = bad_value
    daily_panel = clean_daily_market_panel(raw_market)
    weekly_weights = aggregate_weekly_market_cap_weights(daily_panel)

    summary = build_validation_summary(
        clean_company_metadata(_synthetic_company_frame()),
        daily_panel,
        weekly_weights,
        expected_ticker_count=2,
        expected_trading_date_count=3,
        expected_start_date="2025-04-01",
        expected_end_date="2025-04-03",
    )

    assert failed_check in summary["failed_checks"]


def test_build_tej_market_data_raises_after_writing_failed_summary(
    tmp_path: Path,
) -> None:
    company_raw = tmp_path / "company.csv"
    market_raw = tmp_path / "market.csv"
    output_dir = tmp_path / "processed"
    _write_semicolon_cp950(_synthetic_company_frame(), company_raw)
    _write_semicolon_cp950(_synthetic_market_frame().iloc[:-1], market_raw)

    config = TejBuildConfig(
        company_raw_path=company_raw,
        market_raw_path=market_raw,
        output_dir=output_dir,
        expected_ticker_count=2,
        expected_trading_date_count=3,
        expected_start_date="2025-04-01",
        expected_end_date="2025-04-03",
    )

    with pytest.raises(TejValidationError):
        build_tej_market_data(config)

    summary = json.loads(
        (output_dir / "validation_summary_20250401_20250403.json").read_text()
    )
    assert "each_trading_date_has_expected_rows" in summary["failed_checks"]


def test_missing_metadata_ticker_fails_validation_with_auditable_summary(
    tmp_path: Path,
) -> None:
    company_raw = tmp_path / "company.csv"
    market_raw = tmp_path / "market.csv"
    output_dir = tmp_path / "processed"
    _write_semicolon_cp950(_synthetic_company_frame().iloc[:1], company_raw)
    _write_semicolon_cp950(_synthetic_market_frame(), market_raw)

    config = TejBuildConfig(
        company_raw_path=company_raw,
        market_raw_path=market_raw,
        output_dir=output_dir,
        expected_ticker_count=2,
        expected_trading_date_count=3,
        expected_start_date="2025-04-01",
        expected_end_date="2025-04-03",
    )

    with pytest.raises(TejValidationError, match="0002"):
        build_tej_market_data(config)

    summary = json.loads(
        (output_dir / "validation_summary_20250401_20250403.json").read_text()
    )
    assert "market_panel_tickers_have_company_metadata" in summary["failed_checks"]
    assert summary["metadata_coverage"]["missing_tickers"] == ["0002"]
    assert summary["counts"]["missing_metadata_ticker_count"] == 1


def test_build_top50_universe_is_strict_about_missing_metadata() -> None:
    daily_panel = clean_daily_market_panel(_synthetic_market_frame())
    company_metadata = clean_company_metadata(_synthetic_company_frame().iloc[:1])

    with pytest.raises(TejValidationError, match="0002"):
        build_top50_universe(company_metadata, daily_panel)


def _write_semicolon_cp950(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, sep=";", index=False, encoding="cp950")


def _synthetic_company_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "股票代號": ["0001", "0002"],
            "公司名稱": ["測試公司甲", "測試公司乙"],
            "英文名稱": ["Synthetic Alpha", "Synthetic Beta"],
            "產業名稱": ["電子業", "金融業"],
        }
    )


def _synthetic_tejpro_company_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "證券代碼": ["9999 非偏好代碼", "8888 非偏好代碼"],
            "上市別": ["TSE", "TSE"],
            "目前狀態": ["上市", "上市"],
            "最近上市日": ["2020/01/02", "2021/03/04"],
            "證期會代碼": ["0001", "0002"],
            "TSE 產業別": ["24", "17"],
            "TSE產業名": ["電子工業", "金融保險業"],
            "TEJ產業名": ["半導體業", "金融業"],
            "TEJ子產業名": ["晶圓製造", "銀行"],
            "公司中文全稱": ["測試公司甲股份有限公司", "測試公司乙股份有限公司"],
            "公司英文全稱": [
                "Synthetic Alpha Corporation",
                "Synthetic Beta Corporation",
            ],
            "公司中文簡稱": ["測試甲", "測試乙"],
            "公司英文簡稱": ["Synthetic Alpha", "Synthetic Beta"],
            "實收資本額(元)": ["1,000,000,000", "2,000,000,000"],
        }
    )


def _synthetic_market_frame() -> pd.DataFrame:
    rows = []
    for date in ("2025/04/01", "2025/04/02", "2025/04/03"):
        rows.extend(
            [
                {
                    "年月日": date,
                    "股票代號": "0001 測試甲",
                    "收盤價": "10",
                    "流通在外股數": "100",
                    "市值": "1,000",
                    "成交量": "10",
                    "成交值": "100",
                },
                {
                    "年月日": date,
                    "股票代號": "0002 測試乙",
                    "收盤價": "30",
                    "流通在外股數": "100",
                    "市值": "3,000",
                    "成交量": "30",
                    "成交值": "900",
                },
            ]
        )
    return pd.DataFrame(rows)


def _synthetic_unit_suffixed_market_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "年月日": "2025/04/01",
                "股票代號": "0001 測試甲",
                "收盤價": "2,000",
                "流通在外股數(千股)": "1,500",
                "市值(百萬元)": "3,000",
                "成交量(千股)": "250",
                "成交值(千元)": "75,000",
                "市值比重％": "2.5",
            },
            {
                "年月日": "2025/04/01",
                "股票代號": "0002 測試乙",
                "收盤價": "1,000",
                "流通在外股數(千股)": "117,000",
                "市值(百萬元)": "117,000",
                "成交量(千股)": "1,000",
                "成交值(千元)": "1,000,000",
                "市值比重％": "97.5",
            },
        ]
    )
