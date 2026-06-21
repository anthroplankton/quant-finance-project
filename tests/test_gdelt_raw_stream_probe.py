from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
import sys
import zipfile

import pytest


def _load_stream_module():
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "probe_gdelt_raw_stream.py"
    )
    spec = importlib.util.spec_from_file_location("probe_gdelt_raw_stream", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load probe_gdelt_raw_stream.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["probe_gdelt_raw_stream"] = module
    spec.loader.exec_module(module)
    return module


stream = _load_stream_module()


def _write_synthetic_gkg_zip(path: Path, rows: list[list[str]]) -> Path:
    header = [
        "GKGRECORDID",
        "DATE",
        "SourceCollectionIdentifier",
        "SourceCommonName",
        "DocumentIdentifier",
        "V2Organizations",
    ]
    content_rows = [header, *rows]
    text = "\n".join("\t".join(row) for row in content_rows) + "\n"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("synthetic.gkg.csv", text)
    return path


def _write_headered_gkg_zip(
    path: Path,
    *,
    header: list[str],
    rows: list[list[str]],
) -> Path:
    content_rows = [header, *rows]
    text = "\n".join("\t".join(row) for row in content_rows) + "\n"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("synthetic-headered.gkg.csv", text)
    return path


def _write_headerless_gkg_zip(path: Path, rows: list[list[str]]) -> Path:
    text = "\n".join("\t".join(row) for row in rows) + "\n"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("synthetic-headerless.gkg.csv", text)
    return path


def _gkg_v21_headerless_row(
    *,
    record_id: str = "20250401000000-0",
    row_date: str = "20250401000000",
    source_collection_identifier: str = "1",
    source_common_name: str = "example.com",
    document_identifier: str = "https://example.com/news/article",
    themes: str = "",
    v2themes: str = "",
    locations: str = "",
    v2locations: str = "",
    persons: str = "",
    v2persons: str = "",
    organizations: str = "",
    v2organizations: str = "",
    all_names: str = "",
) -> list[str]:
    row = [""] * 24
    row[0] = record_id
    row[1] = row_date
    row[2] = source_collection_identifier
    row[3] = source_common_name
    row[4] = document_identifier
    row[7] = themes
    row[8] = v2themes
    row[9] = locations
    row[10] = v2locations
    row[11] = persons
    row[12] = v2persons
    row[13] = organizations
    row[14] = v2organizations
    row[23] = all_names
    return row


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class _ScriptedSource:
    def __init__(self, chunks: list[bytes], error: Exception | None = None) -> None:
        self._chunks = list(chunks)
        self._error = error

    def __enter__(self) -> "_ScriptedSource":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int) -> bytes:
        del size
        if self._chunks:
            return self._chunks.pop(0)
        if self._error is not None:
            raise self._error
        return b""


def test_streaming_probe_filters_aliases_and_writes_metadata_only(
    tmp_path: Path,
) -> None:
    zip_path = _write_synthetic_gkg_zip(
        tmp_path / "sample.gkg.csv.zip",
        [
            [
                "20250401000000-0",
                "20250401000000",
                "1",
                "example.com",
                "https://example.com/tsmc",
                "Taiwan Semiconductor;台積電",
            ],
            [
                "20250401001500-0",
                "20250401001500",
                "1",
                "example.org",
                "https://example.org/foxconn",
                "Foxconn supplier update",
            ],
            [
                "20250401003000-0",
                "20250401003000",
                "1",
                "example.net",
                "https://example.net/other",
                "unrelated company",
            ],
        ],
    )

    summary = stream.run_stream_probe(
        start_date="2025-04-01",
        end_date="2025-04-01",
        aliases=[stream.Alias("2330", "台積電"), stream.Alias("2317", "Foxconn")],
        max_files=1,
        max_download_mb=1,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=[str(zip_path)],
        repo_root=tmp_path,
    )

    output_dir = tmp_path / "data/processed/news/gdelt_probe"
    rows = _read_csv(output_dir / "matched_metadata_sample.csv")
    counts = _read_csv(output_dir / "stock_day_counts.csv")

    assert summary["files_attempted"] == 1
    assert summary["files_downloaded"] == 1
    assert summary["matched_rows"] == 2
    assert summary["unique_urls"] == 2
    assert summary["article_text_stored"] is False
    assert {row["matched_ticker"] for row in rows} == {"2330", "2317"}
    assert {row["matched_company_alias"] for row in rows} == {"台積電", "Foxconn"}
    assert all("V2Organizations" not in row for row in rows)
    assert {row["matched_ticker"] for row in counts} == {"2330", "2317"}
    assert (output_dir / "probe_summary.json").exists()


def test_headerless_raw_gkg_schema_maps_source_and_document_identifier(
    tmp_path: Path,
) -> None:
    zip_path = _write_headerless_gkg_zip(
        tmp_path / "headerless.gkg.csv.zip",
        [
            [
                "20250401000000-0",
                "20250401000000",
                "1",
                "example.com",
                "https://example.com/news/article-1",
                "",
                "",
                "ECON_STOCKMARKET",
                "ECON_STOCKMARKET,100",
                "",
                "",
                "",
                "",
                "Taiwan Semiconductor",
                "Taiwan Semiconductor,25;TSMC,50",
                "0,0,0,0,0,0,0",
            ],
            [
                "20250401001500-0",
                "20250401001500",
                "1",
                "example.com",
                "https://example.com/news/article-2",
                "",
                "",
                "ECON_STOCKMARKET",
                "ECON_STOCKMARKET,100",
                "",
                "",
                "",
                "",
                "Taiwan Semiconductor",
                "台積電,50",
                "0,0,0,0,0,0,0",
            ],
        ],
    )

    summary = stream.run_stream_probe(
        start_date="2025-04-01",
        end_date="2025-04-01",
        aliases=[stream.Alias("2330", "TSMC"), stream.Alias("2330", "台積電")],
        max_files=1,
        max_download_mb=1,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=[str(zip_path)],
        repo_root=tmp_path,
    )

    output_dir = tmp_path / "data/processed/news/gdelt_probe"
    rows = _read_csv(output_dir / "matched_metadata_sample.csv")
    counts = _read_csv(output_dir / "stock_day_counts.csv")

    assert summary["matched_rows"] == 2
    assert summary["unique_urls"] == 2
    assert rows[0]["gkg_record_id"] == "20250401000000-0"
    assert rows[0]["source_collection_identifier"] == "1"
    assert rows[0]["source_common_name"] == "example.com"
    assert rows[0]["document_identifier"] == "https://example.com/news/article-1"
    assert counts == [
        {
            "date": "2025-04-01",
            "matched_ticker": "2330",
            "matched_rows": "2",
            "unique_urls": "2",
        }
    ]


def test_headered_gkg_schema_uses_column_names_not_fallback_positions(
    tmp_path: Path,
) -> None:
    zip_path = _write_headered_gkg_zip(
        tmp_path / "headered-reordered.gkg.csv.zip",
        header=[
            "DocumentIdentifier",
            "V2Organizations",
            "DATE",
            "SourceCommonName",
            "GKGRECORDID",
            "SourceCollectionIdentifier",
        ],
        rows=[
            [
                "https://example.com/news/article-1",
                "Taiwan Semiconductor;TSMC",
                "20250401000000",
                "example.com",
                "20250401000000-0",
                "1",
            ],
        ],
    )

    summary = stream.run_stream_probe(
        start_date="2025-04-01",
        end_date="2025-04-01",
        aliases=[stream.Alias("2330", "TSMC")],
        max_files=1,
        max_download_mb=1,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=[str(zip_path)],
        repo_root=tmp_path,
    )

    output_dir = tmp_path / "data/processed/news/gdelt_probe"
    rows = _read_csv(output_dir / "matched_metadata_sample.csv")
    counts = _read_csv(output_dir / "stock_day_counts.csv")

    assert summary["matched_rows"] == 1
    assert summary["unique_urls"] == 1
    assert rows[0]["gkg_record_id"] == "20250401000000-0"
    assert rows[0]["source_collection_identifier"] == "1"
    assert rows[0]["source_common_name"] == "example.com"
    assert rows[0]["document_identifier"] == "https://example.com/news/article-1"
    assert rows[0]["document_identifier"] != rows[0]["source_common_name"]
    assert counts[0]["unique_urls"] == "1"


def test_headered_gkg_matching_excludes_metadata_and_url_fields(
    tmp_path: Path,
) -> None:
    zip_path = _write_headered_gkg_zip(
        tmp_path / "metadata-only.gkg.csv.zip",
        header=[
            "GKGRECORDID",
            "DATE",
            "SourceCollectionIdentifier",
            "SourceCommonName",
            "DocumentIdentifier",
            "V2Organizations",
            "AllNames",
        ],
        rows=[
            [
                "TSMC-record",
                "MediaTek-date",
                "TSMC",
                "MediaTek.example.com",
                "https://example.com/news/TSMC-MediaTek",
                "unrelated company",
                "other name",
            ],
        ],
    )

    summary = stream.run_stream_probe(
        start_date="2025-04-01",
        end_date="2025-04-01",
        aliases=[stream.Alias("2330", "TSMC"), stream.Alias("2454", "MediaTek")],
        max_files=1,
        max_download_mb=1,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=[str(zip_path)],
        repo_root=tmp_path,
    )

    output_dir = tmp_path / "data/processed/news/gdelt_probe"
    rows = _read_csv(output_dir / "matched_metadata_sample.csv")
    counts = _read_csv(output_dir / "stock_day_counts.csv")

    assert summary["matched_rows"] == 0
    assert summary["unique_urls"] == 0
    assert rows == []
    assert counts == []


def test_headered_gkg_matching_uses_entity_and_name_fields(
    tmp_path: Path,
) -> None:
    zip_path = _write_headered_gkg_zip(
        tmp_path / "content-fields.gkg.csv.zip",
        header=[
            "GKGRECORDID",
            "DATE",
            "SourceCollectionIdentifier",
            "SourceCommonName",
            "DocumentIdentifier",
            "V2Organizations",
            "AllNames",
        ],
        rows=[
            [
                "20250401000000-0",
                "20250401000000",
                "1",
                "example.com",
                "https://example.com/news/article-1",
                "Taiwan Semiconductor;TSMC",
                "MediaTek,50",
            ],
        ],
    )

    summary = stream.run_stream_probe(
        start_date="2025-04-01",
        end_date="2025-04-01",
        aliases=[stream.Alias("2330", "TSMC"), stream.Alias("2454", "MediaTek")],
        max_files=1,
        max_download_mb=1,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=[str(zip_path)],
        repo_root=tmp_path,
    )

    rows = _read_csv(
        tmp_path / "data/processed/news/gdelt_probe/matched_metadata_sample.csv"
    )

    assert summary["matched_rows"] == 2
    assert {row["matched_ticker"] for row in rows} == {"2330", "2454"}


def test_headerless_gkg_matching_excludes_metadata_and_url_fields(
    tmp_path: Path,
) -> None:
    zip_path = _write_headerless_gkg_zip(
        tmp_path / "headerless-metadata-only.gkg.csv.zip",
        [
            _gkg_v21_headerless_row(
                record_id="TSMC-record",
                row_date="MediaTek-date",
                source_collection_identifier="TSMC",
                source_common_name="MediaTek.example.com",
                document_identifier="https://example.com/news/TSMC-MediaTek",
                v2organizations="unrelated company",
                all_names="other name",
            )
        ],
    )

    summary = stream.run_stream_probe(
        start_date="2025-04-01",
        end_date="2025-04-01",
        aliases=[stream.Alias("2330", "TSMC"), stream.Alias("2454", "MediaTek")],
        max_files=1,
        max_download_mb=1,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=[str(zip_path)],
        repo_root=tmp_path,
    )

    output_dir = tmp_path / "data/processed/news/gdelt_probe"

    assert summary["matched_rows"] == 0
    assert _read_csv(output_dir / "matched_metadata_sample.csv") == []
    assert _read_csv(output_dir / "stock_day_counts.csv") == []


def test_headerless_gkg_matching_uses_organization_and_allnames_fields(
    tmp_path: Path,
) -> None:
    zip_path = _write_headerless_gkg_zip(
        tmp_path / "headerless-content-fields.gkg.csv.zip",
        [
            _gkg_v21_headerless_row(
                record_id="20250401000000-0",
                document_identifier="https://example.com/news/article-1",
                v2organizations="Taiwan Semiconductor;TSMC",
            ),
            _gkg_v21_headerless_row(
                record_id="20250401001500-0",
                row_date="20250401001500",
                document_identifier="https://example.com/news/article-2",
                all_names="MediaTek,50",
            ),
        ],
    )

    summary = stream.run_stream_probe(
        start_date="2025-04-01",
        end_date="2025-04-01",
        aliases=[stream.Alias("2330", "TSMC"), stream.Alias("2454", "MediaTek")],
        max_files=1,
        max_download_mb=1,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=[str(zip_path)],
        repo_root=tmp_path,
    )

    rows = _read_csv(
        tmp_path / "data/processed/news/gdelt_probe/matched_metadata_sample.csv"
    )

    assert summary["matched_rows"] == 2
    assert summary["unique_urls"] == 2
    assert {row["matched_ticker"] for row in rows} == {"2330", "2454"}


def test_large_gkg_field_streams_without_crashing_or_entering_output(
    tmp_path: Path,
) -> None:
    long_field = "台積電" + ("X" * 140_000)
    zip_path = _write_synthetic_gkg_zip(
        tmp_path / "large-field.gkg.csv.zip",
        [
            [
                "20250401000000-0",
                "20250401000000",
                "1",
                "example.com",
                "https://example.com/tsmc",
                long_field,
            ],
        ],
    )

    summary = stream.run_stream_probe(
        start_date="2025-04-01",
        end_date="2025-04-01",
        aliases=[stream.Alias("2330", "台積電")],
        max_files=1,
        max_download_mb=1,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=[str(zip_path)],
        repo_root=tmp_path,
    )

    output_dir = tmp_path / "data/processed/news/gdelt_probe"
    sample_text = (output_dir / "matched_metadata_sample.csv").read_text(
        encoding="utf-8"
    )
    rows = _read_csv(output_dir / "matched_metadata_sample.csv")

    assert summary["matched_rows"] == 1
    assert rows[0]["matched_ticker"] == "2330"
    assert rows[0]["matched_company_alias"] == "台積電"
    assert "X" * 1000 not in sample_text


def test_keep_raw_false_deletes_temporary_raw_zip(tmp_path: Path) -> None:
    zip_path = _write_synthetic_gkg_zip(
        tmp_path / "sample.gkg.csv.zip",
        [
            [
                "20250401000000-0",
                "20250401000000",
                "1",
                "example.com",
                "https://example.com/tsmc",
                "台積電",
            ],
        ],
    )

    stream.run_stream_probe(
        start_date="2025-04-01",
        end_date="2025-04-01",
        aliases=[stream.Alias("2330", "台積電")],
        max_files=1,
        max_download_mb=1,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=[str(zip_path)],
        repo_root=tmp_path,
    )

    temp_raw_root = tmp_path / "data/raw/news/gdelt_probe_tmp"
    kept_raw_root = tmp_path / "data/raw/news/gdelt_probe"
    assert list(temp_raw_root.rglob("*.zip")) == []
    assert not kept_raw_root.exists()


def test_max_files_limits_synthetic_sources(tmp_path: Path) -> None:
    first_zip = _write_synthetic_gkg_zip(
        tmp_path / "first.gkg.csv.zip",
        [["20250401000000-0", "20250401000000", "1", "a.com", "https://a.com/1", "台積電"]],
    )
    second_zip = _write_synthetic_gkg_zip(
        tmp_path / "second.gkg.csv.zip",
        [
            [
                "20250401001500-0",
                "20250401001500",
                "1",
                "b.com",
                "https://b.com/1",
                "Foxconn",
            ]
        ],
    )

    summary = stream.run_stream_probe(
        start_date="2025-04-01",
        end_date="2025-04-01",
        aliases=[stream.Alias("2330", "台積電"), stream.Alias("2317", "Foxconn")],
        max_files=1,
        max_download_mb=1,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=[str(first_zip), str(second_zip)],
        repo_root=tmp_path,
    )

    assert summary["candidate_file_count_uncapped"] == 2
    assert summary["candidate_file_count_capped"] == 1
    assert summary["files_attempted"] == 1
    assert summary["files_downloaded"] == 1
    assert summary["matched_rows"] == 1


def test_http_404_is_recorded_as_missing_and_probe_continues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    valid_zip = _write_synthetic_gkg_zip(
        tmp_path / "valid.gkg.csv.zip",
        [
            [
                "20250503004500-0",
                "20250503004500",
                "1",
                "example.com",
                "https://example.com/tsmc",
                "台積電",
            ],
        ],
    )
    valid_bytes = valid_zip.read_bytes()
    sources = iter(
        [
            stream.HTTPError(
                "http://data.gdeltproject.org/gdeltv2/20250503003000.gkg.csv.zip",
                404,
                "Not Found",
                {},
                None,
            ),
            _ScriptedSource([valid_bytes]),
        ]
    )

    def fake_open_source(url: str, *, timeout_seconds: float):
        del url, timeout_seconds
        source_or_error = next(sources)
        if isinstance(source_or_error, Exception):
            raise source_or_error
        return source_or_error

    monkeypatch.setattr(stream, "_open_source", fake_open_source)

    summary = stream.run_stream_probe(
        start_date="2025-05-03",
        end_date="2025-05-03",
        aliases=[stream.Alias("2330", "台積電")],
        max_files=2,
        max_download_mb=1,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=[
            "http://data.gdeltproject.org/gdeltv2/20250503003000.gkg.csv.zip",
            "http://data.gdeltproject.org/gdeltv2/20250503004500.gkg.csv.zip",
        ],
        repo_root=tmp_path,
    )

    temp_raw_root = tmp_path / "data/raw/news/gdelt_probe_tmp"

    assert summary["completed"] is True
    assert summary["files_attempted"] == 2
    assert summary["download_attempts"] == 2
    assert summary["retry_count"] == 0
    assert summary["files_missing"] == 1
    assert summary["files_failed"] == 0
    assert summary["files_processed"] == 1
    assert summary["compressed_bytes_processed_successful"] == len(valid_bytes)
    assert summary["missing_file_ratio"] == 0.5
    assert summary["missing_files"] == [
        {
            "url": (
                "http://data.gdeltproject.org/gdeltv2/"
                "20250503003000.gkg.csv.zip"
            ),
            "file_id": "20250503003000.gkg.csv.zip",
            "timestamp": "20250503003000",
            "message": (
                "Missing GDELT raw file "
                "'http://data.gdeltproject.org/gdeltv2/"
                "20250503003000.gkg.csv.zip': HTTP 404 Not Found."
            ),
        }
    ]
    assert summary["matched_rows"] == 1
    assert list(temp_raw_root.rglob("*.zip")) == []


def test_too_many_http_404s_exceeds_missing_file_threshold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    errors = iter(
        [
            stream.HTTPError(
                (
                    "http://data.gdeltproject.org/gdeltv2/"
                    f"2025050300{index:02d}00.gkg.csv.zip"
                ),
                404,
                "Not Found",
                {},
                None,
            )
            for index in (30, 45)
        ]
    )

    def fake_open_source(url: str, *, timeout_seconds: float):
        del url, timeout_seconds
        raise next(errors)

    monkeypatch.setattr(stream, "_open_source", fake_open_source)

    summary = stream.run_stream_probe(
        start_date="2025-05-03",
        end_date="2025-05-03",
        aliases=[stream.Alias("2330", "台積電")],
        max_files=3,
        max_download_mb=1,
        max_missing_files=1,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=[
            "http://data.gdeltproject.org/gdeltv2/20250503003000.gkg.csv.zip",
            "http://data.gdeltproject.org/gdeltv2/20250503004500.gkg.csv.zip",
            "http://data.gdeltproject.org/gdeltv2/20250503010000.gkg.csv.zip",
        ],
        repo_root=tmp_path,
    )

    temp_raw_root = tmp_path / "data/raw/news/gdelt_probe_tmp"

    assert summary["completed"] is False
    assert summary["files_attempted"] == 2
    assert summary["download_attempts"] == 2
    assert summary["retry_count"] == 0
    assert summary["files_missing"] == 2
    assert summary["files_failed"] == 0
    assert summary["files_processed"] == 0
    assert summary["missing_file_threshold_exceeded"] is True
    assert summary["missing_failure_reason"] == "missing_file_threshold_exceeded"
    assert len(summary["missing_files"]) == 2
    assert list(temp_raw_root.rglob("*.zip")) == []


def test_non_404_http_errors_still_retry_and_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[str] = []

    def fake_open_source(url: str, *, timeout_seconds: float):
        del timeout_seconds
        attempts.append(url)
        raise stream.HTTPError(url, 500, "Server Error", {}, None)

    monkeypatch.setattr(stream, "_open_source", fake_open_source)

    summary = stream.run_stream_probe(
        start_date="2025-05-03",
        end_date="2025-05-03",
        aliases=[stream.Alias("2330", "台積電")],
        max_files=1,
        max_download_mb=1,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=[
            "http://data.gdeltproject.org/gdeltv2/20250503003000.gkg.csv.zip",
        ],
        repo_root=tmp_path,
    )

    assert summary["completed"] is False
    assert len(attempts) == stream.MAX_FILE_RETRIES + 1
    assert summary["download_attempts"] == stream.MAX_FILE_RETRIES + 1
    assert summary["retry_count"] == stream.MAX_FILE_RETRIES
    assert summary["files_missing"] == 0
    assert summary["files_failed"] == 1
    assert summary["files_processed"] == 0
    assert summary["failed_files"][0]["error_type"] == "HTTPError"


def test_one_month_file_count_is_allowed_without_full_year_cap() -> None:
    urls, total_count = stream.candidate_gkg_urls(
        start_date="2025-04-01",
        end_date="2025-04-30",
        max_files=2880,
    )

    assert total_count == 2880
    assert len(urls) == 2880
    assert stream.MAX_ALLOWED_FILES == 3500
    assert stream.MAX_ALLOWED_FILES < 10_000


def test_full_year_file_count_is_rejected_by_safety_cap() -> None:
    with pytest.raises(stream.GdeltRawStreamError, match="max_files must be between"):
        stream.candidate_gkg_urls(
            start_date="2025-04-01",
            end_date="2026-03-31",
            max_files=35040,
        )


def test_counts_include_matches_beyond_metadata_sample_cap(tmp_path: Path) -> None:
    rows = [
        [
            f"20250401000000-{index}",
            "20250401000000",
            "1",
            "example.com",
            f"https://example.com/tsmc/{index}",
            "台積電",
        ]
        for index in range(stream.MAX_SAMPLE_ROWS + 5)
    ]
    zip_path = _write_synthetic_gkg_zip(tmp_path / "many.gkg.csv.zip", rows)

    summary = stream.run_stream_probe(
        start_date="2025-04-01",
        end_date="2025-04-01",
        aliases=[stream.Alias("2330", "台積電")],
        max_files=1,
        max_download_mb=1,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=[str(zip_path)],
        repo_root=tmp_path,
    )

    output_dir = tmp_path / "data/processed/news/gdelt_probe"
    sample_rows = _read_csv(output_dir / "matched_metadata_sample.csv")
    count_rows = _read_csv(output_dir / "stock_day_counts.csv")

    assert summary["matched_rows"] == stream.MAX_SAMPLE_ROWS + 5
    assert len(sample_rows) == stream.MAX_SAMPLE_ROWS
    assert count_rows == [
        {
            "date": "2025-04-01",
            "matched_ticker": "2330",
            "matched_rows": str(stream.MAX_SAMPLE_ROWS + 5),
            "unique_urls": str(stream.MAX_SAMPLE_ROWS + 5),
        }
    ]


def test_max_download_mb_is_enforced_and_partial_raw_is_removed(
    tmp_path: Path,
) -> None:
    zip_path = _write_synthetic_gkg_zip(
        tmp_path / "large.gkg.csv.zip",
        [
            [
                "20250401000000-0",
                "20250401000000",
                "1",
                "example.com",
                "https://example.com/tsmc",
                "台積電" * 1000,
            ],
        ],
    )

    summary = stream.run_stream_probe(
        start_date="2025-04-01",
        end_date="2025-04-01",
        aliases=[stream.Alias("2330", "台積電")],
        max_files=1,
        max_download_mb=0.000001,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=[str(zip_path)],
        repo_root=tmp_path,
    )

    temp_raw_root = tmp_path / "data/raw/news/gdelt_probe_tmp"
    assert summary["completed"] is False
    assert summary["max_download_mb_exceeded"] is True
    assert summary["transfer_failure_reason"] == "max_download_mb_exceeded"
    assert summary["files_processed"] == 0
    assert summary["files_failed"] == 1
    assert summary["compressed_bytes_processed_successful"] == 0
    assert list(temp_raw_root.rglob("*.zip")) == []


def test_disk_limit_gb_must_be_positive(tmp_path: Path) -> None:
    with pytest.raises(stream.GdeltRawStreamError, match="disk_limit_gb"):
        stream.run_stream_probe(
            start_date="2025-04-01",
            end_date="2025-04-01",
            aliases=[stream.Alias("2330", "台積電")],
            max_files=1,
            max_download_mb=1,
            disk_limit_gb=0,
            output_dir="data/processed/news/gdelt_probe",
            source_urls=[],
            repo_root=tmp_path,
        )


def test_tiny_disk_limit_stops_probe_with_failure_summary(tmp_path: Path) -> None:
    zip_path = _write_synthetic_gkg_zip(
        tmp_path / "sample.gkg.csv.zip",
        [
            [
                "20250401000000-0",
                "20250401000000",
                "1",
                "example.com",
                "https://example.com/tsmc",
                "台積電",
            ],
        ],
    )

    summary = stream.run_stream_probe(
        start_date="2025-04-01",
        end_date="2025-04-01",
        aliases=[stream.Alias("2330", "台積電")],
        max_files=1,
        max_download_mb=1,
        disk_limit_gb=0.000000001,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=[str(zip_path)],
        repo_root=tmp_path,
    )

    output_dir = tmp_path / "data/processed/news/gdelt_probe"
    temp_raw_root = tmp_path / "data/raw/news/gdelt_probe_tmp"

    assert summary["completed"] is False
    assert summary["disk_limit_exceeded"] is True
    assert summary["disk_failure_reason"] == "disk_limit_gb_exceeded"
    assert summary["files_processed"] == 0
    assert summary["files_failed"] == 1
    assert summary["failed_files"][0]["error_type"] == "disk_limit_gb_exceeded"
    assert summary["matched_rows"] == 0
    assert (output_dir / "probe_summary.json").exists()
    assert list(temp_raw_root.rglob("*.zip")) == []


def test_keep_raw_false_respects_disk_limit_and_deletes_temp_raw(
    tmp_path: Path,
) -> None:
    zip_path = _write_synthetic_gkg_zip(
        tmp_path / "sample.gkg.csv.zip",
        [
            [
                "20250401000000-0",
                "20250401000000",
                "1",
                "example.com",
                "https://example.com/tsmc",
                "台積電",
            ],
        ],
    )
    disk_limit_gb = (zip_path.stat().st_size + 50_000) / 1_000_000_000

    summary = stream.run_stream_probe(
        start_date="2025-04-01",
        end_date="2025-04-01",
        aliases=[stream.Alias("2330", "台積電")],
        max_files=1,
        max_download_mb=1,
        disk_limit_gb=disk_limit_gb,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=[str(zip_path)],
        repo_root=tmp_path,
    )

    temp_raw_root = tmp_path / "data/raw/news/gdelt_probe_tmp"
    kept_raw_root = tmp_path / "data/raw/news/gdelt_probe"

    assert summary["completed"] is True
    assert summary["disk_limit_exceeded"] is False
    assert summary["files_processed"] == 1
    assert summary["matched_rows"] == 1
    assert list(temp_raw_root.rglob("*.zip")) == []
    assert not kept_raw_root.exists()


def test_keep_raw_true_counts_retained_raw_files_against_disk_limit(
    tmp_path: Path,
) -> None:
    first_zip = _write_synthetic_gkg_zip(
        tmp_path / "first.gkg.csv.zip",
        [
            [
                f"20250401000000-{index}",
                "20250401000000",
                "1",
                "example.com",
                f"https://example.com/tsmc/{index}",
                f"台積電 {index}",
            ]
            for index in range(100)
        ],
    )
    second_zip = _write_synthetic_gkg_zip(
        tmp_path / "second.gkg.csv.zip",
        [
            [
                f"20250401001500-{index}",
                "20250401001500",
                "1",
                "example.org",
                f"https://example.org/tsmc/{index}",
                f"台積電 {index}",
            ]
            for index in range(100)
        ],
    )
    disk_limit_gb = (
        first_zip.stat().st_size + second_zip.stat().st_size - 1
    ) / 1_000_000_000

    summary = stream.run_stream_probe(
        start_date="2025-04-01",
        end_date="2025-04-01",
        aliases=[stream.Alias("2330", "台積電")],
        max_files=2,
        max_download_mb=1,
        disk_limit_gb=disk_limit_gb,
        keep_raw=True,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=[str(first_zip), str(second_zip)],
        repo_root=tmp_path,
    )

    kept_raw_root = tmp_path / "data/raw/news/gdelt_probe"
    kept_raw_files = sorted(kept_raw_root.glob("*.zip"))

    assert summary["completed"] is False
    assert summary["disk_limit_exceeded"] is True
    assert summary["disk_failure_reason"] == "disk_limit_gb_exceeded"
    assert summary["files_processed"] == 1
    assert summary["files_failed"] == 1
    assert summary["matched_rows"] == 100
    assert summary["failed_files"][0]["error_type"] == "disk_limit_gb_exceeded"
    assert len(kept_raw_files) == 1
    assert kept_raw_files[0].name == "first.gkg.csv.zip"


def test_corrupt_zip_retry_counts_processed_file_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    valid_zip = _write_synthetic_gkg_zip(
        tmp_path / "valid.gkg.csv.zip",
        [
            [
                "20250401000000-0",
                "20250401000000",
                "1",
                "example.com",
                "https://example.com/tsmc",
                "台積電",
            ],
        ],
    )
    valid_bytes = valid_zip.read_bytes()
    corrupt_bytes = b"not a zip"
    attempts: list[str] = []

    def fake_download_to_path(
        url: str,
        destination: Path,
        *,
        remaining_bytes: int,
        remaining_disk_bytes: int | None = None,
        disk_usage_base_bytes: int = 0,
        disk_limit_bytes: int | None = None,
        timeout_seconds: float = 30.0,
    ) -> int:
        del remaining_bytes, remaining_disk_bytes, disk_usage_base_bytes
        del disk_limit_bytes, timeout_seconds
        attempts.append(url)
        if len(attempts) == 1:
            destination.write_bytes(corrupt_bytes)
            return len(corrupt_bytes)
        destination.write_bytes(valid_bytes)
        return len(valid_bytes)

    monkeypatch.setattr(stream, "download_to_path", fake_download_to_path)

    summary = stream.run_stream_probe(
        start_date="2025-04-01",
        end_date="2025-04-01",
        aliases=[stream.Alias("2330", "台積電")],
        max_files=1,
        max_download_mb=1,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=["https://example.com/synthetic.gkg.csv.zip"],
        repo_root=tmp_path,
    )

    output_dir = tmp_path / "data/processed/news/gdelt_probe"
    rows = _read_csv(output_dir / "matched_metadata_sample.csv")

    assert summary["completed"] is True
    assert summary["files_attempted"] == 1
    assert summary["download_attempts"] == 2
    assert summary["retry_count"] == 1
    assert summary["files_processed"] == 1
    assert summary["files_downloaded"] == 1
    assert summary["files_failed"] == 0
    assert summary["compressed_bytes_transferred_total"] == (
        len(corrupt_bytes) + len(valid_bytes)
    )
    assert summary["compressed_bytes_processed_successful"] == len(valid_bytes)
    assert summary["compressed_bytes_downloaded"] == len(valid_bytes)
    assert summary["matched_rows"] == 1
    assert summary["unique_urls"] == 1
    assert len(rows) == 1
    assert rows[0]["document_identifier"] == "https://example.com/tsmc"


def test_partial_download_failure_counts_transferred_bytes_on_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    valid_zip = _write_synthetic_gkg_zip(
        tmp_path / "valid.gkg.csv.zip",
        [
            [
                "20250401000000-0",
                "20250401000000",
                "1",
                "example.com",
                "https://example.com/tsmc",
                "台積電",
            ],
        ],
    )
    valid_bytes = valid_zip.read_bytes()
    partial_bytes = b"partial transfer"
    sources = iter(
        [
            _ScriptedSource([partial_bytes], TimeoutError("connection dropped")),
            _ScriptedSource([valid_bytes]),
        ]
    )

    def fake_open_source(url: str, *, timeout_seconds: float):
        del url, timeout_seconds
        return next(sources)

    monkeypatch.setattr(stream, "_open_source", fake_open_source)

    summary = stream.run_stream_probe(
        start_date="2025-04-01",
        end_date="2025-04-01",
        aliases=[stream.Alias("2330", "台積電")],
        max_files=1,
        max_download_mb=1,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=["https://example.com/interrupted.gkg.csv.zip"],
        repo_root=tmp_path,
    )

    output_dir = tmp_path / "data/processed/news/gdelt_probe"
    temp_raw_root = tmp_path / "data/raw/news/gdelt_probe_tmp"
    rows = _read_csv(output_dir / "matched_metadata_sample.csv")

    assert summary["completed"] is True
    assert summary["download_attempts"] == 2
    assert summary["retry_count"] == 1
    assert summary["files_processed"] == 1
    assert summary["files_failed"] == 0
    assert summary["compressed_bytes_transferred_total"] == (
        len(partial_bytes) + len(valid_bytes)
    )
    assert summary["compressed_bytes_processed_successful"] == len(valid_bytes)
    assert summary["matched_rows"] == 1
    assert len(rows) == 1
    assert rows[0]["document_identifier"] == "https://example.com/tsmc"
    assert list(temp_raw_root.rglob("*.zip")) == []


def test_partial_download_bytes_count_against_max_download_cap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    valid_zip = _write_synthetic_gkg_zip(
        tmp_path / "valid.gkg.csv.zip",
        [
            [
                "20250401000000-0",
                "20250401000000",
                "1",
                "example.com",
                "https://example.com/tsmc",
                "台積電",
            ],
        ],
    )
    valid_bytes = valid_zip.read_bytes()
    partial_bytes = b"partial transfer"
    sources = iter(
        [
            _ScriptedSource([partial_bytes], TimeoutError("connection dropped")),
            _ScriptedSource([valid_bytes]),
        ]
    )

    def fake_open_source(url: str, *, timeout_seconds: float):
        del url, timeout_seconds
        return next(sources)

    monkeypatch.setattr(stream, "_open_source", fake_open_source)

    summary = stream.run_stream_probe(
        start_date="2025-04-01",
        end_date="2025-04-01",
        aliases=[stream.Alias("2330", "台積電")],
        max_files=1,
        max_download_mb=(len(partial_bytes) + 1) / 1_000_000,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=["https://example.com/interrupted.gkg.csv.zip"],
        repo_root=tmp_path,
    )

    temp_raw_root = tmp_path / "data/raw/news/gdelt_probe_tmp"

    assert summary["completed"] is False
    assert summary["download_attempts"] == 2
    assert summary["retry_count"] == 1
    assert summary["files_processed"] == 0
    assert summary["files_failed"] == 1
    assert summary["max_download_mb_exceeded"] is True
    assert summary["transfer_failure_reason"] == "max_download_mb_exceeded"
    assert summary["compressed_bytes_transferred_total"] == (
        len(partial_bytes) + len(valid_bytes)
    )
    assert summary["compressed_bytes_processed_successful"] == 0
    assert summary["matched_rows"] == 0
    assert summary["failed_files"][0]["error_type"] == "max_download_mb_exceeded"
    assert list(temp_raw_root.rglob("*.zip")) == []


def test_corrupt_zip_records_bounded_failure_after_retries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corrupt_bytes = b"not a zip"

    def fake_download_to_path(
        url: str,
        destination: Path,
        *,
        remaining_bytes: int,
        remaining_disk_bytes: int | None = None,
        disk_usage_base_bytes: int = 0,
        disk_limit_bytes: int | None = None,
        timeout_seconds: float = 30.0,
    ) -> int:
        del url, remaining_bytes, remaining_disk_bytes, disk_usage_base_bytes
        del disk_limit_bytes, timeout_seconds
        destination.write_bytes(corrupt_bytes)
        return len(corrupt_bytes)

    monkeypatch.setattr(stream, "download_to_path", fake_download_to_path)

    summary = stream.run_stream_probe(
        start_date="2025-04-01",
        end_date="2025-04-01",
        aliases=[stream.Alias("2330", "台積電")],
        max_files=1,
        max_download_mb=1,
        output_dir="data/processed/news/gdelt_probe",
        source_urls=["https://example.com/corrupt.gkg.csv.zip"],
        repo_root=tmp_path,
    )

    assert summary["completed"] is False
    assert summary["files_attempted"] == 1
    assert summary["download_attempts"] == stream.MAX_FILE_RETRIES + 1
    assert summary["retry_count"] == stream.MAX_FILE_RETRIES
    assert summary["files_processed"] == 0
    assert summary["files_downloaded"] == 0
    assert summary["files_failed"] == 1
    assert summary["compressed_bytes_transferred_total"] == (
        len(corrupt_bytes) * (stream.MAX_FILE_RETRIES + 1)
    )
    assert summary["compressed_bytes_processed_successful"] == 0
    assert summary["matched_rows"] == 0
    assert summary["failed_files"] == [
        {
            "url": "https://example.com/corrupt.gkg.csv.zip",
            "error_type": "BadZipFile",
            "message": "File is not a zip file",
            "attempts": stream.MAX_FILE_RETRIES + 1,
        }
    ]


def test_output_dir_must_be_under_ignored_news_data(tmp_path: Path) -> None:
    zip_path = _write_synthetic_gkg_zip(
        tmp_path / "sample.gkg.csv.zip",
        [
            [
                "20250401000000-0",
                "20250401000000",
                "1",
                "example.com",
                "https://example.com/tsmc",
                "台積電",
            ]
        ],
    )

    with pytest.raises(stream.GdeltRawStreamError, match="ignored news data roots"):
        stream.run_stream_probe(
            start_date="2025-04-01",
            end_date="2025-04-01",
            aliases=[stream.Alias("2330", "台積電")],
            max_files=1,
            max_download_mb=1,
            output_dir="report/gdelt_probe",
            source_urls=[str(zip_path)],
            repo_root=tmp_path,
        )


def test_alias_csv_loader_uses_only_rows_enabled_for_matching(tmp_path: Path) -> None:
    aliases_path = tmp_path / "aliases.csv"
    aliases_path.write_text(
        "\n".join(
            [
                "ticker,alias,use_for_matching",
                "2330,TSMC,true",
                "1216,統一,false",
                "2603,Evergreen,0",
                "2454,MediaTek,yes",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    aliases = stream.load_aliases(aliases_path)

    assert aliases == [
        stream.Alias("2330", "TSMC"),
        stream.Alias("2454", "MediaTek"),
    ]


def test_cli_missing_alias_file_returns_controlled_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    aliases_path = tmp_path / "missing_aliases.csv"

    exit_code = stream.main(
        [
            "--start-date",
            "2025-04-01",
            "--end-date",
            "2025-04-01",
            "--aliases-file",
            str(aliases_path),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "Alias file not found" in captured.err
    assert str(aliases_path) in captured.err
    assert "Traceback" not in captured.err
