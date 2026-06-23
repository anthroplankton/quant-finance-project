"""Build conservative company-alias tables for news matching.

The alias table is derived from local TEJ processed metadata. It does not call
external services or use LLMs; ambiguous aliases are flagged for review before
they are used in GDELT matching.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Iterable

import pandas as pd


ALIAS_OUTPUT_COLUMNS = [
    "ticker",
    "stock_id",
    "alias",
    "alias_type",
    "language",
    "source_column",
    "is_ambiguous",
    "use_for_matching",
    "review_reason",
    "profile",
    "notes",
]

ALIAS_SOURCE_COLUMNS = [
    ("ticker", "ticker", "code", "ticker"),
    ("official_chinese_name", "official_chinese_name", "zh", "official_chinese_name"),
    ("chinese_short_name", "chinese_short_name", "zh", "chinese_short_name"),
    ("official_english_name", "official_english_name", "en", "official_english_name"),
    ("english_short_name", "english_short_name", "en", "english_short_name"),
]

KNOWN_AMBIGUOUS_CHINESE_ALIASES = {
    "統一",
    "長榮",
    "台塑",
    "南亞",
    "中鋼",
    "國泰",
    "富邦",
    "第一",
    "合庫",
    "台新",
}

GDELT_HIGH_RISK_CHINESE_ALIASES = {
    "統一",
    "長榮",
    "台塑",
    "南亞",
    "國泰",
    "富邦",
    "第一",
    "合庫",
    "台新",
}

GDELT_HIGH_CONFIDENCE_CHINESE_SHORT_NAMES = {
    "台積電",
    "聯發科",
    "鴻海",
    "聯電",
    "中華電",
    "台達電",
    "日月光投控",
    "華碩",
    "廣達",
    "瑞昱",
    "智邦",
    "緯創",
    "緯穎",
    "萬海",
    "遠傳",
    "和碩",
    "聯詠",
    "陽明",
    "彰銀",
    "國巨",
    "玉山金",
    "兆豐金",
    "中信金",
    "元大金",
    "開發金",
    "第一金",
    "合庫金",
    "長榮航",
}

GDELT_HIGH_CONFIDENCE_ENGLISH_BRANDS = {
    "foxconn",
    "hon hai",
    "mediatek",
    "tsmc",
    "yageo",
}

GDELT_SHORT_ALIAS_TYPES = {
    "chinese_short_name",
    "english_short_name",
    "short_name",
    "acronym",
}

GDELT_PROFILE_CONSERVATIVE = "conservative"
GDELT_PROFILE_EXPANDED_REVIEWED = "expanded_reviewed"
GDELT_PROFILE_OUTPUT_NAMES = {
    GDELT_PROFILE_CONSERVATIVE: "top50_alias_allowlist_gdelt_conservative.csv",
    GDELT_PROFILE_EXPANDED_REVIEWED: (
        "top50_alias_allowlist_gdelt_expanded_reviewed.csv"
    ),
}

GENERIC_CHINESE_ALIASES = {
    "集團",
    "控股",
    "投控",
    "金控",
    "銀行",
    "證券",
    "台灣",
    "臺灣",
    "中華",
    "電子",
    "科技",
}

GENERIC_ENGLISH_ALIASES = {
    "bank",
    "cement",
    "chemical",
    "electronics",
    "financial",
    "first",
    "food",
    "global",
    "group",
    "holding",
    "holdings",
    "industrial",
    "international",
    "steel",
    "technology",
}


class AliasGenerationError(RuntimeError):
    """Raised when alias generation inputs are incomplete or invalid."""


@dataclass(frozen=True)
class AliasRecord:
    """One candidate alias before conversion to a DataFrame."""

    ticker: str
    stock_id: str
    alias: str
    alias_type: str
    language: str
    source_column: str
    is_ambiguous: bool
    use_for_matching: bool
    review_reason: str
    profile: str
    notes: str


def normalize_alias(value: object) -> str:
    """Normalize whitespace while preserving the original alias text."""

    if pd.isna(value):
        return ""
    text = str(value).replace("\u3000", " ").strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[\*＊]+$", "", text).strip()
    return text


def _alias_key(alias: str) -> str:
    return normalize_alias(alias).casefold()


def _cjk_length(value: str) -> int:
    return sum(1 for char in value if "\u4e00" <= char <= "\u9fff")


def _english_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _english_compact_length(value: str) -> int:
    return len(re.sub(r"[^a-z0-9]+", "", value.casefold()))


def _require_columns(frame: pd.DataFrame, columns: Iterable[str], *, name: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise AliasGenerationError(
            f"{name} is missing required column(s): {', '.join(missing)}"
        )


def _merged_company_rows(
    universe: pd.DataFrame,
    company_metadata: pd.DataFrame,
) -> pd.DataFrame:
    _require_columns(universe, ("stock_id", "ticker"), name="top50 universe")
    _require_columns(company_metadata, ("stock_id", "ticker"), name="company metadata")

    base = universe[["stock_id", "ticker"]].drop_duplicates()
    merged = base.merge(
        company_metadata,
        on=["stock_id", "ticker"],
        how="left",
        suffixes=("_universe", "_metadata"),
        indicator=True,
    )
    missing = merged.loc[merged["_merge"] != "both", "ticker"].astype(str).tolist()
    if missing:
        raise AliasGenerationError(
            "Missing company metadata for top-50 ticker(s): " + ", ".join(missing)
        )

    universe_name_columns = [
        column
        for column in (
            "official_chinese_name",
            "official_english_name",
            "industry",
        )
        if column in universe.columns
    ]
    if universe_name_columns:
        merged = merged.merge(
            universe[["stock_id", "ticker", *universe_name_columns]],
            on=["stock_id", "ticker"],
            how="left",
            suffixes=("", "_universe"),
        )
    return merged.drop(columns=["_merge"])


def _row_value(row: pd.Series, column: str) -> str:
    for candidate in (
        column,
        f"{column}_metadata",
        f"{column}_universe",
    ):
        if candidate in row.index:
            value = normalize_alias(row[candidate])
            if value:
                return value
    return ""


def _row_alias_value(row: pd.Series, column: str) -> tuple[str, bool]:
    for candidate in (
        column,
        f"{column}_metadata",
        f"{column}_universe",
    ):
        if candidate in row.index:
            raw_value = row[candidate]
            alias = normalize_alias(raw_value)
            if alias:
                raw_text = "" if pd.isna(raw_value) else str(raw_value).strip()
                had_display_mark = raw_text != alias and bool(
                    re.search(r"[\*＊]\s*$", raw_text)
                )
                return alias, had_display_mark
    return "", False


def _base_notes(alias_type: str) -> str:
    if alias_type == "ticker":
        return "Ticker/code alias; monitor for numeric false positives."
    if alias_type.startswith("official_"):
        return "Official full company name."
    return "Short alias; review false-positive risk before production matching."


def ambiguity_reasons(alias: str, *, alias_type: str, language: str) -> list[str]:
    """Return conservative review reasons for a candidate alias."""

    reasons: list[str] = []
    if alias_type == "ticker":
        return reasons

    normalized = normalize_alias(alias)
    if language == "zh":
        cjk_len = _cjk_length(normalized)
        if alias_type == "chinese_short_name" and cjk_len <= 2:
            reasons.append("very short Chinese short alias")
        if normalized in KNOWN_AMBIGUOUS_CHINESE_ALIASES:
            reasons.append("known broad Taiwan market alias")
        if normalized in GENERIC_CHINESE_ALIASES:
            reasons.append("common market or group word")
    elif language == "en":
        english_key = _english_key(normalized)
        if alias_type == "english_short_name" and _english_compact_length(alias) <= 3:
            reasons.append("very short English short alias")
        if english_key in GENERIC_ENGLISH_ALIASES:
            reasons.append("generic English word")
    return reasons


def _append_reason(existing: str, reason: str) -> str:
    if not existing:
        return reason
    if reason in existing.split("; "):
        return existing
    return f"{existing}; {reason}"


def _append_note(existing: str, note: str) -> str:
    if not existing:
        return note
    if note in existing:
        return existing
    return f"{existing} {note}"


def generate_alias_candidates(
    universe: pd.DataFrame,
    company_metadata: pd.DataFrame,
    *,
    allow_ambiguous_matching: bool = False,
) -> pd.DataFrame:
    """Generate conservative alias candidates for the TEJ top-50 universe."""

    merged = _merged_company_rows(universe, company_metadata)
    records: list[AliasRecord] = []
    seen: set[tuple[str, str]] = set()

    for _, row in merged.sort_values(["ticker", "stock_id"]).iterrows():
        ticker = normalize_alias(row["ticker"])
        stock_id = normalize_alias(row["stock_id"])
        for column, alias_type, language, source_column in ALIAS_SOURCE_COLUMNS:
            alias, had_display_mark = _row_alias_value(row, column)
            if not alias:
                continue
            key = (ticker, _alias_key(alias))
            if key in seen:
                continue
            seen.add(key)

            reasons = ambiguity_reasons(
                alias,
                alias_type=alias_type,
                language=language,
            )
            is_ambiguous = bool(reasons)
            use_for_matching = (not is_ambiguous) or allow_ambiguous_matching
            notes = _base_notes(alias_type)
            if had_display_mark:
                notes = _append_note(
                    notes,
                    "TEJ display mark removed from source alias.",
                )
            if is_ambiguous and allow_ambiguous_matching:
                notes = f"{notes} Ambiguous alias explicitly enabled."
            records.append(
                AliasRecord(
                    ticker=ticker,
                    stock_id=stock_id,
                    alias=alias,
                    alias_type=alias_type,
                    language=language,
                    source_column=source_column,
                    is_ambiguous=is_ambiguous,
                    use_for_matching=use_for_matching,
                    review_reason="; ".join(reasons),
                    profile="candidate",
                    notes=notes,
                )
            )

    frame = pd.DataFrame([record.__dict__ for record in records])
    if frame.empty:
        return pd.DataFrame(columns=ALIAS_OUTPUT_COLUMNS)

    shared_aliases = (
        frame.groupby(frame["alias"].map(_alias_key))["ticker"]
        .agg(lambda values: sorted(set(values)))
        .to_dict()
    )
    for index, row in frame.iterrows():
        tickers = shared_aliases.get(_alias_key(row["alias"]), [])
        if len(tickers) <= 1:
            continue
        reason = f"alias shared by tickers: {', '.join(tickers)}"
        frame.at[index, "is_ambiguous"] = True
        frame.at[index, "use_for_matching"] = bool(allow_ambiguous_matching)
        frame.at[index, "review_reason"] = _append_reason(
            str(row["review_reason"]),
            reason,
        )

    return frame[ALIAS_OUTPUT_COLUMNS].sort_values(
        ["ticker", "alias_type", "alias"],
    ).reset_index(drop=True)


def _is_shared_alias_reason(reason: str) -> bool:
    return "alias shared by tickers" in reason


def _with_note(row: pd.Series, note: str) -> str:
    return _append_note(str(row.get("notes", "")), note)


def _is_curated_gdelt_short_alias(
    alias: str,
    *,
    alias_type: str,
    language: str,
) -> bool:
    if alias_type not in GDELT_SHORT_ALIAS_TYPES:
        return False
    if language == "zh":
        return alias in GDELT_HIGH_CONFIDENCE_CHINESE_SHORT_NAMES
    if language == "en":
        return _english_key(alias) in GDELT_HIGH_CONFIDENCE_ENGLISH_BRANDS
    return False


def apply_gdelt_profile(
    alias_candidates: pd.DataFrame,
    *,
    profile: str,
) -> pd.DataFrame:
    """Apply a GDELT matching profile to alias candidates."""

    if profile not in GDELT_PROFILE_OUTPUT_NAMES:
        allowed = ", ".join(sorted(GDELT_PROFILE_OUTPUT_NAMES))
        raise AliasGenerationError(f"Unknown GDELT alias profile {profile!r}: {allowed}")
    if alias_candidates.empty:
        output = pd.DataFrame(columns=ALIAS_OUTPUT_COLUMNS)
        output["profile"] = profile
        return output

    frame = alias_candidates.copy()
    frame["profile"] = profile

    for index, row in frame.iterrows():
        alias = normalize_alias(row["alias"])
        alias_type = str(row["alias_type"])
        language = str(row["language"])
        review_reason = str(row.get("review_reason", ""))
        is_shared = _is_shared_alias_reason(review_reason)
        is_short_alias = alias_type in GDELT_SHORT_ALIAS_TYPES
        is_curated_short_alias = _is_curated_gdelt_short_alias(
            alias,
            alias_type=alias_type,
            language=language,
        )
        use_for_matching = False

        if alias_type == "ticker":
            review_reason = _append_reason(
                review_reason,
                "pure ticker disabled for GDELT numeric false-positive risk",
            )
        elif is_shared:
            use_for_matching = False
        elif alias in GDELT_HIGH_RISK_CHINESE_ALIASES:
            review_reason = _append_reason(
                review_reason,
                "disabled by GDELT high-risk alias policy",
            )
        elif alias_type in {"official_chinese_name", "official_english_name"}:
            use_for_matching = True
        elif profile == GDELT_PROFILE_CONSERVATIVE:
            use_for_matching = False
        elif is_curated_short_alias and language == "zh":
            use_for_matching = True
            frame.at[index, "notes"] = _with_note(
                row,
                "Expanded-reviewed policy enables high-confidence Chinese short alias.",
            )
        elif is_curated_short_alias and language == "en":
            use_for_matching = True
            frame.at[index, "notes"] = _with_note(
                row,
                "Expanded-reviewed policy enables high-confidence English brand alias.",
            )
        elif is_short_alias:
            review_reason = _append_reason(
                review_reason,
                "short alias not in GDELT curated allowlist",
            )
        elif bool(row.get("is_ambiguous")):
            use_for_matching = False

        frame.at[index, "review_reason"] = review_reason
        frame.at[index, "is_ambiguous"] = bool(review_reason)
        frame.at[index, "use_for_matching"] = bool(use_for_matching)

    return frame[ALIAS_OUTPUT_COLUMNS].sort_values(
        ["ticker", "alias_type", "alias"],
    ).reset_index(drop=True)


def gdelt_profile_summary(profile_aliases: pd.DataFrame) -> dict[str, object]:
    """Summarize one GDELT alias profile output."""

    if profile_aliases.empty:
        return {
            "profile": "",
            "total_aliases": 0,
            "enabled_aliases": 0,
            "disabled_aliases": 0,
            "ambiguous_aliases": 0,
            "tickers_covered": 0,
        }

    enabled = int(profile_aliases["use_for_matching"].sum())
    total = int(len(profile_aliases))
    return {
        "profile": str(profile_aliases["profile"].iloc[0]),
        "total_aliases": total,
        "enabled_aliases": enabled,
        "disabled_aliases": total - enabled,
        "ambiguous_aliases": int(profile_aliases["is_ambiguous"].sum()),
        "tickers_covered": int(profile_aliases["ticker"].nunique()),
    }


def alias_review_table(alias_candidates: pd.DataFrame) -> pd.DataFrame:
    """Return rows requiring manual review before production matching."""

    if alias_candidates.empty:
        return pd.DataFrame(columns=ALIAS_OUTPUT_COLUMNS)
    mask = alias_candidates["is_ambiguous"] | ~alias_candidates["use_for_matching"]
    return alias_candidates.loc[mask, ALIAS_OUTPUT_COLUMNS].reset_index(drop=True)


def alias_summary(alias_candidates: pd.DataFrame) -> dict[str, object]:
    """Summarize an alias candidate table for local probe logs."""

    if alias_candidates.empty:
        return {
            "tickers": 0,
            "alias_candidates": 0,
            "use_for_matching": 0,
            "ambiguous_aliases": 0,
            "review_rows": 0,
            "review_reason_counts": {},
        }

    reason_counter: Counter[str] = Counter()
    for reason_text in alias_candidates["review_reason"].dropna().astype(str):
        for reason in [part.strip() for part in reason_text.split(";") if part.strip()]:
            reason_counter[reason] += 1

    review = alias_review_table(alias_candidates)
    return {
        "tickers": int(alias_candidates["ticker"].nunique()),
        "alias_candidates": int(len(alias_candidates)),
        "use_for_matching": int(alias_candidates["use_for_matching"].sum()),
        "ambiguous_aliases": int(alias_candidates["is_ambiguous"].sum()),
        "review_rows": int(len(review)),
        "review_reason_counts": dict(sorted(reason_counter.items())),
    }


def build_alias_tables(
    universe: pd.DataFrame,
    company_metadata: pd.DataFrame,
    *,
    allow_ambiguous_matching: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Build candidates, review rows, and a JSON-serializable summary."""

    candidates = generate_alias_candidates(
        universe,
        company_metadata,
        allow_ambiguous_matching=allow_ambiguous_matching,
    )
    review = alias_review_table(candidates)
    summary = alias_summary(candidates)
    return candidates, review, summary


def write_alias_outputs(
    *,
    candidates: pd.DataFrame,
    review: pd.DataFrame,
    summary: dict[str, object],
    output_dir: Path,
) -> dict[str, Path]:
    """Write local-only alias outputs to an ignored output directory."""

    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths = {
        "candidates": output_dir / "top50_alias_candidates.csv",
        "review": output_dir / "top50_alias_review.csv",
        "summary": output_dir / "alias_summary.json",
    }
    candidates.to_csv(output_paths["candidates"], index=False)
    review.to_csv(output_paths["review"], index=False)
    output_paths["summary"].write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_paths
