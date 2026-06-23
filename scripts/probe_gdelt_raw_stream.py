"""Stream a bounded GDELT raw GKG probe without storing raw files by default.

The script is a feasibility tool, not a production collector. It downloads at
most a small number of GDELT raw GKG zip files, filters rows by conservative
company aliases, writes metadata-only outputs, and deletes temporary raw files
unless --keep-raw is explicitly set.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import (
    FIRST_COMPLETED,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    wait,
)
import csv
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
from statistics import median
import sys
import tempfile
from threading import Lock, get_ident
import time as time_module
from typing import BinaryIO, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import urlopen
import zipfile


REPO_ROOT = Path(__file__).resolve().parents[1]
GDELT_V2_BASE_URL = "http://data.gdeltproject.org/gdeltv2"
DEFAULT_OUTPUT_DIR = Path("data/processed/news/gdelt_probe")
DEFAULT_RAW_DIR = Path("data/raw/news/gdelt_probe")
DEFAULT_TEMP_RAW_DIR = Path("data/raw/news/gdelt_probe_tmp")
PROJECT_WINDOW_START = "2025-04-01"
PROJECT_WINDOW_END = "2026-03-31"
DEFAULT_MAX_FILES = 8
DEFAULT_MAX_DOWNLOAD_MB = 50.0
DEFAULT_DISK_LIMIT_GB = 5.0
DEFAULT_MAX_MISSING_FILES = 10
DEFAULT_WORKERS = 1
DEFAULT_MATCHED_SAMPLE_SIZE = MAX_SAMPLE_ROWS = 500
DEFAULT_PROGRESS_INTERVAL_SECONDS = 30.0
MAX_WORKERS = 32
WORKER_BACKENDS = {"thread", "process"}
MAX_ALLOWED_FILES = 3_500
MAX_FILE_RETRIES = 2
MAX_FAILED_FILES_RECORDED = 20
MAX_MISSING_FILES_RECORDED = 50
MATCH_TEXT_EXCERPT_CHARS = 220
SLOWEST_FILES_RECORDED = 10
MATCHING_SEMANTICS_VERSION = "gkg_content_fields_latin_boundary_cjk_substring_v2"
MATCHED_AUDIT_SCHEMA_VERSION = "matched_metadata_audit_v1"
OUTPUT_SCHEMA_VERSION = "gdelt_raw_probe_outputs_v2"
SHARD_FINGERPRINT_VERSION = "gdelt_raw_probe_shard_fingerprint_v1"
REUSABLE_SHARD_STATUSES = {"completed", "missing"}
CHUNK_SIZE = 1024 * 256
LATIN_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")
ALLOWED_OUTPUT_ROOTS = (
    Path("data/processed/news"),
    Path("data/raw/news"),
)
QUERY_METHOD = "gdelt_raw_gkg_stream_probe"
TRANSIENT_FILE_ERRORS = (HTTPError, URLError, TimeoutError, OSError, zipfile.BadZipFile)

# GKG 2.1 raw files are headerless. Fields 0-4 are metadata:
# GKGRECORDID, DATE, SourceCollectionIdentifier, SourceCommonName, DocumentIdentifier.
# Those metadata fields, source domains, and URLs must not drive company matching.
HEADERLESS_GKG_RECORD_ID_INDEX = 0
HEADERLESS_GKG_DATE_INDEX = 1
HEADERLESS_GKG_SOURCE_COLLECTION_INDEX = 2
HEADERLESS_GKG_SOURCE_COMMON_NAME_INDEX = 3
HEADERLESS_GKG_DOCUMENT_IDENTIFIER_INDEX = 4
HEADERLESS_GKG_MATCH_FIELD_INDICES = (
    7,  # Themes
    8,  # V2Themes
    9,  # Locations
    10,  # V2Locations
    11,  # Persons
    12,  # V2Persons
    13,  # Organizations
    14,  # V2Organizations
    23,  # AllNames
)
HEADERLESS_GKG_MATCH_FIELDS = (
    (7, "Themes"),
    (8, "V2Themes"),
    (9, "Locations"),
    (10, "V2Locations"),
    (11, "Persons"),
    (12, "V2Persons"),
    (13, "Organizations"),
    (14, "V2Organizations"),
    (23, "AllNames"),
)
MATCH_FIELD_HEADER_NAMES = {
    "themes",
    "v2themes",
    "locations",
    "v2locations",
    "persons",
    "v2persons",
    "organizations",
    "v2organizations",
    "allnames",
}


def configure_csv_field_size_limit() -> int:
    """Set the CSV parser field-size limit as high as the platform accepts."""

    limit = sys.maxsize
    while limit > 0:
        try:
            csv.field_size_limit(limit)
        except OverflowError:
            limit //= 10
            continue
        return limit
    raise RuntimeError("Could not configure CSV field-size limit.")


CSV_FIELD_SIZE_LIMIT = configure_csv_field_size_limit()


@dataclass(frozen=True)
class Alias:
    ticker: str
    alias: str
    alias_type: str = ""


@dataclass(frozen=True)
class AliasFieldMatch:
    alias: Alias
    field_name: str
    text_excerpt: str


@dataclass(frozen=True)
class AliasMatcher:
    alias: Alias
    contains_cjk: bool
    folded_alias: str
    order: int
    pattern: re.Pattern[str] | None = None
    anchor_token: str = ""
    cjk_anchor: str = ""


@dataclass(frozen=True)
class AliasMatcherIndex:
    matchers: tuple[AliasMatcher, ...]
    latin_by_anchor: dict[str, tuple[AliasMatcher, ...]]
    cjk_by_anchor: dict[str, tuple[AliasMatcher, ...]]
    fallback_matchers: tuple[AliasMatcher, ...]


@dataclass(frozen=True)
class PreparedMatchField:
    name: str
    text: str
    folded_text: str
    latin_tokens: frozenset[str]
    cjk_chars: frozenset[str]


@dataclass(frozen=True)
class GkgParseResult:
    matches: list[dict[str, str]]
    rows_scanned: int
    match_seconds: float


@dataclass(frozen=True)
class FileProbeResult:
    index: int
    url: str
    status: str
    download_attempts: int
    retry_count: int
    transferred_bytes: int
    processed_bytes: int
    max_raw_file_bytes: int
    matches: list[dict[str, str]]
    rows_scanned: int = 0
    elapsed_seconds: float = 0.0
    download_seconds: float = 0.0
    decompress_seconds: float = 0.0
    parse_seconds: float = 0.0
    match_seconds: float = 0.0
    worker_id: str = ""
    error_type: str = ""
    message: str = ""
    attempts: int = 0
    projected_usage_bytes: int | None = None


@dataclass
class CandidateProcessState:
    index: int
    url: str
    file_started_at: float
    download_attempts: int = 0
    retry_count: int = 0
    transferred_bytes: int = 0
    max_raw_file_bytes: int = 0
    download_seconds: float = 0.0


@dataclass(frozen=True)
class ParseWorkerResult:
    status: str
    matches: list[dict[str, str]]
    rows_scanned: int
    parse_seconds: float
    match_seconds: float
    worker_id: str
    error_type: str = ""
    message: str = ""


class GdeltRawStreamError(RuntimeError):
    """Raised when a bounded raw-stream probe cannot be completed."""


class DiskLimitExceeded(GdeltRawStreamError):
    """Raised when a raw probe would exceed its local disk budget."""

    def __init__(
        self,
        message: str,
        *,
        projected_usage_bytes: int,
        disk_limit_bytes: int,
        transferred_bytes: int = 0,
    ) -> None:
        super().__init__(message)
        self.projected_usage_bytes = projected_usage_bytes
        self.disk_limit_bytes = disk_limit_bytes
        self.transferred_bytes = transferred_bytes


class MaxDownloadExceeded(GdeltRawStreamError):
    """Raised when a download attempt would exceed the transfer budget."""

    def __init__(
        self,
        message: str,
        *,
        transferred_bytes: int,
        max_download_bytes: int,
    ) -> None:
        super().__init__(message)
        self.transferred_bytes = transferred_bytes
        self.max_download_bytes = max_download_bytes


class DownloadAttemptFailed(GdeltRawStreamError):
    """Raised when a download attempt fails after transferring bytes."""

    def __init__(
        self,
        message: str,
        *,
        transferred_bytes: int,
        error_type: str,
    ) -> None:
        super().__init__(message)
        self.transferred_bytes = transferred_bytes
        self.error_type = error_type


class MissingSourceFile(GdeltRawStreamError):
    """Raised when a raw GDELT archive file is absent from the source."""

    def __init__(
        self,
        message: str,
        *,
        transferred_bytes: int = 0,
    ) -> None:
        super().__init__(message)
        self.transferred_bytes = transferred_bytes


class ProbeResourceLimiter:
    """Thread-safe transfer and temporary raw-file budget tracker."""

    def __init__(
        self,
        *,
        max_download_bytes: int,
        disk_limit_bytes: int,
        disk_usage_base_bytes: int,
    ) -> None:
        self.max_download_bytes = max_download_bytes
        self.disk_limit_bytes = disk_limit_bytes
        self.disk_usage_base_bytes = disk_usage_base_bytes
        self._lock = Lock()
        self._transferred_bytes = 0
        self._active_raw_bytes = 0
        self._max_disk_usage_observed = disk_usage_base_bytes

    @property
    def max_disk_usage_observed(self) -> int:
        with self._lock:
            return self._max_disk_usage_observed

    def record_download_chunk(
        self,
        *,
        url: str,
        chunk_bytes: int,
        file_downloaded_bytes: int,
    ) -> None:
        with self._lock:
            self._transferred_bytes += chunk_bytes
            if self._transferred_bytes > self.max_download_bytes:
                raise MaxDownloadExceeded(
                    "max_download_mb exceeded while downloading "
                    f"{url!r}.",
                    transferred_bytes=file_downloaded_bytes,
                    max_download_bytes=self.max_download_bytes,
                )

            projected_usage = (
                self.disk_usage_base_bytes + self._active_raw_bytes + chunk_bytes
            )
            if projected_usage > self.disk_limit_bytes:
                raise DiskLimitExceeded(
                    "disk_limit_gb_exceeded while downloading "
                    f"{url!r}: projected local probe usage "
                    f"{projected_usage} bytes exceeds limit "
                    f"{self.disk_limit_bytes} bytes.",
                    projected_usage_bytes=projected_usage,
                    disk_limit_bytes=self.disk_limit_bytes,
                    transferred_bytes=file_downloaded_bytes,
                )

            self._active_raw_bytes += chunk_bytes
            self._max_disk_usage_observed = max(
                self._max_disk_usage_observed,
                projected_usage,
            )

    def release_raw_bytes(self, byte_count: int) -> None:
        if byte_count <= 0:
            return
        with self._lock:
            self._active_raw_bytes = max(0, self._active_raw_bytes - byte_count)


def built_in_aliases() -> list[Alias]:
    """Return a tiny default alias set for feasibility probing."""

    return [
        Alias("2330", "台積電"),
        Alias("2330", "TSMC"),
        Alias("2330", "Taiwan Semiconductor"),
        Alias("2330", "Taiwan Semiconductor Manufacturing"),
        Alias("2317", "鴻海"),
        Alias("2317", "Hon Hai"),
        Alias("2317", "Hon Hai Precision"),
        Alias("2317", "Foxconn"),
        Alias("2454", "聯發科"),
        Alias("2454", "MediaTek"),
        Alias("2454", "MediaTek Inc"),
    ]


def parse_iso_date(value: str) -> date:
    """Parse a YYYY-MM-DD date for CLI arguments and summaries."""

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise GdeltRawStreamError(
            f"Invalid date {value!r}; expected YYYY-MM-DD."
        ) from exc


def interval_timestamps(start_date: str, end_date: str) -> list[str]:
    """Return 15-minute GDELT timestamp labels for an inclusive date window."""

    start = parse_iso_date(start_date)
    end = parse_iso_date(end_date)
    if start > end:
        raise GdeltRawStreamError("start_date must be on or before end_date.")

    current = datetime.combine(start, time.min)
    last = datetime.combine(end, time(hour=23, minute=45))
    labels: list[str] = []
    while current <= last:
        labels.append(current.strftime("%Y%m%d%H%M%S"))
        current += timedelta(minutes=15)
    return labels


def gdelt_gkg_url(timestamp_label: str) -> str:
    """Return the expected GDELT 2.0 GKG compressed-file URL."""

    return f"{GDELT_V2_BASE_URL}/{timestamp_label}.gkg.csv.zip"


def candidate_gkg_urls(
    *,
    start_date: str,
    end_date: str,
    max_files: int,
) -> tuple[list[str], int]:
    """Return capped candidate GKG URLs and the uncapped file count."""

    if max_files < 1 or max_files > MAX_ALLOWED_FILES:
        raise GdeltRawStreamError(
            f"max_files must be between 1 and {MAX_ALLOWED_FILES}; got {max_files}."
        )
    labels = interval_timestamps(start_date, end_date)
    return [gdelt_gkg_url(label) for label in labels[:max_files]], len(labels)


def validate_workers(workers: int) -> int:
    """Validate bounded local worker count for raw GKG file processing."""

    if workers < 1:
        raise GdeltRawStreamError("workers must be a positive integer.")
    if workers > MAX_WORKERS:
        raise GdeltRawStreamError(
            f"workers must be between 1 and {MAX_WORKERS}; got {workers}."
        )
    return workers


def validate_worker_backend(worker_backend: str) -> str:
    """Validate the worker execution backend."""

    normalized = worker_backend.strip().casefold()
    if normalized not in WORKER_BACKENDS:
        allowed = ", ".join(sorted(WORKER_BACKENDS))
        raise GdeltRawStreamError(
            f"worker_backend must be one of {allowed}; got {worker_backend!r}."
        )
    return normalized


def _process_backend_error(*, phase: str, exc: BaseException) -> GdeltRawStreamError:
    return GdeltRawStreamError(
        "process backend failed to "
        f"{phase}. Use --worker-backend thread as a fallback. "
        f"Original {type(exc).__name__}: {exc}"
    )


def validate_local_data_path(
    path: str | Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> Path:
    """Resolve a path and require it to live under ignored news data roots."""

    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    resolved = candidate.resolve(strict=False)
    allowed_roots = [
        (repo_root / root).resolve(strict=False) for root in ALLOWED_OUTPUT_ROOTS
    ]
    if not any(resolved == root or root in resolved.parents for root in allowed_roots):
        allowed = ", ".join(str(root) for root in ALLOWED_OUTPUT_ROOTS)
        raise GdeltRawStreamError(
            f"Output path must be under one of the ignored news data roots: {allowed}."
        )
    return resolved


def load_aliases(aliases_file: str | Path | None = None) -> list[Alias]:
    """Load aliases from CSV or return the built-in tiny sample aliases.

    CSV files should contain columns named ticker and alias. Two-column files
    without a header are also accepted.
    """

    if aliases_file is None:
        return built_in_aliases()

    path = Path(aliases_file)
    if not path.is_file():
        raise GdeltRawStreamError(f"Alias file not found: {path}.")

    aliases: list[Alias] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(2048)
        handle.seek(0)
        try:
            has_header = csv.Sniffer().has_header(sample) if sample.strip() else False
        except csv.Error:
            has_header = False
        if has_header:
            reader = csv.DictReader(handle)
            for row in reader:
                if not _row_allows_matching(row):
                    continue
                ticker = (row.get("ticker") or row.get("stock_id") or "").strip()
                alias = (row.get("alias") or row.get("company_alias") or "").strip()
                alias_type = (row.get("alias_type") or "").strip()
                if ticker and alias:
                    aliases.append(
                        Alias(ticker=ticker, alias=alias, alias_type=alias_type)
                    )
        else:
            reader = csv.reader(handle)
            for row in reader:
                if len(row) >= 2 and row[0].strip() and row[1].strip():
                    aliases.append(Alias(ticker=row[0].strip(), alias=row[1].strip()))

    if not aliases:
        raise GdeltRawStreamError(f"No aliases found in {path}.")
    return aliases


def _row_allows_matching(row: dict[str, str | None]) -> bool:
    value = row.get("use_for_matching")
    if value is None or str(value).strip() == "":
        return True
    normalized = str(value).strip().casefold()
    return normalized in {"1", "true", "t", "yes", "y"}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_alias_payload(aliases: Iterable[Alias]) -> str:
    payload = [
        {
            "ticker": alias.ticker,
            "alias": alias.alias,
            "alias_type": alias.alias_type,
        }
        for alias in aliases
    ]
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _alias_content_digest(
    aliases: Iterable[Alias],
    *,
    alias_file_path: str | Path | None = None,
) -> tuple[str, str, str]:
    if alias_file_path is not None:
        path = Path(alias_file_path)
        return _sha256_bytes(path.read_bytes()), str(alias_file_path), "file"
    return (
        _sha256_bytes(_canonical_alias_payload(aliases).encode("utf-8")),
        "",
        "in_memory_alias_list",
    )


def _fingerprint_id(fingerprint: dict[str, object]) -> str:
    payload = {
        key: value for key, value in fingerprint.items() if key != "run_fingerprint_id"
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256_bytes(canonical.encode("utf-8"))


def build_run_fingerprint(
    *,
    aliases: Iterable[Alias],
    start_date: str,
    end_date: str,
    matched_sample_size: int,
    sample_per_ticker: int | None,
    alias_file_path: str | Path | None = None,
) -> dict[str, object]:
    """Build a deterministic shard provenance fingerprint for one probe run."""

    alias_digest, alias_display_path, alias_digest_source = _alias_content_digest(
        aliases,
        alias_file_path=alias_file_path,
    )
    fingerprint: dict[str, object] = {
        "fingerprint_version": SHARD_FINGERPRINT_VERSION,
        "query_method": QUERY_METHOD,
        "start_date": start_date,
        "end_date": end_date,
        "alias_content_sha256": alias_digest,
        "alias_digest_source": alias_digest_source,
        "alias_file_path": alias_display_path,
        "matching_semantics_version": MATCHING_SEMANTICS_VERSION,
        "url_source_document_identifier_excluded": True,
        "latin_token_boundary_matching_enabled": True,
        "cjk_substring_matching_enabled": True,
        "token_candidate_alias_index_enabled": True,
        "matched_audit_schema_version": MATCHED_AUDIT_SCHEMA_VERSION,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "matched_sample_size": matched_sample_size,
        "sample_per_ticker": sample_per_ticker,
    }
    fingerprint["run_fingerprint_id"] = _fingerprint_id(fingerprint)
    return fingerprint


def _fingerprint_mismatches(
    *,
    expected: dict[str, object],
    observed: object,
) -> list[str]:
    if not isinstance(observed, dict):
        return ["run_fingerprint missing or malformed"]
    mismatches: list[str] = []
    for key in sorted(set(expected) | set(observed)):
        expected_value = expected.get(key, "<missing>")
        observed_value = observed.get(key, "<missing>")
        if expected_value != observed_value:
            mismatches.append(
                f"{key}: expected {expected_value!r}, observed {observed_value!r}"
            )
    return mismatches


def _format_shard_fingerprint_error(
    *,
    path: Path,
    mismatches: list[str],
) -> str:
    preview = "; ".join(mismatches[:3])
    if len(mismatches) > 3:
        preview += f"; ... {len(mismatches) - 3} more"
    return f"Shard fingerprint mismatch for {path}: {preview}."


def _contains_cjk(value: str) -> bool:
    return any(
        "\u3400" <= char <= "\u9fff" or "\uf900" <= char <= "\ufaff"
        for char in value
    )


def _is_cjk_char(value: str) -> bool:
    return "\u3400" <= value <= "\u9fff" or "\uf900" <= value <= "\ufaff"


def _first_cjk_char(value: str) -> str:
    for char in value:
        if _is_cjk_char(char):
            return char
    return ""


@lru_cache(maxsize=2048)
def _latin_alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias.strip())
    escaped = re.sub(r"\\\s+", r"\\s+", escaped)
    return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE)


def _latin_anchor_token(alias: str) -> str:
    tokens = LATIN_TOKEN_PATTERN.findall(alias.casefold())
    if not tokens:
        return ""
    return max(enumerate(tokens), key=lambda item: (len(item[1]), -item[0]))[1]


def prepare_alias_matchers(aliases: Iterable[Alias]) -> list[AliasMatcher]:
    """Compile reusable alias match state for a probe worker."""

    matchers: list[AliasMatcher] = []
    for order, alias in enumerate(aliases):
        normalized_alias = alias.alias.strip()
        if not normalized_alias:
            continue
        contains_cjk = _contains_cjk(normalized_alias)
        folded_alias = normalized_alias.casefold()
        if contains_cjk:
            matchers.append(
                AliasMatcher(
                    alias=alias,
                    contains_cjk=True,
                    folded_alias=folded_alias,
                    order=order,
                    cjk_anchor=_first_cjk_char(folded_alias),
                )
            )
            continue
        matchers.append(
            AliasMatcher(
                alias=alias,
                contains_cjk=False,
                folded_alias=folded_alias,
                order=order,
                pattern=_latin_alias_pattern(normalized_alias),
                anchor_token=_latin_anchor_token(normalized_alias),
            )
        )
    return matchers


def build_alias_matcher_index(
    alias_matchers: Iterable[AliasMatcher],
) -> AliasMatcherIndex:
    """Build deterministic field-token indexes for prepared alias matchers."""

    matchers = tuple(alias_matchers)
    latin_by_anchor: dict[str, list[AliasMatcher]] = defaultdict(list)
    cjk_by_anchor: dict[str, list[AliasMatcher]] = defaultdict(list)
    fallback_matchers: list[AliasMatcher] = []
    for matcher in matchers:
        if matcher.contains_cjk:
            if matcher.cjk_anchor:
                cjk_by_anchor[matcher.cjk_anchor].append(matcher)
            else:
                fallback_matchers.append(matcher)
            continue
        if matcher.anchor_token:
            latin_by_anchor[matcher.anchor_token].append(matcher)
        else:
            fallback_matchers.append(matcher)

    return AliasMatcherIndex(
        matchers=matchers,
        latin_by_anchor={
            key: tuple(sorted(value, key=lambda matcher: matcher.order))
            for key, value in latin_by_anchor.items()
        },
        cjk_by_anchor={
            key: tuple(sorted(value, key=lambda matcher: matcher.order))
            for key, value in cjk_by_anchor.items()
        },
        fallback_matchers=tuple(
            sorted(fallback_matchers, key=lambda matcher: matcher.order)
        ),
    )


def _alias_matches_text(row_text: str, alias: str, *, folded_row_text: str) -> bool:
    return _alias_match_span(row_text, alias, folded_row_text=folded_row_text) is not None


def _alias_match_span(
    row_text: str,
    alias: str,
    *,
    folded_row_text: str | None = None,
) -> tuple[int, int] | None:
    normalized_alias = alias.strip()
    if not normalized_alias:
        return None
    if _contains_cjk(normalized_alias):
        folded_text = folded_row_text if folded_row_text is not None else row_text.casefold()
        start = folded_text.find(normalized_alias.casefold())
        if start < 0:
            return None
        return start, start + len(normalized_alias)
    match = _latin_alias_pattern(normalized_alias).search(row_text)
    return match.span() if match is not None else None


def _bounded_match_excerpt(
    text: str,
    *,
    start: int,
    end: int,
    max_chars: int = MATCH_TEXT_EXCERPT_CHARS,
) -> str:
    if max_chars <= 0:
        return ""
    context = max(0, (max_chars - max(0, end - start)) // 2)
    left = max(0, start - context)
    right = min(len(text), end + context)
    excerpt = text[left:right].strip()
    excerpt = re.sub(r"\s+", " ", excerpt)
    if left > 0:
        excerpt = f"...{excerpt}"
    if right < len(text):
        excerpt = f"{excerpt}..."
    if len(excerpt) > max_chars + 6:
        excerpt = excerpt[: max_chars + 3].rstrip() + "..."
    return excerpt


def alias_matches(row_text: str, aliases: Iterable[Alias]) -> list[Alias]:
    """Return the first matched alias per ticker for one GKG row."""

    folded = row_text.casefold()
    matched_by_ticker: dict[str, Alias] = {}
    for alias in aliases:
        if alias.ticker in matched_by_ticker:
            continue
        if _alias_matches_text(row_text, alias.alias, folded_row_text=folded):
            matched_by_ticker[alias.ticker] = alias
    return list(matched_by_ticker.values())


def alias_matches_in_fields(
    match_fields: Iterable[tuple[str, str]],
    aliases: Iterable[Alias],
) -> list[AliasFieldMatch]:
    """Return the first deterministic alias/field match per ticker."""

    return alias_matchers_in_fields(
        match_fields,
        build_alias_matcher_index(prepare_alias_matchers(aliases)),
    )


def alias_matchers_in_fields(
    match_fields: Iterable[tuple[str, str]],
    alias_matchers: Iterable[AliasMatcher] | AliasMatcherIndex,
) -> list[AliasFieldMatch]:
    """Return the first deterministic prepared alias/field match per ticker."""

    matcher_index = (
        alias_matchers
        if isinstance(alias_matchers, AliasMatcherIndex)
        else build_alias_matcher_index(alias_matchers)
    )
    fields = [
        PreparedMatchField(
            name=name,
            text=value,
            folded_text=value.casefold(),
            latin_tokens=frozenset(LATIN_TOKEN_PATTERN.findall(value.casefold())),
            cjk_chars=frozenset(char for char in value.casefold() if _is_cjk_char(char)),
        )
        for name, value in match_fields
        if value
    ]
    candidate_by_order: dict[int, AliasMatcher] = {
        matcher.order: matcher for matcher in matcher_index.fallback_matchers
    }
    for field in fields:
        for token in field.latin_tokens:
            for matcher in matcher_index.latin_by_anchor.get(token, ()):
                candidate_by_order[matcher.order] = matcher
        for char in field.cjk_chars:
            for matcher in matcher_index.cjk_by_anchor.get(char, ()):
                candidate_by_order[matcher.order] = matcher

    matched_by_ticker: dict[str, AliasFieldMatch] = {}
    for matcher in (
        candidate_by_order[order] for order in sorted(candidate_by_order)
    ):
        alias = matcher.alias
        if alias.ticker in matched_by_ticker:
            continue
        for field in fields:
            if matcher.contains_cjk:
                start = field.folded_text.find(matcher.folded_alias)
                if start < 0:
                    continue
                span = (start, start + len(alias.alias.strip()))
            else:
                if matcher.anchor_token and matcher.anchor_token not in field.latin_tokens:
                    continue
                if matcher.pattern is None:
                    continue
                match = matcher.pattern.search(field.text)
                if match is None:
                    continue
                span = match.span()
            if not span:
                continue
            matched_by_ticker[alias.ticker] = AliasFieldMatch(
                alias=alias,
                field_name=field.name,
                text_excerpt=_bounded_match_excerpt(
                    field.text,
                    start=span[0],
                    end=span[1],
                ),
            )
            break
    return list(matched_by_ticker.values())


def _looks_like_header(fields: list[str]) -> bool:
    if not fields:
        return False
    normalized = {_normalize_header_name(field) for field in fields}
    return "date" in normalized and any(
        value in normalized for value in ("documentidentifier", "url")
    )


def _header_index(fields: list[str], *names: str) -> int | None:
    normalized = {
        _normalize_header_name(field): index for index, field in enumerate(fields)
    }
    for name in names:
        index = normalized.get(_normalize_header_name(name))
        if index is not None:
            return index
    return None


def _normalize_header_name(value: str) -> str:
    return "".join(char for char in value.casefold() if char.isalnum())


def _field(fields: list[str], index: int | None) -> str:
    if index is None or index >= len(fields):
        return ""
    return fields[index].strip()


def build_gkg_match_text(fields: list[str], header: list[str] | None = None) -> str:
    """Build searchable text from GKG content/entity/name fields only.

    Matching intentionally excludes source, URL, document identifier, record ID,
    raw-link, media, and other metadata fields to avoid URL/domain false hits.
    """

    values = [field_text for _, field_text in iter_gkg_match_fields(fields, header)]
    return "\t".join(value for value in values if value)


def iter_gkg_match_fields(
    fields: list[str],
    header: list[str] | None = None,
) -> list[tuple[str, str]]:
    """Return allowed GKG content/entity/name fields for matching and excerpts."""

    if header is not None:
        output: list[tuple[str, str]] = []
        for index, field_name in enumerate(header):
            if index >= len(fields):
                continue
            if _normalize_header_name(field_name) in MATCH_FIELD_HEADER_NAMES:
                value = fields[index].strip()
                if value:
                    output.append((field_name, value))
        return output
    return [
        (field_name, _field(fields, index))
        for index, field_name in HEADERLESS_GKG_MATCH_FIELDS
        if _field(fields, index)
    ]


def _format_gdelt_timestamp(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 14 and value[:14].isdigit():
        try:
            return datetime.strptime(value[:14], "%Y%m%d%H%M%S").isoformat()
        except ValueError:
            return value
    if len(value) >= 8 and value[:8].isdigit():
        try:
            return datetime.strptime(value[:8], "%Y%m%d").date().isoformat()
        except ValueError:
            return value
    return value


def _date_from_timestamp(timestamp: str) -> str:
    if len(timestamp) >= 10:
        return timestamp[:10]
    return ""


def metadata_from_fields(
    fields: list[str],
    *,
    header: list[str] | None,
    matched_alias: AliasFieldMatch,
    source_file: str,
    query_start_date: str,
    query_end_date: str,
) -> dict[str, str]:
    """Extract non-text GKG metadata for a matched row."""

    if header is not None:
        record_index = _header_index(header, "GKGRECORDID", "gkg_record_id")
        date_index = _header_index(header, "DATE", "date", "timestamp")
        source_collection_index = _header_index(
            header,
            "SourceCollectionIdentifier",
            "source_collection_identifier",
        )
        source_index = _header_index(
            header,
            "SourceCommonName",
            "source_common_name",
            "source_domain",
        )
        document_index = _header_index(
            header,
            "DocumentIdentifier",
            "document_identifier",
            "url",
        )
    else:
        record_index = HEADERLESS_GKG_RECORD_ID_INDEX
        date_index = HEADERLESS_GKG_DATE_INDEX
        source_collection_index = HEADERLESS_GKG_SOURCE_COLLECTION_INDEX
        source_index = HEADERLESS_GKG_SOURCE_COMMON_NAME_INDEX
        document_index = HEADERLESS_GKG_DOCUMENT_IDENTIFIER_INDEX

    timestamp = _format_gdelt_timestamp(_field(fields, date_index))
    return {
        "gkg_record_id": _field(fields, record_index),
        "timestamp": timestamp,
        "date": _date_from_timestamp(timestamp),
        "source_collection_identifier": _field(fields, source_collection_index),
        "source_common_name": _field(fields, source_index),
        "document_identifier": _field(fields, document_index),
        "matched_ticker": matched_alias.alias.ticker,
        "matched_company_alias": matched_alias.alias.alias,
        "matched_alias": matched_alias.alias.alias,
        "matched_alias_type": matched_alias.alias.alias_type,
        "matched_field_name": matched_alias.field_name,
        "matched_text_excerpt": matched_alias.text_excerpt,
        "query_start_date": query_start_date,
        "query_end_date": query_end_date,
        "query_method": QUERY_METHOD,
        "gdelt_file": source_file,
    }


def iter_gkg_metadata_matches(
    zip_path: Path,
    *,
    aliases: list[Alias],
    query_start_date: str,
    query_end_date: str,
    source_file_name: str | None = None,
) -> Iterable[dict[str, str]]:
    """Yield metadata-only matches from a compressed GKG file."""

    parse_result = parse_gkg_metadata_matches(
        zip_path,
        aliases=aliases,
        query_start_date=query_start_date,
        query_end_date=query_end_date,
        source_file_name=source_file_name,
    )
    yield from parse_result.matches


def parse_gkg_metadata_matches(
    zip_path: Path,
    *,
    aliases: list[Alias],
    query_start_date: str,
    query_end_date: str,
    source_file_name: str | None = None,
) -> GkgParseResult:
    """Return metadata-only GKG matches plus parser/matcher counters."""

    source_file = source_file_name or zip_path.name
    matches: list[dict[str, str]] = []
    rows_scanned = 0
    match_seconds = 0.0
    alias_matcher_index = build_alias_matcher_index(prepare_alias_matchers(aliases))
    with zipfile.ZipFile(zip_path) as archive:
        for member_name in archive.namelist():
            if member_name.endswith("/"):
                continue
            with archive.open(member_name) as raw_member:
                text_member = (
                    line.decode("utf-8", errors="replace") for line in raw_member
                )
                reader = csv.reader(text_member, delimiter="\t")
                header: list[str] | None = None
                for fields in reader:
                    if not fields:
                        continue
                    if header is None and _looks_like_header(fields):
                        header = fields
                        continue
                    rows_scanned += 1
                    match_fields = iter_gkg_match_fields(fields, header)
                    match_started_at = time_module.perf_counter()
                    field_matches = alias_matchers_in_fields(
                        match_fields,
                        alias_matcher_index,
                    )
                    match_seconds += time_module.perf_counter() - match_started_at
                    for matched_alias in field_matches:
                        matches.append(
                            metadata_from_fields(
                                fields,
                                header=header,
                                matched_alias=matched_alias,
                                source_file=source_file,
                                query_start_date=query_start_date,
                                query_end_date=query_end_date,
                            )
                        )
    return GkgParseResult(
        matches=matches,
        rows_scanned=rows_scanned,
        match_seconds=match_seconds,
    )


def _open_source(url: str, *, timeout_seconds: float) -> BinaryIO:
    parsed = urlparse(url)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path)).open("rb")
    if parsed.scheme in {"http", "https"}:
        return urlopen(url, timeout=timeout_seconds)  # noqa: S310
    path = Path(url)
    if path.exists():
        return path.open("rb")
    return urlopen(url, timeout=timeout_seconds)  # noqa: S310


def download_to_path(
    url: str,
    destination: Path,
    *,
    remaining_bytes: int,
    remaining_disk_bytes: int | None = None,
    disk_usage_base_bytes: int = 0,
    disk_limit_bytes: int | None = None,
    timeout_seconds: float = 30.0,
    resource_limiter: ProbeResourceLimiter | None = None,
) -> int:
    """Download or copy one source into destination, enforcing byte budget."""

    downloaded = 0
    reserved_raw_bytes = 0
    try:
        with _open_source(url, timeout_seconds=timeout_seconds) as source:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("wb") as output:
                while True:
                    chunk = source.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if resource_limiter is not None:
                        resource_limiter.record_download_chunk(
                            url=url,
                            chunk_bytes=len(chunk),
                            file_downloaded_bytes=downloaded,
                        )
                        reserved_raw_bytes += len(chunk)
                    elif downloaded > remaining_bytes:
                        raise MaxDownloadExceeded(
                            "max_download_mb exceeded while downloading "
                            f"{url!r}.",
                            transferred_bytes=downloaded,
                            max_download_bytes=remaining_bytes,
                        )
                    if (
                        remaining_disk_bytes is not None
                        and downloaded > remaining_disk_bytes
                    ):
                        projected_usage = disk_usage_base_bytes + downloaded
                        limit = (
                            disk_limit_bytes
                            if disk_limit_bytes is not None
                            else disk_usage_base_bytes + remaining_disk_bytes
                        )
                        raise DiskLimitExceeded(
                            "disk_limit_gb_exceeded while downloading "
                            f"{url!r}: projected local probe usage "
                            f"{projected_usage} bytes exceeds limit "
                            f"{limit} bytes.",
                            projected_usage_bytes=projected_usage,
                            disk_limit_bytes=limit,
                            transferred_bytes=downloaded,
                        )
                    output.write(chunk)
    except (DiskLimitExceeded, MaxDownloadExceeded):
        if resource_limiter is not None:
            resource_limiter.release_raw_bytes(reserved_raw_bytes)
        destination.unlink(missing_ok=True)
        raise
    except HTTPError as exc:
        if resource_limiter is not None:
            resource_limiter.release_raw_bytes(reserved_raw_bytes)
        destination.unlink(missing_ok=True)
        if exc.code == 404:
            raise MissingSourceFile(
                f"Missing GDELT raw file {url!r}: HTTP 404 Not Found.",
                transferred_bytes=downloaded,
            ) from exc
        raise DownloadAttemptFailed(
            f"Download attempt failed for {url!r}: {exc}",
            transferred_bytes=downloaded,
            error_type=type(exc).__name__,
        ) from exc
    except Exception as exc:
        if resource_limiter is not None:
            resource_limiter.release_raw_bytes(reserved_raw_bytes)
        destination.unlink(missing_ok=True)
        raise DownloadAttemptFailed(
            f"Download attempt failed for {url!r}: {exc}",
            transferred_bytes=downloaded,
            error_type=type(exc).__name__,
        ) from exc
    return downloaded


def _safe_raw_name(url: str, index: int) -> str:
    parsed = urlparse(url)
    name = Path(unquote(parsed.path)).name
    if not name:
        name = f"gdelt_probe_{index:04d}.zip"
    if not name.endswith(".zip"):
        name = f"{name}.zip"
    return name


def _gdelt_file_id(url: str) -> str:
    parsed = urlparse(url)
    name = Path(unquote(parsed.path)).name
    return name or url


def _gdelt_timestamp_from_url(url: str) -> str:
    file_id = _gdelt_file_id(url)
    candidate = file_id.split(".", maxsplit=1)[0]
    if len(candidate) == 14 and candidate.isdigit():
        return candidate
    return ""


def _process_candidate_file(
    *,
    index: int,
    url: str,
    raw_work_dir: Path,
    aliases: list[Alias],
    query_start_date: str,
    query_end_date: str,
    keep_raw: bool,
    max_download_bytes: int,
    resource_limiter: ProbeResourceLimiter,
) -> FileProbeResult:
    file_started_at = time_module.perf_counter()
    raw_name = _safe_raw_name(url, index)
    raw_path = raw_work_dir / raw_name if keep_raw else raw_work_dir / f"{index:05d}_{raw_name}"
    source_file_name = _gdelt_file_id(url)
    transferred_bytes = 0
    max_raw_file_bytes = 0
    download_attempts = 0
    retry_count = 0
    download_seconds = 0.0

    for attempt_index in range(MAX_FILE_RETRIES + 1):
        if attempt_index > 0:
            retry_count += 1
        download_attempts += 1
        try:
            download_started_at = time_module.perf_counter()
            downloaded_bytes = download_to_path(
                url,
                raw_path,
                remaining_bytes=max_download_bytes,
                resource_limiter=resource_limiter,
            )
            download_seconds += time_module.perf_counter() - download_started_at
            transferred_bytes += downloaded_bytes
            max_raw_file_bytes = max(max_raw_file_bytes, downloaded_bytes)

            parse_started_at = time_module.perf_counter()
            parse_result = parse_gkg_metadata_matches(
                raw_path,
                aliases=aliases,
                query_start_date=query_start_date,
                query_end_date=query_end_date,
                source_file_name=source_file_name,
            )
            parse_seconds = time_module.perf_counter() - parse_started_at
            if not keep_raw:
                raw_path.unlink(missing_ok=True)
                resource_limiter.release_raw_bytes(downloaded_bytes)
            return FileProbeResult(
                index=index,
                url=url,
                status="completed",
                download_attempts=download_attempts,
                retry_count=retry_count,
                transferred_bytes=transferred_bytes,
                processed_bytes=downloaded_bytes,
                max_raw_file_bytes=max_raw_file_bytes,
                matches=parse_result.matches,
                rows_scanned=parse_result.rows_scanned,
                elapsed_seconds=time_module.perf_counter() - file_started_at,
                download_seconds=download_seconds,
                decompress_seconds=0.0,
                parse_seconds=parse_seconds,
                match_seconds=parse_result.match_seconds,
                worker_id=str(get_ident()),
                attempts=download_attempts,
            )
        except DiskLimitExceeded as exc:
            download_seconds += time_module.perf_counter() - download_started_at
            transferred_bytes += exc.transferred_bytes
            raw_path.unlink(missing_ok=True)
            return FileProbeResult(
                index=index,
                url=url,
                status="disk_limit_gb_exceeded",
                download_attempts=download_attempts,
                retry_count=retry_count,
                transferred_bytes=transferred_bytes,
                processed_bytes=0,
                max_raw_file_bytes=max(max_raw_file_bytes, exc.transferred_bytes),
                matches=[],
                elapsed_seconds=time_module.perf_counter() - file_started_at,
                download_seconds=download_seconds,
                worker_id=str(get_ident()),
                error_type="disk_limit_gb_exceeded",
                message=str(exc),
                attempts=download_attempts,
                projected_usage_bytes=exc.projected_usage_bytes,
            )
        except MaxDownloadExceeded as exc:
            download_seconds += time_module.perf_counter() - download_started_at
            transferred_bytes += exc.transferred_bytes
            raw_path.unlink(missing_ok=True)
            return FileProbeResult(
                index=index,
                url=url,
                status="max_download_mb_exceeded",
                download_attempts=download_attempts,
                retry_count=retry_count,
                transferred_bytes=transferred_bytes,
                processed_bytes=0,
                max_raw_file_bytes=max(max_raw_file_bytes, exc.transferred_bytes),
                matches=[],
                elapsed_seconds=time_module.perf_counter() - file_started_at,
                download_seconds=download_seconds,
                worker_id=str(get_ident()),
                error_type="max_download_mb_exceeded",
                message=str(exc),
                attempts=download_attempts,
            )
        except MissingSourceFile as exc:
            download_seconds += time_module.perf_counter() - download_started_at
            transferred_bytes += exc.transferred_bytes
            raw_path.unlink(missing_ok=True)
            return FileProbeResult(
                index=index,
                url=url,
                status="missing",
                download_attempts=download_attempts,
                retry_count=retry_count,
                transferred_bytes=transferred_bytes,
                processed_bytes=0,
                max_raw_file_bytes=max_raw_file_bytes,
                matches=[],
                elapsed_seconds=time_module.perf_counter() - file_started_at,
                download_seconds=download_seconds,
                worker_id=str(get_ident()),
                error_type="HTTPError",
                message=str(exc),
                attempts=download_attempts,
            )
        except DownloadAttemptFailed as exc:
            download_seconds += time_module.perf_counter() - download_started_at
            transferred_bytes += exc.transferred_bytes
            max_raw_file_bytes = max(max_raw_file_bytes, exc.transferred_bytes)
            raw_path.unlink(missing_ok=True)
            if attempt_index >= MAX_FILE_RETRIES:
                return FileProbeResult(
                    index=index,
                    url=url,
                    status="failed",
                    download_attempts=download_attempts,
                    retry_count=retry_count,
                    transferred_bytes=transferred_bytes,
                    processed_bytes=0,
                    max_raw_file_bytes=max_raw_file_bytes,
                    matches=[],
                    elapsed_seconds=time_module.perf_counter() - file_started_at,
                    download_seconds=download_seconds,
                    worker_id=str(get_ident()),
                    error_type=exc.error_type,
                    message=str(exc),
                    attempts=download_attempts,
                )
        except TRANSIENT_FILE_ERRORS as exc:
            raw_bytes = raw_path.stat().st_size if raw_path.exists() else 0
            raw_path.unlink(missing_ok=True)
            resource_limiter.release_raw_bytes(raw_bytes)
            if attempt_index >= MAX_FILE_RETRIES:
                return FileProbeResult(
                    index=index,
                    url=url,
                    status="failed",
                    download_attempts=download_attempts,
                    retry_count=retry_count,
                    transferred_bytes=transferred_bytes,
                    processed_bytes=0,
                    max_raw_file_bytes=max_raw_file_bytes,
                    matches=[],
                    elapsed_seconds=time_module.perf_counter() - file_started_at,
                    download_seconds=download_seconds,
                    worker_id=str(get_ident()),
                    error_type=type(exc).__name__,
                    message=str(exc),
                    attempts=download_attempts,
                )

    return FileProbeResult(
        index=index,
        url=url,
        status="failed",
        download_attempts=download_attempts,
        retry_count=retry_count,
        transferred_bytes=transferred_bytes,
        processed_bytes=0,
        max_raw_file_bytes=max_raw_file_bytes,
        matches=[],
        elapsed_seconds=time_module.perf_counter() - file_started_at,
        download_seconds=download_seconds,
        worker_id=str(get_ident()),
        error_type="unknown",
        message=f"Could not process {url!r}.",
        attempts=download_attempts,
    )


def _parse_downloaded_candidate_file(
    *,
    zip_path: str,
    aliases: list[Alias],
    query_start_date: str,
    query_end_date: str,
    source_file_name: str,
) -> ParseWorkerResult:
    """Parse one already-downloaded GKG zip in a process worker."""

    parse_started_at = time_module.perf_counter()
    try:
        parse_result = parse_gkg_metadata_matches(
            Path(zip_path),
            aliases=aliases,
            query_start_date=query_start_date,
            query_end_date=query_end_date,
            source_file_name=source_file_name,
        )
    except TRANSIENT_FILE_ERRORS as exc:
        return ParseWorkerResult(
            status="failed",
            matches=[],
            rows_scanned=0,
            parse_seconds=time_module.perf_counter() - parse_started_at,
            match_seconds=0.0,
            worker_id=str(os.getpid()),
            error_type=type(exc).__name__,
            message=str(exc),
        )
    except Exception as exc:  # pragma: no cover - defensive process guard.
        return ParseWorkerResult(
            status="failed",
            matches=[],
            rows_scanned=0,
            parse_seconds=time_module.perf_counter() - parse_started_at,
            match_seconds=0.0,
            worker_id=str(os.getpid()),
            error_type=type(exc).__name__,
            message=str(exc),
        )
    return ParseWorkerResult(
        status="completed",
        matches=parse_result.matches,
        rows_scanned=parse_result.rows_scanned,
        parse_seconds=time_module.perf_counter() - parse_started_at,
        match_seconds=parse_result.match_seconds,
        worker_id=str(os.getpid()),
    )


def _completed_process_file_result(
    *,
    state: CandidateProcessState,
    downloaded_bytes: int,
    parse_result: ParseWorkerResult,
) -> FileProbeResult:
    return FileProbeResult(
        index=state.index,
        url=state.url,
        status="completed",
        download_attempts=state.download_attempts,
        retry_count=state.retry_count,
        transferred_bytes=state.transferred_bytes,
        processed_bytes=downloaded_bytes,
        max_raw_file_bytes=state.max_raw_file_bytes,
        matches=parse_result.matches,
        rows_scanned=parse_result.rows_scanned,
        elapsed_seconds=time_module.perf_counter() - state.file_started_at,
        download_seconds=state.download_seconds,
        decompress_seconds=0.0,
        parse_seconds=parse_result.parse_seconds,
        match_seconds=parse_result.match_seconds,
        worker_id=parse_result.worker_id,
        attempts=state.download_attempts,
    )


def _failed_process_file_result(
    *,
    state: CandidateProcessState,
    parse_result: ParseWorkerResult,
) -> FileProbeResult:
    return FileProbeResult(
        index=state.index,
        url=state.url,
        status="failed",
        download_attempts=state.download_attempts,
        retry_count=state.retry_count,
        transferred_bytes=state.transferred_bytes,
        processed_bytes=0,
        max_raw_file_bytes=state.max_raw_file_bytes,
        matches=[],
        rows_scanned=parse_result.rows_scanned,
        elapsed_seconds=time_module.perf_counter() - state.file_started_at,
        download_seconds=state.download_seconds,
        decompress_seconds=0.0,
        parse_seconds=parse_result.parse_seconds,
        match_seconds=parse_result.match_seconds,
        worker_id=parse_result.worker_id,
        error_type=parse_result.error_type,
        message=parse_result.message,
        attempts=state.download_attempts,
    )


def _write_csv(path: Path, rows: list[dict[str, str]], *, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _count_rows(rows: list[dict[str, str]]) -> list[dict[str, str | int]]:
    grouped: dict[tuple[str, str], dict[str, object]] = defaultdict(
        lambda: {"matched_rows": 0, "urls": set()}
    )
    for row in rows:
        _add_count_row(grouped, row)

    return _count_rows_from_grouped(grouped)


def _add_count_row(
    grouped: dict[tuple[str, str], dict[str, object]],
    row: dict[str, str],
) -> None:
    key = (row.get("date", ""), row.get("matched_ticker", ""))
    grouped_row = grouped[key]
    grouped_row["matched_rows"] = int(grouped_row["matched_rows"]) + 1
    document_identifier = row.get("document_identifier", "")
    if document_identifier:
        urls = grouped_row["urls"]
        if isinstance(urls, set):
            urls.add(document_identifier)


def _count_rows_from_grouped(
    grouped: dict[tuple[str, str], dict[str, object]],
) -> list[dict[str, str | int]]:
    output_rows: list[dict[str, str | int]] = []
    for (row_date, ticker), values in sorted(grouped.items()):
        urls = values["urls"]
        unique_urls = len(urls) if isinstance(urls, set) else 0
        output_rows.append(
            {
                "date": row_date,
                "matched_ticker": ticker,
                "matched_rows": int(values["matched_rows"]),
                "unique_urls": unique_urls,
            }
        )
    return output_rows


def _write_counts_csv(path: Path, count_rows: list[dict[str, str | int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["date", "matched_ticker", "matched_rows", "unique_urls"],
        )
        writer.writeheader()
        writer.writerows(count_rows)


def _select_sample_rows(
    rows: list[dict[str, str]],
    *,
    matched_sample_size: int,
    sample_per_ticker: int | None,
) -> list[dict[str, str]]:
    if sample_per_ticker is None:
        return rows[:matched_sample_size]
    selected: list[dict[str, str]] = []
    ticker_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        ticker = row.get("matched_ticker", "")
        if ticker_counts[ticker] >= sample_per_ticker:
            continue
        selected.append(row)
        ticker_counts[ticker] += 1
    return selected


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return round(float(median(values)), 6)


def _round_seconds(value: float) -> float:
    return round(value, 6)


def _unique_url_count(rows: list[dict[str, str]]) -> int:
    return len({row.get("document_identifier", "") for row in rows if row.get("document_identifier", "")})


def _file_result_metrics_row(result: FileProbeResult) -> dict[str, str | int | float | bool]:
    return {
        "gdelt_file": _gdelt_file_id(result.url),
        "timestamp": _gdelt_timestamp_from_url(result.url),
        "completed": result.status == "completed",
        "missing": result.status == "missing",
        "failed": result.status not in {"completed", "missing"},
        "compressed_bytes_transferred_total": result.transferred_bytes,
        "compressed_bytes_processed_successful": result.processed_bytes,
        "rows_scanned": result.rows_scanned,
        "matched_rows": len(result.matches),
        "unique_urls": _unique_url_count(result.matches),
        "elapsed_seconds": _round_seconds(result.elapsed_seconds),
        "download_seconds": _round_seconds(result.download_seconds),
        "decompress_seconds": _round_seconds(result.decompress_seconds),
        "parse_seconds": _round_seconds(result.parse_seconds),
        "match_seconds": _round_seconds(result.match_seconds),
        "worker_id": result.worker_id,
    }


def _write_per_file_metrics_csv(path: Path, results: list[FileProbeResult]) -> None:
    fieldnames = [
        "gdelt_file",
        "timestamp",
        "completed",
        "missing",
        "failed",
        "compressed_bytes_transferred_total",
        "compressed_bytes_processed_successful",
        "rows_scanned",
        "matched_rows",
        "unique_urls",
        "elapsed_seconds",
        "download_seconds",
        "decompress_seconds",
        "parse_seconds",
        "match_seconds",
        "worker_id",
    ]
    rows = [
        {key: str(value) for key, value in _file_result_metrics_row(result).items()}
        for result in sorted(results, key=lambda item: item.index)
    ]
    _write_csv(path, rows, fieldnames=fieldnames)


def _safe_shard_stem(url: str, index: int) -> str:
    stem = _safe_raw_name(url, index).removesuffix(".zip")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem)
    return f"{index:05d}_{stem}"


def _shard_path(shard_output_dir: Path, *, index: int, url: str) -> Path:
    return shard_output_dir / f"{_safe_shard_stem(url, index)}.json"


def _shard_status_for_result(result: FileProbeResult) -> str:
    if result.status == "completed":
        return "processed"
    if result.status == "missing":
        return "missing"
    return "failed"


def _shard_status_from_payload(payload: dict[str, object]) -> str:
    if "status" not in payload:
        raise GdeltRawStreamError("shard result is missing required field 'status'.")
    raw_status = payload["status"]
    if not isinstance(raw_status, str) or not raw_status:
        raise GdeltRawStreamError("shard result has malformed field 'status'.")

    derived_status = (
        "processed"
        if raw_status == "completed"
        else "missing"
        if raw_status == "missing"
        else "failed"
    )
    raw_shard_status = payload.get("shard_status")
    if raw_shard_status is None:
        return derived_status
    if raw_shard_status not in {"processed", "missing", "failed"}:
        raise GdeltRawStreamError("shard result has malformed field 'shard_status'.")
    if raw_shard_status != derived_status:
        raise GdeltRawStreamError(
            "shard result has inconsistent status fields: "
            f"status={raw_status!r}, shard_status={raw_shard_status!r}."
        )
    return str(raw_shard_status)


def _validate_shard_payload_shape(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise GdeltRawStreamError("shard result JSON must be an object.")
    for key in ("index", "url", "status", "matches", "run_fingerprint"):
        if key not in payload:
            raise GdeltRawStreamError(
                f"shard result is missing required field {key!r}."
            )
    if not isinstance(payload["matches"], list):
        raise GdeltRawStreamError("shard result has malformed field 'matches'.")
    try:
        int(payload["index"])
    except (TypeError, ValueError) as exc:
        raise GdeltRawStreamError(
            "shard result has malformed field 'index'."
        ) from exc
    if not str(payload["url"]):
        raise GdeltRawStreamError("shard result has malformed field 'url'.")
    _shard_status_from_payload(payload)
    return payload


def _candidate_identity(index: int, url: str) -> dict[str, object]:
    return {
        "candidate_index": index,
        "candidate_url": url,
        "candidate_file_name": _gdelt_file_id(url),
        "candidate_timestamp": _gdelt_timestamp_from_url(url),
    }


def _payload_candidate_identity(payload: dict[str, object]) -> dict[str, object]:
    raw_index = payload.get("candidate_index", payload.get("index", ""))
    try:
        candidate_index: object = int(raw_index)
    except (TypeError, ValueError):
        candidate_index = raw_index
    return {
        "candidate_index": candidate_index,
        "candidate_url": str(payload.get("candidate_url", payload.get("url", ""))),
        "candidate_file_name": str(
            payload.get("candidate_file_name", payload.get("gdelt_file", ""))
        ),
        "candidate_timestamp": str(
            payload.get("candidate_timestamp", payload.get("timestamp", ""))
        ),
    }


def _candidate_identity_mismatches(
    *,
    expected_index: int,
    expected_url: str,
    payload: dict[str, object],
) -> list[str]:
    expected = _candidate_identity(expected_index, expected_url)
    actual = _payload_candidate_identity(payload)
    mismatches: list[str] = []
    for key in ("candidate_index", "candidate_url", "candidate_file_name"):
        if expected[key] != actual[key]:
            mismatches.append(
                f"{key}: expected {expected[key]!r}, actual {actual[key]!r}"
            )
    if expected["candidate_timestamp"] != actual["candidate_timestamp"]:
        mismatches.append(
            "candidate_timestamp: "
            f"expected {expected['candidate_timestamp']!r}, "
            f"actual {actual['candidate_timestamp']!r}"
        )
    return mismatches


def _format_candidate_identity_error(
    *,
    path: Path,
    expected_index: int,
    expected_url: str,
    payload: dict[str, object],
    mismatches: list[str],
) -> str:
    expected = _candidate_identity(expected_index, expected_url)
    actual = _payload_candidate_identity(payload)
    return (
        f"Shard candidate identity mismatch for {path}: "
        f"expected candidate {expected}; actual candidate {actual}; "
        f"mismatches: {'; '.join(mismatches)}."
    )


def _load_shard_payload(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GdeltRawStreamError(
            f"Malformed shard result for {path}: {type(exc).__name__}: {exc}."
        ) from exc
    try:
        return _validate_shard_payload_shape(payload)
    except GdeltRawStreamError as exc:
        raise GdeltRawStreamError(f"Malformed shard result for {path}: {exc}") from exc


def _failed_shard_merge_error(path: Path, result: FileProbeResult) -> GdeltRawStreamError:
    return GdeltRawStreamError(
        f"Cannot merge failed shard result {path} with status {result.status!r}. "
        "Rerun without --merge-only or use --resume so the failed shard can be "
        "recomputed."
    )


def _file_result_to_dict(result: FileProbeResult) -> dict[str, object]:
    identity = _candidate_identity(result.index, result.url)
    return {
        "index": result.index,
        "url": result.url,
        **identity,
        "gdelt_file": _gdelt_file_id(result.url),
        "timestamp": _gdelt_timestamp_from_url(result.url),
        "status": result.status,
        "shard_status": _shard_status_for_result(result),
        "download_attempts": result.download_attempts,
        "retry_count": result.retry_count,
        "transferred_bytes": result.transferred_bytes,
        "processed_bytes": result.processed_bytes,
        "max_raw_file_bytes": result.max_raw_file_bytes,
        "rows_scanned": result.rows_scanned,
        "elapsed_seconds": result.elapsed_seconds,
        "download_seconds": result.download_seconds,
        "decompress_seconds": result.decompress_seconds,
        "parse_seconds": result.parse_seconds,
        "match_seconds": result.match_seconds,
        "worker_id": result.worker_id,
        "error_type": result.error_type,
        "message": result.message,
        "attempts": result.attempts,
        "projected_usage_bytes": result.projected_usage_bytes,
        "matched_rows": len(result.matches),
        "unique_urls": _unique_url_count(result.matches),
        "matches": result.matches,
    }


def _file_result_from_dict(payload: dict[str, object]) -> FileProbeResult:
    matches = payload.get("matches", [])
    if not isinstance(matches, list):
        matches = []
    return FileProbeResult(
        index=int(payload.get("index", 0)),
        url=str(payload.get("url", "")),
        status=str(payload.get("status", "failed")),
        download_attempts=int(payload.get("download_attempts", 0)),
        retry_count=int(payload.get("retry_count", 0)),
        transferred_bytes=int(payload.get("transferred_bytes", 0)),
        processed_bytes=int(payload.get("processed_bytes", 0)),
        max_raw_file_bytes=int(payload.get("max_raw_file_bytes", 0)),
        matches=[row for row in matches if isinstance(row, dict)],
        rows_scanned=int(payload.get("rows_scanned", 0)),
        elapsed_seconds=float(payload.get("elapsed_seconds", 0.0)),
        download_seconds=float(payload.get("download_seconds", 0.0)),
        decompress_seconds=float(payload.get("decompress_seconds", 0.0)),
        parse_seconds=float(payload.get("parse_seconds", 0.0)),
        match_seconds=float(payload.get("match_seconds", 0.0)),
        worker_id=str(payload.get("worker_id", "")),
        error_type=str(payload.get("error_type", "")),
        message=str(payload.get("message", "")),
        attempts=int(payload.get("attempts", 0)),
        projected_usage_bytes=(
            int(payload["projected_usage_bytes"])
            if payload.get("projected_usage_bytes") is not None
            else None
        ),
    )


def _write_shard_result(
    path: Path,
    result: FileProbeResult,
    *,
    run_fingerprint: dict[str, object],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        payload = _file_result_to_dict(result)
        payload["run_fingerprint"] = run_fingerprint
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temp_path.replace(path)


def _read_shard_result(path: Path) -> FileProbeResult:
    return _file_result_from_dict(_load_shard_payload(path))


def _read_validated_shard_result(
    path: Path,
    *,
    expected_fingerprint: dict[str, object],
    expected_index: int,
    expected_url: str,
) -> FileProbeResult:
    payload = _load_shard_payload(path)
    mismatches = _fingerprint_mismatches(
        expected=expected_fingerprint,
        observed=payload.get("run_fingerprint"),
    )
    if mismatches:
        raise GdeltRawStreamError(
            _format_shard_fingerprint_error(path=path, mismatches=mismatches)
        )
    identity_mismatches = _candidate_identity_mismatches(
        expected_index=expected_index,
        expected_url=expected_url,
        payload=payload,
    )
    if identity_mismatches:
        raise GdeltRawStreamError(
            _format_candidate_identity_error(
                path=path,
                expected_index=expected_index,
                expected_url=expected_url,
                payload=payload,
                mismatches=identity_mismatches,
            )
        )
    result = _file_result_from_dict(payload)
    if result.status not in REUSABLE_SHARD_STATUSES:
        raise _failed_shard_merge_error(path, result)
    return result


def _try_read_resume_shard_result(
    path: Path,
    *,
    expected_fingerprint: dict[str, object],
    expected_index: int,
    expected_url: str,
) -> FileProbeResult | None:
    try:
        payload = _load_shard_payload(path)
    except GdeltRawStreamError as exc:
        print(
            "GDELT probe resume: recomputing malformed shard: "
            f"{path}: {exc}",
            file=sys.stderr,
        )
        return None
    mismatches = _fingerprint_mismatches(
        expected=expected_fingerprint,
        observed=payload.get("run_fingerprint"),
    )
    if mismatches:
        print(
            "GDELT probe resume: recomputing shard with mismatched fingerprint: "
            f"{_format_shard_fingerprint_error(path=path, mismatches=mismatches)}",
            file=sys.stderr,
        )
        return None
    identity_mismatches = _candidate_identity_mismatches(
        expected_index=expected_index,
        expected_url=expected_url,
        payload=payload,
    )
    if identity_mismatches:
        error_message = _format_candidate_identity_error(
            path=path,
            expected_index=expected_index,
            expected_url=expected_url,
            payload=payload,
            mismatches=identity_mismatches,
        )
        print(
            "GDELT probe resume: recomputing shard with mismatched candidate "
            f"identity: {error_message}",
            file=sys.stderr,
        )
        return None
    result = _file_result_from_dict(payload)
    if result.status not in REUSABLE_SHARD_STATUSES:
        print(
            "GDELT probe resume: recomputing failed shard: "
            f"{path}: status={result.status!r}.",
            file=sys.stderr,
        )
        return None
    return result


def _summed_existing_file_size(paths: Iterable[Path]) -> int:
    return sum(path.stat().st_size for path in paths if path.exists())


def _tree_file_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(child.stat().st_size for child in path.rglob("*") if child.is_file())


def _write_summary(path: Path, summary: dict[str, object], outputs: list[Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(3):
        path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        size = _summed_existing_file_size(outputs)
        if summary.get("output_file_size_bytes") == size:
            return
        summary["output_file_size_bytes"] = size


def estimate_full_window_download_size(
    *,
    compressed_bytes_downloaded: int,
    files_downloaded: int,
    full_window_start_date: str,
    full_window_end_date: str,
) -> dict[str, float | int | None]:
    """Estimate full-window compressed transfer from observed downloaded files."""

    full_window_file_count = len(
        interval_timestamps(full_window_start_date, full_window_end_date)
    )
    if files_downloaded == 0:
        return {
            "basis": "no_downloaded_files",
            "bytes": None,
            "gb": None,
            "full_window_file_count": full_window_file_count,
        }
    average_bytes = compressed_bytes_downloaded / files_downloaded
    estimated_bytes = int(average_bytes * full_window_file_count)
    return {
        "basis": "sample_average_compressed_bytes_per_file",
        "bytes": estimated_bytes,
        "gb": round(estimated_bytes / 1_000_000_000, 3),
        "full_window_file_count": full_window_file_count,
        "sample_average_bytes_per_file": round(average_bytes, 2),
    }


def run_stream_probe(
    *,
    start_date: str,
    end_date: str,
    aliases: list[Alias],
    max_files: int = DEFAULT_MAX_FILES,
    max_download_mb: float = DEFAULT_MAX_DOWNLOAD_MB,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    keep_raw: bool = False,
    disk_limit_gb: float = DEFAULT_DISK_LIMIT_GB,
    max_missing_files: int = DEFAULT_MAX_MISSING_FILES,
    full_window_start_date: str = PROJECT_WINDOW_START,
    full_window_end_date: str = PROJECT_WINDOW_END,
    source_urls: list[str] | None = None,
    repo_root: Path = REPO_ROOT,
    alias_file_path: str | Path | None = None,
    workers: int = DEFAULT_WORKERS,
    worker_backend: str = "thread",
    matched_sample_size: int = DEFAULT_MATCHED_SAMPLE_SIZE,
    sample_per_ticker: int | None = None,
    profile_performance: bool = False,
    shard_output_dir: str | Path | None = None,
    resume: bool = False,
    merge_only: bool = False,
    progress_interval_seconds: float = DEFAULT_PROGRESS_INTERVAL_SECONDS,
) -> dict[str, object]:
    """Execute a bounded streaming GDELT raw GKG probe."""

    if max_download_mb <= 0:
        raise GdeltRawStreamError("max_download_mb must be positive.")
    if disk_limit_gb <= 0:
        raise GdeltRawStreamError("disk_limit_gb must be positive.")
    if max_missing_files < 0:
        raise GdeltRawStreamError("max_missing_files must be non-negative.")
    if matched_sample_size < 0:
        raise GdeltRawStreamError("matched_sample_size must be non-negative.")
    if sample_per_ticker is not None and sample_per_ticker < 1:
        raise GdeltRawStreamError("sample_per_ticker must be positive when set.")
    if progress_interval_seconds < 0:
        raise GdeltRawStreamError("progress_interval_seconds must be non-negative.")
    workers = validate_workers(workers)
    worker_backend = validate_worker_backend(worker_backend)
    if merge_only and shard_output_dir is None:
        raise GdeltRawStreamError("--merge-only requires --shard-output-dir.")
    if resume and shard_output_dir is None:
        raise GdeltRawStreamError("--resume requires --shard-output-dir.")
    if keep_raw and workers > 1:
        raise GdeltRawStreamError(
            "--keep-raw with --workers > 1 is not supported because retained "
            "raw-file disk accounting is intentionally conservative; rerun with "
            "--workers 1 or omit --keep-raw."
        )

    output_path = validate_local_data_path(output_dir, repo_root=repo_root)
    raw_keep_dir = validate_local_data_path(DEFAULT_RAW_DIR, repo_root=repo_root)
    temp_raw_parent = validate_local_data_path(DEFAULT_TEMP_RAW_DIR, repo_root=repo_root)
    shard_path = (
        validate_local_data_path(shard_output_dir, repo_root=repo_root)
        if shard_output_dir is not None
        else None
    )
    disk_limit_bytes = int(disk_limit_gb * 1_000_000_000)

    if source_urls is None:
        urls, uncapped_file_count = candidate_gkg_urls(
            start_date=start_date,
            end_date=end_date,
            max_files=max_files,
        )
    else:
        if max_files < 1 or max_files > MAX_ALLOWED_FILES:
            raise GdeltRawStreamError(
                f"max_files must be between 1 and {MAX_ALLOWED_FILES}; got {max_files}."
            )
        urls = source_urls[:max_files]
        uncapped_file_count = len(source_urls)

    output_path.mkdir(parents=True, exist_ok=True)
    if shard_path is not None:
        shard_path.mkdir(parents=True, exist_ok=True)
    if keep_raw:
        raw_keep_dir.mkdir(parents=True, exist_ok=True)
    else:
        temp_raw_parent.mkdir(parents=True, exist_ok=True)

    sample_path = output_path / "matched_metadata_sample.csv"
    counts_path = output_path / "stock_day_counts.csv"
    summary_path = output_path / "probe_summary.json"
    per_file_metrics_path = output_path / "per_file_metrics.csv"
    output_files = [sample_path, counts_path, summary_path]
    if profile_performance:
        output_files.append(per_file_metrics_path)
    run_fingerprint = build_run_fingerprint(
        aliases=aliases,
        start_date=start_date,
        end_date=end_date,
        matched_sample_size=matched_sample_size,
        sample_per_ticker=sample_per_ticker,
        alias_file_path=alias_file_path,
    )

    started_at = time_module.perf_counter()
    max_download_bytes = int(max_download_mb * 1_000_000)
    compressed_bytes_transferred_total = 0
    compressed_bytes_processed_successful = 0
    files_attempted = 0
    download_attempts = 0
    retry_count = 0
    files_processed = 0
    files_failed = 0
    failed_files: list[dict[str, str | int]] = []
    files_missing = 0
    missing_files: list[dict[str, str]] = []
    missing_file_threshold_exceeded = False
    missing_failure_reason = ""
    max_raw_file_bytes = 0
    max_disk_usage_observed = _tree_file_size(output_path)
    disk_limit_exceeded = False
    disk_failure_reason = ""
    disk_usage_bytes_at_failure: int | None = None
    max_download_exceeded = False
    transfer_failure_reason = ""
    transfer_bytes_at_failure: int | None = None
    total_matched_rows = 0
    all_matched_rows: list[dict[str, str]] = []
    grouped_counts: dict[tuple[str, str], dict[str, object]] = defaultdict(
        lambda: {"matched_rows": 0, "urls": set()}
    )
    unique_urls: set[str] = set()
    file_results: list[FileProbeResult] = []
    merge_seconds = 0.0

    temp_context = (
        tempfile.TemporaryDirectory(dir=temp_raw_parent) if not keep_raw else None
    )
    raw_work_dir = (
        Path(temp_context.name) if temp_context is not None else raw_keep_dir
    )
    initial_disk_usage = _tree_file_size(output_path) + _tree_file_size(
        raw_keep_dir if keep_raw else temp_raw_parent
    )
    resource_limiter = ProbeResourceLimiter(
        max_download_bytes=max_download_bytes,
        disk_limit_bytes=disk_limit_bytes,
        disk_usage_base_bytes=initial_disk_usage,
    )

    def record_disk_limit_failure(
        *,
        url: str,
        message: str,
        attempts: int,
        projected_usage_bytes: int,
    ) -> None:
        nonlocal disk_limit_exceeded
        nonlocal disk_failure_reason
        nonlocal disk_usage_bytes_at_failure
        nonlocal files_failed
        nonlocal max_disk_usage_observed

        disk_limit_exceeded = True
        disk_failure_reason = "disk_limit_gb_exceeded"
        disk_usage_bytes_at_failure = projected_usage_bytes
        max_disk_usage_observed = max(max_disk_usage_observed, projected_usage_bytes)
        files_failed += 1
        if len(failed_files) < MAX_FAILED_FILES_RECORDED:
            failed_files.append(
                {
                    "url": url,
                    "error_type": "disk_limit_gb_exceeded",
                    "message": message,
                    "attempts": attempts,
                }
            )

    def record_max_download_failure(
        *,
        url: str,
        message: str,
        attempts: int,
    ) -> None:
        nonlocal max_download_exceeded
        nonlocal transfer_failure_reason
        nonlocal transfer_bytes_at_failure
        nonlocal files_failed

        max_download_exceeded = True
        transfer_failure_reason = "max_download_mb_exceeded"
        transfer_bytes_at_failure = compressed_bytes_transferred_total
        files_failed += 1
        if len(failed_files) < MAX_FAILED_FILES_RECORDED:
            failed_files.append(
                {
                    "url": url,
                    "error_type": "max_download_mb_exceeded",
                    "message": message,
                    "attempts": attempts,
                }
            )

    def record_missing_file(*, url: str, message: str) -> None:
        nonlocal files_missing

        files_missing += 1
        if len(missing_files) < MAX_MISSING_FILES_RECORDED:
            missing_files.append(
                {
                    "url": url,
                    "file_id": _gdelt_file_id(url),
                    "timestamp": _gdelt_timestamp_from_url(url),
                    "message": message,
                }
            )

    def record_failed_file(result: FileProbeResult) -> None:
        nonlocal files_failed

        files_failed += 1
        if len(failed_files) < MAX_FAILED_FILES_RECORDED:
            failed_files.append(
                {
                    "url": result.url,
                    "error_type": result.error_type,
                    "message": result.message,
                    "attempts": result.attempts,
                }
            )

    def merge_file_result(result: FileProbeResult) -> bool:
        nonlocal compressed_bytes_transferred_total
        nonlocal compressed_bytes_processed_successful
        nonlocal download_attempts
        nonlocal retry_count
        nonlocal files_processed
        nonlocal missing_file_threshold_exceeded
        nonlocal missing_failure_reason
        nonlocal max_raw_file_bytes
        nonlocal total_matched_rows

        compressed_bytes_transferred_total += result.transferred_bytes
        download_attempts += result.download_attempts
        retry_count += result.retry_count
        max_raw_file_bytes = max(max_raw_file_bytes, result.max_raw_file_bytes)

        if result.status == "completed":
            files_processed += 1
            compressed_bytes_processed_successful += result.processed_bytes
            total_matched_rows += len(result.matches)
            for row in result.matches:
                _add_count_row(grouped_counts, row)
                document_identifier = row.get("document_identifier", "")
                if document_identifier:
                    unique_urls.add(document_identifier)
            all_matched_rows.extend(result.matches)
            return False

        if result.status == "missing":
            record_missing_file(url=result.url, message=result.message)
            if files_missing > max_missing_files:
                missing_file_threshold_exceeded = True
                missing_failure_reason = "missing_file_threshold_exceeded"
                return True
            return False

        if result.status == "disk_limit_gb_exceeded":
            record_disk_limit_failure(
                url=result.url,
                message=result.message,
                attempts=result.attempts,
                projected_usage_bytes=(
                    result.projected_usage_bytes
                    if result.projected_usage_bytes is not None
                    else disk_limit_bytes
                ),
            )
            return True

        if result.status == "max_download_mb_exceeded":
            record_max_download_failure(
                url=result.url,
                message=result.message,
                attempts=result.attempts,
            )
            return True

        record_failed_file(result)
        return True

    def emit_progress(completed_count: int, in_flight_count: int, *, force: bool = False) -> None:
        nonlocal last_progress_at

        if progress_interval_seconds == 0:
            return
        now = time_module.perf_counter()
        if not force and now - last_progress_at < progress_interval_seconds:
            return
        elapsed = max(now - started_at, 0.000001)
        files_per_second = completed_count / elapsed
        average_seconds_per_file = elapsed / completed_count if completed_count else 0.0
        print(
            "GDELT probe progress: "
            f"completed={completed_count}/{len(urls)} "
            f"in_flight={in_flight_count} "
            f"files_per_sec={files_per_second:.4f} "
            f"avg_sec_per_file={average_seconds_per_file:.3f} "
            f"elapsed_sec={elapsed:.1f}",
            file=sys.stderr,
        )
        last_progress_at = now

    def append_file_result(result: FileProbeResult) -> bool:
        file_results.append(result)
        if shard_path is not None:
            _write_shard_result(
                _shard_path(shard_path, index=result.index, url=result.url),
                result,
                run_fingerprint=run_fingerprint,
            )
        if result.status not in {"completed", "missing"}:
            return True
        missing_results = sum(item.status == "missing" for item in file_results)
        return missing_results > max_missing_files

    last_progress_at = started_at

    try:
        if merge_only:
            if shard_path is None:
                raise GdeltRawStreamError("--merge-only requires --shard-output-dir.")
            missing_shards: list[str] = []
            for index, url in enumerate(urls, start=1):
                expected_shard = _shard_path(shard_path, index=index, url=url)
                if not expected_shard.exists():
                    missing_shards.append(str(expected_shard))
                    continue
                file_results.append(
                    _read_validated_shard_result(
                        expected_shard,
                        expected_fingerprint=run_fingerprint,
                        expected_index=index,
                        expected_url=url,
                    )
                )
            if missing_shards:
                preview = ", ".join(missing_shards[:5])
                raise GdeltRawStreamError(
                    "--merge-only requires one shard result per candidate file; "
                    f"missing {len(missing_shards)} shard(s): {preview}."
                )
            files_attempted = len(file_results)
        else:
            pending_inputs: list[tuple[int, str]] = []
            if resume and shard_path is not None:
                for index, url in enumerate(urls, start=1):
                    expected_shard = _shard_path(shard_path, index=index, url=url)
                    if expected_shard.exists():
                        result = _try_read_resume_shard_result(
                            expected_shard,
                            expected_fingerprint=run_fingerprint,
                            expected_index=index,
                            expected_url=url,
                        )
                        if result is None:
                            pending_inputs.append((index, url))
                        else:
                            file_results.append(result)
                            files_attempted += 1
                    else:
                        pending_inputs.append((index, url))
            else:
                pending_inputs = list(enumerate(urls, start=1))

            next_pending_index = 0
            stop_submitting = False
            if worker_backend == "thread":
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    future_to_input: dict[object, tuple[int, str]] = {}

                    def submit_next_thread() -> bool:
                        nonlocal files_attempted
                        nonlocal next_pending_index

                        if next_pending_index >= len(pending_inputs):
                            return False
                        index, url = pending_inputs[next_pending_index]
                        next_pending_index += 1
                        files_attempted += 1
                        future = executor.submit(
                            _process_candidate_file,
                            index=index,
                            url=url,
                            raw_work_dir=raw_work_dir,
                            aliases=aliases,
                            query_start_date=start_date,
                            query_end_date=end_date,
                            keep_raw=keep_raw,
                            max_download_bytes=max_download_bytes,
                            resource_limiter=resource_limiter,
                        )
                        future_to_input[future] = (index, url)
                        return True

                    for _ in range(min(workers, len(pending_inputs))):
                        submit_next_thread()

                    while future_to_input:
                        done, _ = wait(
                            future_to_input,
                            return_when=FIRST_COMPLETED,
                        )
                        for future in done:
                            index, url = future_to_input.pop(future)
                            try:
                                result = future.result()
                            except Exception as exc:  # pragma: no cover - defensive guard.
                                result = FileProbeResult(
                                    index=index,
                                    url=url,
                                    status="failed",
                                    download_attempts=0,
                                    retry_count=0,
                                    transferred_bytes=0,
                                    processed_bytes=0,
                                    max_raw_file_bytes=0,
                                    matches=[],
                                    elapsed_seconds=0.0,
                                    error_type=type(exc).__name__,
                                    message=str(exc),
                                    attempts=0,
                                )
                            if append_file_result(result):
                                stop_submitting = True
                            emit_progress(len(file_results), len(future_to_input))
                        while (
                            not stop_submitting
                            and len(future_to_input) < workers
                            and submit_next_thread()
                        ):
                            continue
                    emit_progress(len(file_results), 0, force=True)
            else:
                try:
                    executor = ProcessPoolExecutor(max_workers=workers)
                except Exception as exc:
                    raise _process_backend_error(phase="start", exc=exc) from exc
                with executor:
                    future_to_parse: dict[object, tuple[CandidateProcessState, Path, int]] = {}

                    def download_for_process_parse(
                        state: CandidateProcessState,
                    ) -> tuple[Path, int] | FileProbeResult:
                        raw_name = _safe_raw_name(state.url, state.index)
                        raw_path = (
                            raw_work_dir / raw_name
                            if keep_raw
                            else raw_work_dir / f"{state.index:05d}_{raw_name}"
                        )
                        while state.download_attempts <= MAX_FILE_RETRIES:
                            if state.download_attempts > 0:
                                state.retry_count += 1
                            state.download_attempts += 1
                            try:
                                download_started_at = time_module.perf_counter()
                                downloaded_bytes = download_to_path(
                                    state.url,
                                    raw_path,
                                    remaining_bytes=max_download_bytes,
                                    resource_limiter=resource_limiter,
                                )
                                state.download_seconds += (
                                    time_module.perf_counter() - download_started_at
                                )
                                state.transferred_bytes += downloaded_bytes
                                state.max_raw_file_bytes = max(
                                    state.max_raw_file_bytes,
                                    downloaded_bytes,
                                )
                                return raw_path, downloaded_bytes
                            except DiskLimitExceeded as exc:
                                state.download_seconds += (
                                    time_module.perf_counter() - download_started_at
                                )
                                state.transferred_bytes += exc.transferred_bytes
                                raw_path.unlink(missing_ok=True)
                                return FileProbeResult(
                                    index=state.index,
                                    url=state.url,
                                    status="disk_limit_gb_exceeded",
                                    download_attempts=state.download_attempts,
                                    retry_count=state.retry_count,
                                    transferred_bytes=state.transferred_bytes,
                                    processed_bytes=0,
                                    max_raw_file_bytes=max(
                                        state.max_raw_file_bytes,
                                        exc.transferred_bytes,
                                    ),
                                    matches=[],
                                    elapsed_seconds=(
                                        time_module.perf_counter()
                                        - state.file_started_at
                                    ),
                                    download_seconds=state.download_seconds,
                                    worker_id=str(os.getpid()),
                                    error_type="disk_limit_gb_exceeded",
                                    message=str(exc),
                                    attempts=state.download_attempts,
                                    projected_usage_bytes=exc.projected_usage_bytes,
                                )
                            except MaxDownloadExceeded as exc:
                                state.download_seconds += (
                                    time_module.perf_counter() - download_started_at
                                )
                                state.transferred_bytes += exc.transferred_bytes
                                raw_path.unlink(missing_ok=True)
                                return FileProbeResult(
                                    index=state.index,
                                    url=state.url,
                                    status="max_download_mb_exceeded",
                                    download_attempts=state.download_attempts,
                                    retry_count=state.retry_count,
                                    transferred_bytes=state.transferred_bytes,
                                    processed_bytes=0,
                                    max_raw_file_bytes=max(
                                        state.max_raw_file_bytes,
                                        exc.transferred_bytes,
                                    ),
                                    matches=[],
                                    elapsed_seconds=(
                                        time_module.perf_counter()
                                        - state.file_started_at
                                    ),
                                    download_seconds=state.download_seconds,
                                    worker_id=str(os.getpid()),
                                    error_type="max_download_mb_exceeded",
                                    message=str(exc),
                                    attempts=state.download_attempts,
                                )
                            except MissingSourceFile as exc:
                                state.download_seconds += (
                                    time_module.perf_counter() - download_started_at
                                )
                                state.transferred_bytes += exc.transferred_bytes
                                raw_path.unlink(missing_ok=True)
                                return FileProbeResult(
                                    index=state.index,
                                    url=state.url,
                                    status="missing",
                                    download_attempts=state.download_attempts,
                                    retry_count=state.retry_count,
                                    transferred_bytes=state.transferred_bytes,
                                    processed_bytes=0,
                                    max_raw_file_bytes=state.max_raw_file_bytes,
                                    matches=[],
                                    elapsed_seconds=(
                                        time_module.perf_counter()
                                        - state.file_started_at
                                    ),
                                    download_seconds=state.download_seconds,
                                    worker_id=str(os.getpid()),
                                    error_type="HTTPError",
                                    message=str(exc),
                                    attempts=state.download_attempts,
                                )
                            except DownloadAttemptFailed as exc:
                                state.download_seconds += (
                                    time_module.perf_counter() - download_started_at
                                )
                                state.transferred_bytes += exc.transferred_bytes
                                state.max_raw_file_bytes = max(
                                    state.max_raw_file_bytes,
                                    exc.transferred_bytes,
                                )
                                raw_path.unlink(missing_ok=True)
                                if state.download_attempts > MAX_FILE_RETRIES:
                                    return FileProbeResult(
                                        index=state.index,
                                        url=state.url,
                                        status="failed",
                                        download_attempts=state.download_attempts,
                                        retry_count=state.retry_count,
                                        transferred_bytes=state.transferred_bytes,
                                        processed_bytes=0,
                                        max_raw_file_bytes=state.max_raw_file_bytes,
                                        matches=[],
                                        elapsed_seconds=(
                                            time_module.perf_counter()
                                            - state.file_started_at
                                        ),
                                        download_seconds=state.download_seconds,
                                        worker_id=str(os.getpid()),
                                        error_type=exc.error_type,
                                        message=str(exc),
                                        attempts=state.download_attempts,
                                    )
                                continue

                        return FileProbeResult(
                            index=state.index,
                            url=state.url,
                            status="failed",
                            download_attempts=state.download_attempts,
                            retry_count=state.retry_count,
                            transferred_bytes=state.transferred_bytes,
                            processed_bytes=0,
                            max_raw_file_bytes=state.max_raw_file_bytes,
                            matches=[],
                            elapsed_seconds=(
                                time_module.perf_counter() - state.file_started_at
                            ),
                            download_seconds=state.download_seconds,
                            worker_id=str(os.getpid()),
                            error_type="unknown",
                            message=f"Could not download {state.url!r}.",
                            attempts=state.download_attempts,
                        )

                    def submit_process_state(state: CandidateProcessState) -> bool:
                        nonlocal stop_submitting

                        download_result = download_for_process_parse(state)
                        if isinstance(download_result, FileProbeResult):
                            if append_file_result(download_result):
                                stop_submitting = True
                            emit_progress(len(file_results), len(future_to_parse))
                            return False
                        raw_path, downloaded_bytes = download_result
                        try:
                            future = executor.submit(
                                _parse_downloaded_candidate_file,
                                zip_path=str(raw_path),
                                aliases=aliases,
                                query_start_date=start_date,
                                query_end_date=end_date,
                                source_file_name=_gdelt_file_id(state.url),
                            )
                        except Exception as exc:
                            if not keep_raw:
                                raw_path.unlink(missing_ok=True)
                                resource_limiter.release_raw_bytes(downloaded_bytes)
                            raise _process_backend_error(
                                phase="submit work",
                                exc=exc,
                            ) from exc
                        future_to_parse[future] = (state, raw_path, downloaded_bytes)
                        return True

                    def submit_next_process() -> bool:
                        nonlocal files_attempted
                        nonlocal next_pending_index

                        while next_pending_index < len(pending_inputs):
                            index, url = pending_inputs[next_pending_index]
                            next_pending_index += 1
                            files_attempted += 1
                            state = CandidateProcessState(
                                index=index,
                                url=url,
                                file_started_at=time_module.perf_counter(),
                            )
                            if submit_process_state(state):
                                return True
                            if stop_submitting:
                                return False
                        return False

                    for _ in range(min(workers, len(pending_inputs))):
                        if stop_submitting or not submit_next_process():
                            break

                    while future_to_parse:
                        done, _ = wait(
                            future_to_parse,
                            return_when=FIRST_COMPLETED,
                        )
                        for future in done:
                            state, raw_path, downloaded_bytes = future_to_parse.pop(
                                future
                            )
                            try:
                                parse_result = future.result()
                            except Exception as exc:  # pragma: no cover - defensive guard.
                                parse_result = ParseWorkerResult(
                                    status="failed",
                                    matches=[],
                                    rows_scanned=0,
                                    parse_seconds=0.0,
                                    match_seconds=0.0,
                                    worker_id="",
                                    error_type=type(exc).__name__,
                                    message=str(exc),
                                )
                            if parse_result.status == "completed":
                                if not keep_raw:
                                    raw_path.unlink(missing_ok=True)
                                    resource_limiter.release_raw_bytes(
                                        downloaded_bytes
                                    )
                                result = _completed_process_file_result(
                                    state=state,
                                    downloaded_bytes=downloaded_bytes,
                                    parse_result=parse_result,
                                )
                                if append_file_result(result):
                                    stop_submitting = True
                            else:
                                raw_path.unlink(missing_ok=True)
                                resource_limiter.release_raw_bytes(downloaded_bytes)
                                if state.download_attempts > MAX_FILE_RETRIES:
                                    result = _failed_process_file_result(
                                        state=state,
                                        parse_result=parse_result,
                                    )
                                    if append_file_result(result):
                                        stop_submitting = True
                                elif not stop_submitting:
                                    submit_process_state(state)
                            emit_progress(len(file_results), len(future_to_parse))
                        while (
                            not stop_submitting
                            and len(future_to_parse) < workers
                            and submit_next_process()
                        ):
                            continue
                    emit_progress(len(file_results), 0, force=True)

        merge_started_at = time_module.perf_counter()
        for result in sorted(file_results, key=lambda item: item.index):
            merge_file_result(result)
        merge_seconds = time_module.perf_counter() - merge_started_at
    finally:
        if temp_context is not None:
            temp_context.cleanup()

    max_disk_usage_observed = max(
        max_disk_usage_observed,
        resource_limiter.max_disk_usage_observed,
    )

    metadata_fields = [
        "gkg_record_id",
        "timestamp",
        "date",
        "source_collection_identifier",
        "source_common_name",
        "document_identifier",
        "matched_ticker",
        "matched_company_alias",
        "matched_alias",
        "matched_alias_type",
        "matched_field_name",
        "matched_text_excerpt",
        "query_start_date",
        "query_end_date",
        "query_method",
        "gdelt_file",
    ]
    matched_rows = _select_sample_rows(
        all_matched_rows,
        matched_sample_size=matched_sample_size,
        sample_per_ticker=sample_per_ticker,
    )
    _write_csv(sample_path, matched_rows, fieldnames=metadata_fields)
    _write_counts_csv(counts_path, _count_rows_from_grouped(grouped_counts))
    if profile_performance:
        _write_per_file_metrics_csv(per_file_metrics_path, file_results)

    elapsed_seconds = round(time_module.perf_counter() - started_at, 3)
    output_file_size_bytes = _summed_existing_file_size(output_files)
    retained_raw_bytes = _tree_file_size(raw_keep_dir) if keep_raw else 0
    streaming_peak_disk_usage_bytes = (
        output_file_size_bytes + retained_raw_bytes
        if keep_raw
        else output_file_size_bytes + max_raw_file_bytes
    )
    peak_disk_usage_bytes = max(
        max_disk_usage_observed,
        streaming_peak_disk_usage_bytes,
        output_file_size_bytes + retained_raw_bytes,
    )
    estimated_full_window = estimate_full_window_download_size(
        compressed_bytes_downloaded=compressed_bytes_processed_successful,
        files_downloaded=files_processed,
        full_window_start_date=full_window_start_date,
        full_window_end_date=full_window_end_date,
    )
    if files_processed:
        retry_overhead_ratio = round(
            compressed_bytes_transferred_total
            / compressed_bytes_processed_successful,
            6,
        )
    else:
        retry_overhead_ratio = None
    full_year_feasible_under_disk_limit = (
        peak_disk_usage_bytes <= disk_limit_bytes
        and not keep_raw
        and not disk_limit_exceeded
    )
    missing_file_ratio = files_missing / len(urls) if urls else 0.0
    completed = files_failed == 0 and not disk_limit_exceeded
    completed = completed and not max_download_exceeded
    completed = completed and not missing_file_threshold_exceeded
    elapsed_values = [result.elapsed_seconds for result in file_results]
    download_values = [result.download_seconds for result in file_results]
    parse_values = [result.parse_seconds for result in file_results]
    slowest_files = [
        {
            "gdelt_file": _gdelt_file_id(result.url),
            "timestamp": _gdelt_timestamp_from_url(result.url),
            "status": result.status,
            "elapsed_seconds": _round_seconds(result.elapsed_seconds),
        }
        for result in sorted(
            file_results,
            key=lambda item: item.elapsed_seconds,
            reverse=True,
        )[:SLOWEST_FILES_RECORDED]
    ]
    output_file_map = {
        "probe_summary": str(summary_path),
        "matched_metadata_sample": str(sample_path),
        "stock_day_counts": str(counts_path),
    }
    if profile_performance:
        output_file_map["per_file_metrics"] = str(per_file_metrics_path)

    summary: dict[str, object] = {
        "query_method": QUERY_METHOD,
        "start_date": start_date,
        "end_date": end_date,
        "candidate_file_count_uncapped": uncapped_file_count,
        "candidate_file_count_capped": len(urls),
        "files_attempted": files_attempted,
        "download_attempts": download_attempts,
        "retry_count": retry_count,
        "files_processed": files_processed,
        "files_failed": files_failed,
        "failed_files": failed_files,
        "files_missing": files_missing,
        "missing_files": missing_files,
        "missing_file_ratio": round(missing_file_ratio, 6),
        "max_missing_files": max_missing_files,
        "missing_file_threshold_exceeded": missing_file_threshold_exceeded,
        "missing_failure_reason": missing_failure_reason,
        "workers": workers,
        "worker_backend": worker_backend,
        "worker_backend_detail": (
            "thread_pool" if worker_backend == "thread" else "process_pool"
        ),
        "progress_mode": "continuous_bounded_executor",
        "scheduling_note": (
            "Workers are kept fed continuously; process backend downloads raw "
            "zips in the parent process before parse/match workers receive "
            "local temp paths. Final outputs are merged in candidate-file "
            "order for deterministic counts and samples."
        ),
        "matched_sample_size": matched_sample_size,
        "sample_per_ticker": sample_per_ticker,
        "profile_performance": profile_performance,
        "shard_output_dir": str(shard_path) if shard_path is not None else "",
        "resume": resume,
        "merge_only": merge_only,
        "run_fingerprint": run_fingerprint,
        "run_fingerprint_id": run_fingerprint["run_fingerprint_id"],
        "file_download_attempts": download_attempts,
        "files_retried": retry_count,
        "files_downloaded": files_processed,
        "compressed_bytes_transferred_total": compressed_bytes_transferred_total,
        "compressed_bytes_processed_successful": compressed_bytes_processed_successful,
        "compressed_bytes_downloaded": compressed_bytes_processed_successful,
        "max_download_mb": max_download_mb,
        "max_download_bytes": max_download_bytes,
        "max_download_mb_exceeded": max_download_exceeded,
        "transfer_failure_reason": transfer_failure_reason,
        "transfer_bytes_at_failure": transfer_bytes_at_failure,
        "matched_rows": total_matched_rows,
        "matched_sample_rows_written": len(matched_rows),
        "unique_urls": len(unique_urls),
        "output_file_size_bytes": output_file_size_bytes,
        "elapsed_seconds": elapsed_seconds,
        "total_elapsed_seconds": elapsed_seconds,
        "total_download_seconds": _round_seconds(
            sum(result.download_seconds for result in file_results)
        ),
        "total_decompress_seconds": _round_seconds(
            sum(result.decompress_seconds for result in file_results)
        ),
        "total_parse_seconds": _round_seconds(
            sum(result.parse_seconds for result in file_results)
        ),
        "total_match_seconds": _round_seconds(
            sum(result.match_seconds for result in file_results)
        ),
        "total_merge_seconds": _round_seconds(merge_seconds),
        "average_elapsed_seconds_per_file": _average(elapsed_values),
        "median_elapsed_seconds_per_file": _median(elapsed_values),
        "average_download_seconds_per_file": _average(download_values),
        "median_download_seconds_per_file": _median(download_values),
        "average_parse_seconds_per_file": _average(parse_values),
        "median_parse_seconds_per_file": _median(parse_values),
        "slowest_files": slowest_files,
        "estimated_full_window_download_size": estimated_full_window,
        "estimated_full_window_clean_download_size": estimated_full_window,
        "retry_network_overhead_ratio": retry_overhead_ratio,
        "disk_limit_gb": disk_limit_gb,
        "disk_limit_bytes": disk_limit_bytes,
        "disk_limit_exceeded": disk_limit_exceeded,
        "disk_failure_reason": disk_failure_reason,
        "disk_usage_bytes_at_failure": disk_usage_bytes_at_failure,
        "estimated_peak_disk_usage_bytes": peak_disk_usage_bytes,
        "full_year_feasible_under_disk_limit": full_year_feasible_under_disk_limit,
        "completed": completed,
        "keep_raw": keep_raw,
        "article_text_stored": False,
        "output_files": output_file_map,
        "notes": [
            "Peak disk estimate tracks bounded in-flight raw zip files during this probe.",
            "files_downloaded is retained as a compatibility alias for files_processed.",
            "compressed_bytes_downloaded is retained as a compatibility alias for compressed_bytes_processed_successful.",
            "compressed_bytes_transferred_total includes retry attempts and is the actual probe network transfer.",
            "disk_limit_gb bounds local probe storage during raw downloads.",
            "HTTP 404 raw archive files are recorded as missing and skipped unless the missing-file threshold is exceeded.",
            "Full-window clean download estimates use successful processed bytes, not retry overhead.",
            "Full-year processing should not be attempted until probe results are reviewed.",
        ],
    }
    _write_summary(summary_path, summary, output_files)
    return summary


def render_dry_run_plan(
    *,
    start_date: str,
    end_date: str,
    aliases: list[Alias],
    max_files: int,
    max_download_mb: float,
    output_dir: str | Path,
    disk_limit_gb: float,
    max_missing_files: int = DEFAULT_MAX_MISSING_FILES,
    workers: int = DEFAULT_WORKERS,
    worker_backend: str = "thread",
    matched_sample_size: int = DEFAULT_MATCHED_SAMPLE_SIZE,
    sample_per_ticker: int | None = None,
    profile_performance: bool = False,
    shard_output_dir: str | Path | None = None,
    resume: bool = False,
    merge_only: bool = False,
    repo_root: Path = REPO_ROOT,
) -> str:
    """Render the plan that execute mode would run."""

    workers = validate_workers(workers)
    worker_backend = validate_worker_backend(worker_backend)
    if matched_sample_size < 0:
        raise GdeltRawStreamError("matched_sample_size must be non-negative.")
    if sample_per_ticker is not None and sample_per_ticker < 1:
        raise GdeltRawStreamError("sample_per_ticker must be positive when set.")
    if merge_only and shard_output_dir is None:
        raise GdeltRawStreamError("--merge-only requires --shard-output-dir.")
    if resume and shard_output_dir is None:
        raise GdeltRawStreamError("--resume requires --shard-output-dir.")
    urls, uncapped_file_count = candidate_gkg_urls(
        start_date=start_date,
        end_date=end_date,
        max_files=max_files,
    )
    output_path = validate_local_data_path(output_dir, repo_root=repo_root)
    shard_path = (
        validate_local_data_path(shard_output_dir, repo_root=repo_root)
        if shard_output_dir is not None
        else ""
    )
    alias_preview = ", ".join(
        f"{alias.ticker}:{alias.alias}" for alias in aliases[:8]
    )
    if len(aliases) > 8:
        alias_preview += f", ... {len(aliases) - 8} more"
    lines = [
        "# GDELT raw GKG streaming probe dry run",
        f"query_method: {QUERY_METHOD}",
        f"start_date: {start_date}",
        f"end_date: {end_date}",
        f"candidate_file_count_uncapped: {uncapped_file_count}",
        f"candidate_file_count_capped: {len(urls)}",
        f"max_download_mb: {max_download_mb}",
        f"disk_limit_gb: {disk_limit_gb}",
        f"max_missing_files: {max_missing_files}",
        f"workers: {workers}",
        f"worker_backend: {worker_backend}",
        f"matched_sample_size: {matched_sample_size}",
        f"sample_per_ticker: {sample_per_ticker}",
        f"profile_performance: {profile_performance}",
        f"shard_output_dir_if_execute: {shard_path}",
        f"resume: {resume}",
        f"merge_only: {merge_only}",
        f"output_dir_if_execute: {output_path}",
        f"aliases_loaded: {len(aliases)}",
        f"alias_preview: {alias_preview}",
        "candidate_file_urls:",
    ]
    lines.extend(f"- {url}" for url in urls)
    lines.extend(
        [
            "execute_behavior:",
            "- requires --execute",
            "- processes candidate compressed GKG zip files with the configured bounded worker count and backend",
            "- deletes each temporary raw zip unless --keep-raw is set",
            "- writes metadata-only outputs under ignored news data paths",
            "- optional shard/resume mode writes one JSON result per candidate file",
            "- never stores article full text",
            "dry_run: true",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a bounded streaming GDELT raw GKG feasibility probe."
    )
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD.")
    parser.add_argument("--aliases-file")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--max-download-mb", type=float, default=DEFAULT_MAX_DOWNLOAD_MB)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan. This is the default unless --execute is set.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Opt in to live download/stream processing.",
    )
    parser.add_argument(
        "--keep-raw",
        action="store_true",
        help="Keep downloaded raw zip files under ignored data/raw/news/.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--disk-limit-gb", type=float, default=DEFAULT_DISK_LIMIT_GB)
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=(
            "Bounded file-level worker count for execute mode. Default 1 "
            "preserves sequential behavior; recommended local diagnostics "
            "usually start at 8, 12, or 16. Maximum 32."
        ),
    )
    parser.add_argument(
        "--worker-backend",
        choices=sorted(WORKER_BACKENDS),
        default="thread",
        help=(
            "Worker backend for execute mode. 'thread' preserves current "
            "download/parse behavior; 'process' downloads in the parent "
            "process and parses local temp files in a ProcessPoolExecutor."
        ),
    )
    parser.add_argument(
        "--matched-sample-size",
        type=int,
        default=DEFAULT_MATCHED_SAMPLE_SIZE,
        help=(
            "Maximum global matched metadata sample rows when "
            "--sample-per-ticker is not set. Default preserves current behavior."
        ),
    )
    parser.add_argument(
        "--sample-per-ticker",
        type=int,
        help=(
            "Optional deterministic per-ticker sample cap for "
            "matched_metadata_sample.csv."
        ),
    )
    parser.add_argument(
        "--profile-performance",
        action="store_true",
        help="Write timing metrics to probe_summary.json and per_file_metrics.csv.",
    )
    parser.add_argument(
        "--shard-output-dir",
        help="Optional ignored directory for one per-candidate-file JSON result shard.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse existing shard results and process only missing shards.",
    )
    parser.add_argument(
        "--merge-only",
        action="store_true",
        help="Merge existing shard results without downloading or parsing files.",
    )
    parser.add_argument(
        "--progress-interval-seconds",
        type=float,
        default=DEFAULT_PROGRESS_INTERVAL_SECONDS,
        help="Progress logging interval for execute mode; set 0 to disable.",
    )
    parser.add_argument(
        "--max-missing-files",
        type=int,
        default=DEFAULT_MAX_MISSING_FILES,
        help=(
            "Maximum number of HTTP 404 raw GKG files to skip before the "
            "probe is marked incomplete."
        ),
    )
    parser.add_argument("--full-window-start-date", default=PROJECT_WINDOW_START)
    parser.add_argument("--full-window-end-date", default=PROJECT_WINDOW_END)
    args = parser.parse_args(argv)

    try:
        aliases = load_aliases(args.aliases_file)
        if not args.execute:
            print(
                render_dry_run_plan(
                    start_date=args.start_date,
                    end_date=args.end_date,
                    aliases=aliases,
                    max_files=args.max_files,
                    max_download_mb=args.max_download_mb,
                    output_dir=args.output_dir,
                    disk_limit_gb=args.disk_limit_gb,
                    max_missing_files=args.max_missing_files,
                    workers=args.workers,
                    worker_backend=args.worker_backend,
                    matched_sample_size=args.matched_sample_size,
                    sample_per_ticker=args.sample_per_ticker,
                    profile_performance=args.profile_performance,
                    shard_output_dir=args.shard_output_dir,
                    resume=args.resume,
                    merge_only=args.merge_only,
                ),
                end="",
            )
            return 0

        summary = run_stream_probe(
            start_date=args.start_date,
            end_date=args.end_date,
            aliases=aliases,
            max_files=args.max_files,
            max_download_mb=args.max_download_mb,
            output_dir=args.output_dir,
            keep_raw=args.keep_raw,
            disk_limit_gb=args.disk_limit_gb,
            max_missing_files=args.max_missing_files,
            full_window_start_date=args.full_window_start_date,
            full_window_end_date=args.full_window_end_date,
            alias_file_path=args.aliases_file,
            workers=args.workers,
            worker_backend=args.worker_backend,
            matched_sample_size=args.matched_sample_size,
            sample_per_ticker=args.sample_per_ticker,
            profile_performance=args.profile_performance,
            shard_output_dir=args.shard_output_dir,
            resume=args.resume,
            merge_only=args.merge_only,
            progress_interval_seconds=args.progress_interval_seconds,
        )
    except GdeltRawStreamError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("completed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
