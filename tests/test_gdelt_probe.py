from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_probe_module():
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "probe_gdelt_metadata.py"
    )
    spec = importlib.util.spec_from_file_location("probe_gdelt_metadata", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load probe_gdelt_metadata.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = _load_probe_module()


def test_candidate_gkg_urls_are_capped_without_downloading() -> None:
    urls, total_count = probe.candidate_gkg_urls(
        start_date="2025-04-01",
        end_date="2025-04-01",
        max_files=2,
    )

    assert total_count == 96
    assert urls == [
        "http://data.gdeltproject.org/gdeltv2/20250401000000.gkg.csv.zip",
        "http://data.gdeltproject.org/gdeltv2/20250401001500.gkg.csv.zip",
    ]


def test_raw_probe_plan_includes_alias_paths_and_no_cloud_terms(
    tmp_path: Path,
) -> None:
    plan = probe.render_raw_probe_plan(
        start_date="2025-04-01",
        end_date="2025-04-01",
        company_alias="台積電",
        ticker="2330",
        max_files=1,
        repo_root=tmp_path,
    )

    assert "gdelt_raw_gkg_direct_download_dry_run" in plan
    assert "matched_company_alias: 台積電" in plan
    assert "matched_ticker: 2330" in plan
    assert "20250401000000.gkg.csv.zip" in plan
    assert "data/raw/news/gdelt" in plan
    assert "data/processed/news/gdelt" in plan
    assert "no files downloaded" in plan
    assert "BigQuery" not in plan
    assert "Google Cloud" not in plan


def test_path_labels_and_output_paths_are_local_and_ignored(tmp_path: Path) -> None:
    assert probe.sanitize_path_label("2330.TW") == "2330_TW"
    assert probe.sanitize_path_label("台積電") == "value"

    raw_dir = probe.build_default_raw_dir(
        start_date="2025-04-01",
        end_date="2025-04-02",
    )
    filtered = probe.build_default_filtered_output_path(
        start_date="2025-04-01",
        end_date="2025-04-02",
        ticker="2330.TW",
    )

    assert raw_dir.parts[:4] == ("data", "raw", "news", "gdelt")
    assert filtered.parts[:4] == ("data", "processed", "news", "gdelt")
    assert probe.validate_local_output_path(raw_dir, repo_root=tmp_path) == (
        tmp_path / raw_dir
    )
    assert probe.validate_local_output_path(filtered, repo_root=tmp_path) == (
        tmp_path / filtered
    )

    with pytest.raises(probe.GdeltProbeError, match="ignored local roots"):
        probe.validate_local_output_path("report/gdelt_probe.jsonl", repo_root=tmp_path)


def test_dry_run_main_prints_plan_without_network_or_files(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = probe.main(
        [
            "--dry-run",
            "--start-date",
            "2025-04-01",
            "--end-date",
            "2025-04-01",
            "--company-alias",
            "台積電",
            "--ticker",
            "2330",
            "--max-files",
            "1",
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "GDELT raw-file metadata probe dry run" in captured.out
    assert "20250401000000.gkg.csv.zip" in captured.out
    assert "no files downloaded" in captured.out
