"""Stream a bounded GDELT raw GKG probe without storing raw files by default.

The script is a feasibility tool, not a production collector. It downloads at
most a small number of GDELT raw GKG zip files, filters rows by conservative
company aliases, writes metadata-only outputs, and deletes temporary raw files
unless --keep-raw is explicitly set.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import json
from pathlib import Path
import sys
import tempfile
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
MAX_ALLOWED_FILES = 3_500
MAX_FILE_RETRIES = 2
MAX_SAMPLE_ROWS = 500
MAX_FAILED_FILES_RECORDED = 20
MAX_MISSING_FILES_RECORDED = 50
CHUNK_SIZE = 1024 * 256
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


@dataclass(frozen=True)
class FileProcessResult:
    downloaded_bytes: int
    matched_rows: int
    max_raw_file_bytes: int


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
                if ticker and alias:
                    aliases.append(Alias(ticker=ticker, alias=alias))
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


def alias_matches(row_text: str, aliases: Iterable[Alias]) -> list[Alias]:
    """Return the first matched alias per ticker for one GKG row."""

    folded = row_text.casefold()
    matched_by_ticker: dict[str, Alias] = {}
    for alias in aliases:
        if alias.ticker in matched_by_ticker:
            continue
        if alias.alias.casefold() in folded:
            matched_by_ticker[alias.ticker] = alias
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

    if header is not None:
        values = [
            field
            for index, field in enumerate(fields)
            if index < len(header)
            and _normalize_header_name(header[index]) in MATCH_FIELD_HEADER_NAMES
        ]
    else:
        values = [_field(fields, index) for index in HEADERLESS_GKG_MATCH_FIELD_INDICES]
    return "\t".join(value for value in values if value)


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
    matched_alias: Alias,
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
        "matched_ticker": matched_alias.ticker,
        "matched_company_alias": matched_alias.alias,
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
) -> Iterable[dict[str, str]]:
    """Yield metadata-only matches from a compressed GKG file."""

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
                    row_text = build_gkg_match_text(fields, header)
                    for matched_alias in alias_matches(row_text, aliases):
                        yield metadata_from_fields(
                            fields,
                            header=header,
                            matched_alias=matched_alias,
                            source_file=zip_path.name,
                            query_start_date=query_start_date,
                            query_end_date=query_end_date,
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
) -> int:
    """Download or copy one source into destination, enforcing byte budget."""

    downloaded = 0
    try:
        with _open_source(url, timeout_seconds=timeout_seconds) as source:
            with destination.open("wb") as output:
                while True:
                    chunk = source.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > remaining_bytes:
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
        destination.unlink(missing_ok=True)
        raise
    except HTTPError as exc:
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
) -> dict[str, object]:
    """Execute a bounded streaming GDELT raw GKG probe."""

    if max_download_mb <= 0:
        raise GdeltRawStreamError("max_download_mb must be positive.")
    if disk_limit_gb <= 0:
        raise GdeltRawStreamError("disk_limit_gb must be positive.")
    if max_missing_files < 0:
        raise GdeltRawStreamError("max_missing_files must be non-negative.")

    output_path = validate_local_data_path(output_dir, repo_root=repo_root)
    raw_keep_dir = validate_local_data_path(DEFAULT_RAW_DIR, repo_root=repo_root)
    temp_raw_parent = validate_local_data_path(DEFAULT_TEMP_RAW_DIR, repo_root=repo_root)
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
    if keep_raw:
        raw_keep_dir.mkdir(parents=True, exist_ok=True)
    else:
        temp_raw_parent.mkdir(parents=True, exist_ok=True)

    sample_path = output_path / "matched_metadata_sample.csv"
    counts_path = output_path / "stock_day_counts.csv"
    summary_path = output_path / "probe_summary.json"
    output_files = [sample_path, counts_path, summary_path]

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
    matched_rows: list[dict[str, str]] = []
    grouped_counts: dict[tuple[str, str], dict[str, object]] = defaultdict(
        lambda: {"matched_rows": 0, "urls": set()}
    )
    unique_urls: set[str] = set()

    temp_context = (
        tempfile.TemporaryDirectory(dir=temp_raw_parent) if not keep_raw else None
    )
    raw_work_dir = (
        Path(temp_context.name) if temp_context is not None else raw_keep_dir
    )

    def current_probe_disk_usage() -> int:
        raw_path = raw_keep_dir if keep_raw else temp_raw_parent
        return _tree_file_size(output_path) + _tree_file_size(raw_path)

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

    try:
        for index, url in enumerate(urls, start=1):
            if compressed_bytes_transferred_total >= max_download_bytes:
                break
            raw_path = raw_work_dir / _safe_raw_name(url, index)
            files_attempted += 1
            stop_after_failure = False
            for attempt_index in range(MAX_FILE_RETRIES + 1):
                if attempt_index > 0:
                    retry_count += 1
                remaining_bytes = max_download_bytes - compressed_bytes_transferred_total
                disk_usage_before_download = current_probe_disk_usage()
                max_disk_usage_observed = max(
                    max_disk_usage_observed,
                    disk_usage_before_download,
                )
                remaining_disk_bytes = disk_limit_bytes - disk_usage_before_download
                if remaining_disk_bytes <= 0:
                    record_disk_limit_failure(
                        url=url,
                        message=(
                            "disk_limit_gb_exceeded before downloading "
                            f"{url!r}: current local probe usage "
                            f"{disk_usage_before_download} bytes meets or exceeds "
                            f"limit {disk_limit_bytes} bytes."
                        ),
                        attempts=attempt_index,
                        projected_usage_bytes=disk_usage_before_download,
                    )
                    stop_after_failure = True
                    break
                try:
                    download_attempts += 1
                    downloaded_bytes = download_to_path(
                        url,
                        raw_path,
                        remaining_bytes=remaining_bytes,
                        remaining_disk_bytes=remaining_disk_bytes,
                        disk_usage_base_bytes=disk_usage_before_download,
                        disk_limit_bytes=disk_limit_bytes,
                    )
                    compressed_bytes_transferred_total += downloaded_bytes
                    max_raw_file_bytes = max(max_raw_file_bytes, downloaded_bytes)
                    max_disk_usage_observed = max(
                        max_disk_usage_observed,
                        disk_usage_before_download + downloaded_bytes,
                    )

                    file_matches = list(
                        iter_gkg_metadata_matches(
                            raw_path,
                            aliases=aliases,
                            query_start_date=start_date,
                            query_end_date=end_date,
                        )
                    )
                    files_processed += 1
                    compressed_bytes_processed_successful += downloaded_bytes
                    total_matched_rows += len(file_matches)
                    for row in file_matches:
                        _add_count_row(grouped_counts, row)
                        document_identifier = row.get("document_identifier", "")
                        if document_identifier:
                            unique_urls.add(document_identifier)
                    if len(matched_rows) < MAX_SAMPLE_ROWS:
                        remaining_sample_slots = MAX_SAMPLE_ROWS - len(matched_rows)
                        matched_rows.extend(file_matches[:remaining_sample_slots])

                    if not keep_raw:
                        raw_path.unlink(missing_ok=True)
                    break
                except DiskLimitExceeded as exc:
                    compressed_bytes_transferred_total += exc.transferred_bytes
                    raw_path.unlink(missing_ok=True)
                    record_disk_limit_failure(
                        url=url,
                        message=str(exc),
                        attempts=attempt_index + 1,
                        projected_usage_bytes=exc.projected_usage_bytes,
                    )
                    stop_after_failure = True
                    break
                except MaxDownloadExceeded as exc:
                    compressed_bytes_transferred_total += exc.transferred_bytes
                    raw_path.unlink(missing_ok=True)
                    record_max_download_failure(
                        url=url,
                        message=str(exc),
                        attempts=attempt_index + 1,
                    )
                    stop_after_failure = True
                    break
                except MissingSourceFile as exc:
                    compressed_bytes_transferred_total += exc.transferred_bytes
                    raw_path.unlink(missing_ok=True)
                    record_missing_file(url=url, message=str(exc))
                    if files_missing > max_missing_files:
                        missing_file_threshold_exceeded = True
                        missing_failure_reason = "missing_file_threshold_exceeded"
                        stop_after_failure = True
                    break
                except DownloadAttemptFailed as exc:
                    compressed_bytes_transferred_total += exc.transferred_bytes
                    max_raw_file_bytes = max(max_raw_file_bytes, exc.transferred_bytes)
                    max_disk_usage_observed = max(
                        max_disk_usage_observed,
                        disk_usage_before_download + exc.transferred_bytes,
                    )
                    raw_path.unlink(missing_ok=True)
                    if compressed_bytes_transferred_total >= max_download_bytes:
                        record_max_download_failure(
                            url=url,
                            message=(
                                "max_download_mb_exceeded after failed partial "
                                f"download attempt for {url!r}."
                            ),
                            attempts=attempt_index + 1,
                        )
                        stop_after_failure = True
                        break
                    if attempt_index >= MAX_FILE_RETRIES:
                        files_failed += 1
                        if len(failed_files) < MAX_FAILED_FILES_RECORDED:
                            failed_files.append(
                                {
                                    "url": url,
                                    "error_type": exc.error_type,
                                    "message": str(exc),
                                    "attempts": MAX_FILE_RETRIES + 1,
                                }
                            )
                        stop_after_failure = True
                        break
                except TRANSIENT_FILE_ERRORS as exc:
                    raw_path.unlink(missing_ok=True)
                    if attempt_index >= MAX_FILE_RETRIES:
                        files_failed += 1
                        if len(failed_files) < MAX_FAILED_FILES_RECORDED:
                            failed_files.append(
                                {
                                    "url": url,
                                    "error_type": type(exc).__name__,
                                    "message": str(exc),
                                    "attempts": MAX_FILE_RETRIES + 1,
                                }
                            )
                        stop_after_failure = True
                        break
            if stop_after_failure:
                break
    finally:
        if temp_context is not None:
            temp_context.cleanup()

    metadata_fields = [
        "gkg_record_id",
        "timestamp",
        "date",
        "source_collection_identifier",
        "source_common_name",
        "document_identifier",
        "matched_ticker",
        "matched_company_alias",
        "query_start_date",
        "query_end_date",
        "query_method",
        "gdelt_file",
    ]
    _write_csv(sample_path, matched_rows, fieldnames=metadata_fields)
    _write_counts_csv(counts_path, _count_rows_from_grouped(grouped_counts))

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
        "output_files": {
            "probe_summary": str(summary_path),
            "matched_metadata_sample": str(sample_path),
            "stock_day_counts": str(counts_path),
        },
        "notes": [
            "Peak disk estimate assumes one compressed raw zip is processed at a time.",
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
    repo_root: Path = REPO_ROOT,
) -> str:
    """Render the plan that execute mode would run."""

    urls, uncapped_file_count = candidate_gkg_urls(
        start_date=start_date,
        end_date=end_date,
        max_files=max_files,
    )
    output_path = validate_local_data_path(output_dir, repo_root=repo_root)
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
            "- downloads one compressed GKG zip at a time",
            "- deletes each temporary raw zip unless --keep-raw is set",
            "- writes metadata-only outputs under ignored news data paths",
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
        )
    except GdeltRawStreamError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("completed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
