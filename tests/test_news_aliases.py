from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from quant_finance_project.news.aliases import (
    ALIAS_OUTPUT_COLUMNS,
    GDELT_PROFILE_EXPANDED_REVIEWED,
    apply_gdelt_profile,
    alias_review_table,
    build_alias_tables,
    generate_alias_candidates,
    write_alias_outputs,
)


def _synthetic_universe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "stock_id": "2330",
                "ticker": "2330",
                "official_chinese_name": "台灣積體電路製造股份有限公司",
                "official_english_name": "Taiwan Semiconductor Manufacturing Co Ltd",
            },
            {
                "stock_id": "1216",
                "ticker": "1216",
                "official_chinese_name": "統一企業股份有限公司",
                "official_english_name": "Uni-President Enterprises Corp",
            },
            {
                "stock_id": "2603",
                "ticker": "2603",
                "official_chinese_name": "長榮海運股份有限公司",
                "official_english_name": "Evergreen Marine Corp Taiwan Ltd",
            },
        ]
    )


def _synthetic_company_metadata() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "stock_id": "2330",
                "ticker": "2330",
                "official_chinese_name": "台灣積體電路製造股份有限公司",
                "chinese_short_name": "台積電",
                "official_english_name": "Taiwan Semiconductor Manufacturing Co Ltd",
                "english_short_name": "TSMC",
            },
            {
                "stock_id": "1216",
                "ticker": "1216",
                "official_chinese_name": "統一企業股份有限公司",
                "chinese_short_name": "統一",
                "official_english_name": "Uni-President Enterprises Corp",
                "english_short_name": "Uni-President",
            },
            {
                "stock_id": "2603",
                "ticker": "2603",
                "official_chinese_name": "長榮海運股份有限公司",
                "chinese_short_name": "長榮",
                "official_english_name": "Evergreen Marine Corp Taiwan Ltd",
                "english_short_name": "EMC",
            },
        ]
    )


def _synthetic_profile_universe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "stock_id": "2330",
                "ticker": "2330",
                "official_chinese_name": "台灣積體電路製造股份有限公司",
                "official_english_name": "Taiwan Semiconductor Manufacturing Co Ltd",
            },
            {
                "stock_id": "2317",
                "ticker": "2317",
                "official_chinese_name": "鴻海精密工業股份有限公司",
                "official_english_name": "Hon Hai Precision Industry Co Ltd",
            },
            {
                "stock_id": "2454",
                "ticker": "2454",
                "official_chinese_name": "聯發科技股份有限公司",
                "official_english_name": "MediaTek Inc",
            },
            {
                "stock_id": "1216",
                "ticker": "1216",
                "official_chinese_name": "統一企業股份有限公司",
                "official_english_name": "Uni-President Enterprises Corp",
            },
            {
                "stock_id": "2327",
                "ticker": "2327",
                "official_chinese_name": "國巨股份有限公司",
                "official_english_name": "Yageo Corp",
            },
            {
                "stock_id": "2308",
                "ticker": "2308",
                "official_chinese_name": "台達電子工業股份有限公司",
                "official_english_name": "Delta Electronics Inc",
            },
            {
                "stock_id": "9999",
                "ticker": "9999",
                "official_chinese_name": "測試鋼鐵股份有限公司",
                "official_english_name": "Synthetic Steel Corp",
            },
        ]
    )


def _synthetic_profile_metadata() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "stock_id": "2330",
                "ticker": "2330",
                "official_chinese_name": "台灣積體電路製造股份有限公司",
                "chinese_short_name": "台積電",
                "official_english_name": "Taiwan Semiconductor Manufacturing Co Ltd",
                "english_short_name": "TSMC",
            },
            {
                "stock_id": "2317",
                "ticker": "2317",
                "official_chinese_name": "鴻海精密工業股份有限公司",
                "chinese_short_name": "鴻海",
                "official_english_name": "Hon Hai Precision Industry Co Ltd",
                "english_short_name": "Foxconn",
            },
            {
                "stock_id": "2454",
                "ticker": "2454",
                "official_chinese_name": "聯發科技股份有限公司",
                "chinese_short_name": "聯發科",
                "official_english_name": "MediaTek Inc",
                "english_short_name": "MediaTek",
            },
            {
                "stock_id": "1216",
                "ticker": "1216",
                "official_chinese_name": "統一企業股份有限公司",
                "chinese_short_name": "統一",
                "official_english_name": "Uni-President Enterprises Corp",
                "english_short_name": "Uni-President",
            },
            {
                "stock_id": "2327",
                "ticker": "2327",
                "official_chinese_name": "國巨股份有限公司",
                "chinese_short_name": "國巨*",
                "official_english_name": "Yageo Corp",
                "english_short_name": "Yageo",
            },
            {
                "stock_id": "2308",
                "ticker": "2308",
                "official_chinese_name": "台達電子工業股份有限公司",
                "chinese_short_name": "台達電",
                "official_english_name": "Delta Electronics Inc",
                "english_short_name": "DELTA",
            },
            {
                "stock_id": "9999",
                "ticker": "9999",
                "official_chinese_name": "測試鋼鐵股份有限公司",
                "chinese_short_name": "測試鋼",
                "official_english_name": "Synthetic Steel Corp",
                "english_short_name": "CSC",
            },
        ]
    )


def _row_by_alias(frame: pd.DataFrame, alias: str) -> pd.Series:
    rows = frame.loc[frame["alias"] == alias]
    assert len(rows) == 1
    return rows.iloc[0]


def _profile_rows_for_short_aliases(aliases: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": f"9{index:03d}",
                "stock_id": f"9{index:03d}",
                "alias": alias,
                "alias_type": "chinese_short_name",
                "language": "zh",
                "source_column": "chinese_short_name",
                "is_ambiguous": False,
                "use_for_matching": True,
                "review_reason": "",
                "profile": "candidate",
                "notes": "Short alias; review false-positive risk before production matching.",
            }
            for index, alias in enumerate(aliases)
        ],
        columns=ALIAS_OUTPUT_COLUMNS,
    )


def _profile_rows_for_english_short_aliases(aliases: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": f"8{index:03d}",
                "stock_id": f"8{index:03d}",
                "alias": alias,
                "alias_type": "english_short_name",
                "language": "en",
                "source_column": "english_short_name",
                "is_ambiguous": False,
                "use_for_matching": True,
                "review_reason": "",
                "profile": "candidate",
                "notes": "Short alias; review false-positive risk before production matching.",
            }
            for index, alias in enumerate(aliases)
        ],
        columns=ALIAS_OUTPUT_COLUMNS,
    )


def test_generate_alias_candidates_from_synthetic_metadata() -> None:
    aliases = generate_alias_candidates(
        _synthetic_universe(),
        _synthetic_company_metadata(),
    )

    assert list(aliases.columns) == ALIAS_OUTPUT_COLUMNS
    tsmc = _row_by_alias(aliases, "Taiwan Semiconductor Manufacturing Co Ltd")
    assert tsmc["ticker"] == "2330"
    assert tsmc["alias_type"] == "official_english_name"
    assert tsmc["language"] == "en"
    assert tsmc["source_column"] == "official_english_name"
    assert tsmc["profile"] == "candidate"
    assert not bool(tsmc["is_ambiguous"])
    assert bool(tsmc["use_for_matching"])


def test_duplicate_aliases_are_removed_per_ticker() -> None:
    metadata = _synthetic_company_metadata()
    metadata.loc[0, "chinese_short_name"] = "台灣積體電路製造股份有限公司"

    aliases = generate_alias_candidates(_synthetic_universe(), metadata)

    duplicate_rows = aliases.loc[
        (aliases["ticker"] == "2330")
        & (aliases["alias"] == "台灣積體電路製造股份有限公司")
    ]
    assert len(duplicate_rows) == 1
    assert duplicate_rows.iloc[0]["source_column"] == "official_chinese_name"


def test_ambiguous_aliases_are_flagged_and_disabled_by_default() -> None:
    aliases = generate_alias_candidates(
        _synthetic_universe(),
        _synthetic_company_metadata(),
    )

    ambiguous = _row_by_alias(aliases, "統一")
    assert bool(ambiguous["is_ambiguous"])
    assert not bool(ambiguous["use_for_matching"])
    assert "known broad Taiwan market alias" in ambiguous["review_reason"]

    short_english = _row_by_alias(aliases, "EMC")
    assert bool(short_english["is_ambiguous"])
    assert not bool(short_english["use_for_matching"])
    assert "very short English short alias" in short_english["review_reason"]


def test_ambiguous_aliases_can_be_explicitly_enabled_but_remain_flagged() -> None:
    aliases = generate_alias_candidates(
        _synthetic_universe(),
        _synthetic_company_metadata(),
        allow_ambiguous_matching=True,
    )

    ambiguous = _row_by_alias(aliases, "統一")
    assert bool(ambiguous["is_ambiguous"])
    assert bool(ambiguous["use_for_matching"])
    assert "explicitly enabled" in ambiguous["notes"]


def test_shared_alias_across_tickers_requires_review() -> None:
    metadata = _synthetic_company_metadata()
    metadata.loc[1, "english_short_name"] = "Evergreen"
    metadata.loc[2, "english_short_name"] = "Evergreen"

    aliases = generate_alias_candidates(_synthetic_universe(), metadata)
    shared = aliases.loc[aliases["alias"] == "Evergreen"]

    assert len(shared) == 2
    assert shared["is_ambiguous"].tolist() == [True, True]
    assert shared["use_for_matching"].tolist() == [False, False]
    assert all("alias shared by tickers" in reason for reason in shared["review_reason"])


def test_build_alias_tables_and_write_outputs(tmp_path: Path) -> None:
    candidates, review, summary = build_alias_tables(
        _synthetic_universe(),
        _synthetic_company_metadata(),
    )
    paths = write_alias_outputs(
        candidates=candidates,
        review=review,
        summary=summary,
        output_dir=tmp_path / "aliases",
    )

    assert paths["candidates"].exists()
    assert paths["review"].exists()
    assert paths["summary"].exists()
    assert len(alias_review_table(candidates)) == len(review)
    written_summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    assert written_summary["tickers"] == 3
    assert written_summary["ambiguous_aliases"] >= 2


def test_expanded_reviewed_profile_disables_pure_ticker_aliases() -> None:
    candidates = generate_alias_candidates(
        _synthetic_profile_universe(),
        _synthetic_profile_metadata(),
    )

    profile = apply_gdelt_profile(candidates, profile=GDELT_PROFILE_EXPANDED_REVIEWED)
    tickers = profile.loc[profile["alias"].isin(["2330", "2454", "2317"])]

    assert set(tickers["alias"]) == {"2330", "2454", "2317"}
    assert set(tickers["profile"]) == {GDELT_PROFILE_EXPANDED_REVIEWED}
    assert set(tickers["alias_type"]) == {"ticker"}
    assert tickers["is_ambiguous"].tolist() == [True] * len(tickers)
    assert tickers["use_for_matching"].tolist() == [False] * len(tickers)
    assert all("pure ticker disabled" in reason for reason in tickers["review_reason"])


def test_expanded_reviewed_profile_keeps_high_risk_alias_disabled() -> None:
    candidates = generate_alias_candidates(
        _synthetic_profile_universe(),
        _synthetic_profile_metadata(),
    )

    profile = apply_gdelt_profile(candidates, profile=GDELT_PROFILE_EXPANDED_REVIEWED)
    high_risk = _row_by_alias(profile, "統一")

    assert bool(high_risk["is_ambiguous"])
    assert not bool(high_risk["use_for_matching"])
    assert "disabled by GDELT high-risk alias policy" in high_risk["review_reason"]


def test_expanded_reviewed_profile_enables_high_confidence_short_aliases() -> None:
    candidates = generate_alias_candidates(
        _synthetic_profile_universe(),
        _synthetic_profile_metadata(),
    )

    profile = apply_gdelt_profile(candidates, profile=GDELT_PROFILE_EXPANDED_REVIEWED)
    tsmc_chinese = _row_by_alias(profile, "台積電")
    tsmc_brand = _row_by_alias(profile, "TSMC")
    chinese_short = _row_by_alias(profile, "鴻海")
    english_brand = _row_by_alias(profile, "Foxconn")
    mediatek_chinese = _row_by_alias(profile, "聯發科")
    mediatek_brand = _row_by_alias(profile, "MediaTek")
    delta_chinese = _row_by_alias(profile, "台達電")

    assert bool(tsmc_chinese["use_for_matching"])
    assert "high-confidence Chinese short alias" in tsmc_chinese["notes"]
    assert bool(tsmc_brand["use_for_matching"])
    assert "high-confidence English brand alias" in tsmc_brand["notes"]
    assert bool(chinese_short["use_for_matching"])
    assert "high-confidence Chinese short alias" in chinese_short["notes"]
    assert bool(english_brand["use_for_matching"])
    assert "high-confidence English brand alias" in english_brand["notes"]
    assert bool(mediatek_chinese["use_for_matching"])
    assert "high-confidence Chinese short alias" in mediatek_chinese["notes"]
    assert bool(mediatek_brand["use_for_matching"])
    assert "high-confidence English brand alias" in mediatek_brand["notes"]
    assert bool(delta_chinese["use_for_matching"])
    assert "high-confidence Chinese short alias" in delta_chinese["notes"]


def test_expanded_reviewed_profile_disables_delta_regression_alias() -> None:
    candidates = generate_alias_candidates(
        _synthetic_profile_universe(),
        _synthetic_profile_metadata(),
    )

    profile = apply_gdelt_profile(candidates, profile=GDELT_PROFILE_EXPANDED_REVIEWED)
    delta = _row_by_alias(profile, "DELTA")

    assert delta["alias_type"] == "english_short_name"
    assert bool(delta["is_ambiguous"])
    assert not bool(delta["use_for_matching"])
    assert "short alias not in GDELT curated allowlist" in delta["review_reason"]


def test_expanded_reviewed_profile_disables_generic_english_acronym() -> None:
    candidates = generate_alias_candidates(
        _synthetic_profile_universe(),
        _synthetic_profile_metadata(),
    )

    profile = apply_gdelt_profile(candidates, profile=GDELT_PROFILE_EXPANDED_REVIEWED)
    acronym = _row_by_alias(profile, "CSC")

    assert acronym["alias_type"] == "english_short_name"
    assert bool(acronym["is_ambiguous"])
    assert not bool(acronym["use_for_matching"])
    assert "very short English short alias" in acronym["review_reason"]
    assert "short alias not in GDELT curated allowlist" in acronym["review_reason"]


def test_expanded_reviewed_profile_keeps_generic_english_aliases_disabled() -> None:
    candidates = _profile_rows_for_english_short_aliases(["DELTA", "FIRST", "CSC"])

    profile = apply_gdelt_profile(candidates, profile=GDELT_PROFILE_EXPANDED_REVIEWED)

    assert set(profile["alias"]) == {"DELTA", "FIRST", "CSC"}
    assert profile["use_for_matching"].tolist() == [False] * len(profile)
    assert all(
        "short alias not in GDELT curated allowlist" in reason
        for reason in profile["review_reason"]
    )


def test_expanded_reviewed_profile_disables_unlisted_short_aliases() -> None:
    candidates = generate_alias_candidates(
        _synthetic_profile_universe(),
        _synthetic_profile_metadata(),
    )

    profile = apply_gdelt_profile(candidates, profile=GDELT_PROFILE_EXPANDED_REVIEWED)
    chinese_short = _row_by_alias(profile, "測試鋼")
    english_short = _row_by_alias(profile, "Uni-President")

    assert not bool(chinese_short["use_for_matching"])
    assert "short alias not in GDELT curated allowlist" in chinese_short["review_reason"]
    assert not bool(english_short["use_for_matching"])
    assert "short alias not in GDELT curated allowlist" in english_short["review_reason"]


def test_expanded_reviewed_profile_keeps_high_risk_chinese_aliases_disabled() -> None:
    candidates = _profile_rows_for_short_aliases(
        ["統一", "長榮", "台塑", "國泰", "富邦", "第一", "合庫", "台新", "南亞"]
    )

    profile = apply_gdelt_profile(candidates, profile=GDELT_PROFILE_EXPANDED_REVIEWED)

    assert set(profile["alias"]) == {
        "統一",
        "長榮",
        "台塑",
        "國泰",
        "富邦",
        "第一",
        "合庫",
        "台新",
        "南亞",
    }
    assert profile["use_for_matching"].tolist() == [False] * len(profile)
    assert all(
        "disabled by GDELT high-risk alias policy" in reason
        for reason in profile["review_reason"]
    )


def test_tej_display_mark_is_removed_before_alias_output() -> None:
    candidates = generate_alias_candidates(
        _synthetic_profile_universe(),
        _synthetic_profile_metadata(),
    )

    normalized = _row_by_alias(candidates, "國巨")

    assert normalized["source_column"] == "chinese_short_name"
    assert "TEJ display mark removed" in normalized["notes"]
    assert candidates.loc[candidates["alias"] == "國巨*"].empty


def test_normalized_curated_alias_is_enabled_only_after_profile_review() -> None:
    candidates = generate_alias_candidates(
        _synthetic_profile_universe(),
        _synthetic_profile_metadata(),
    )
    candidate = _row_by_alias(candidates, "國巨")

    profile = apply_gdelt_profile(candidates, profile=GDELT_PROFILE_EXPANDED_REVIEWED)
    normalized = _row_by_alias(profile, "國巨")
    yageo = _row_by_alias(profile, "Yageo")

    assert "TEJ display mark removed" in candidate["notes"]
    assert bool(normalized["use_for_matching"])
    assert "high-confidence Chinese short alias" in normalized["notes"]
    assert bool(yageo["use_for_matching"])
    assert "high-confidence English brand alias" in yageo["notes"]


def test_profile_output_schema_includes_profile_and_matching_flag() -> None:
    candidates = generate_alias_candidates(
        _synthetic_profile_universe(),
        _synthetic_profile_metadata(),
    )

    profile = apply_gdelt_profile(candidates, profile=GDELT_PROFILE_EXPANDED_REVIEWED)

    assert list(profile.columns) == ALIAS_OUTPUT_COLUMNS
    assert set(profile["profile"]) == {GDELT_PROFILE_EXPANDED_REVIEWED}
    assert "use_for_matching" in profile.columns
