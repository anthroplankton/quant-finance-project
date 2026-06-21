"""Plan tiny zero-cost GDELT raw-file metadata probes.

The command prints candidate GDELT raw GKG file URLs and ignored local paths.
It does not download files, does not require Google Cloud, and does not use
BigQuery.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta
from pathlib import Path
import re
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
GDELT_V2_BASE_URL = "http://data.gdeltproject.org/gdeltv2"
DEFAULT_MAX_FILES = 8
MAX_ALLOWED_FILES = 200
ALLOWED_OUTPUT_ROOTS = (
    Path("data/raw/news/gdelt"),
    Path("data/processed/news/gdelt"),
)


class GdeltProbeError(RuntimeError):
    """Raised when the raw-file probe plan cannot be rendered."""


def parse_iso_date(value: str) -> date:
    """Parse YYYY-MM-DD dates and raise a compact CLI-friendly error."""

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise GdeltProbeError(f"Invalid date {value!r}; expected YYYY-MM-DD.") from exc


def validate_max_files(max_files: int) -> int:
    """Keep raw-file dry runs small and readable."""

    if max_files < 1 or max_files > MAX_ALLOWED_FILES:
        raise GdeltProbeError(
            f"max_files must be between 1 and {MAX_ALLOWED_FILES}; got {max_files}."
        )
    return max_files


def interval_timestamps(start_date: str, end_date: str) -> list[str]:
    """Return 15-minute GDELT timestamp labels for an inclusive date window."""

    start = parse_iso_date(start_date)
    end = parse_iso_date(end_date)
    if start > end:
        raise GdeltProbeError("start_date must be on or before end_date.")

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
    max_files: int = DEFAULT_MAX_FILES,
) -> tuple[list[str], int]:
    """Return a capped list of candidate GKG URLs and the uncapped count."""

    labels = interval_timestamps(start_date, end_date)
    max_files = validate_max_files(max_files)
    return [gdelt_gkg_url(label) for label in labels[:max_files]], len(labels)


def sanitize_path_label(value: str) -> str:
    """Return a conservative ASCII-ish label for local file names."""

    label = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return label or "value"


def build_default_raw_dir(*, start_date: str, end_date: str) -> Path:
    """Return the ignored raw directory for a possible future live probe."""

    return Path("data/raw/news/gdelt") / f"{start_date}_{end_date}"


def build_default_filtered_output_path(
    *,
    start_date: str,
    end_date: str,
    ticker: str,
) -> Path:
    """Return an ignored filtered metadata path for a possible future probe."""

    ticker_label = sanitize_path_label(ticker)
    start_label = start_date.replace("-", "")
    end_label = end_date.replace("-", "")
    return (
        Path("data/processed/news/gdelt")
        / f"gdelt_metadata_probe_{ticker_label}_{start_label}_{end_label}.jsonl"
    )


def validate_local_output_path(
    output_path: str | Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> Path:
    """Ensure any future outputs stay under ignored local data directories."""

    candidate = Path(output_path)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    resolved = candidate.resolve(strict=False)

    allowed_roots = [
        (repo_root / allowed_root).resolve(strict=False)
        for allowed_root in ALLOWED_OUTPUT_ROOTS
    ]
    if not any(resolved == root or root in resolved.parents for root in allowed_roots):
        allowed = ", ".join(str(root) for root in ALLOWED_OUTPUT_ROOTS)
        raise GdeltProbeError(
            f"Output path must be under one of the ignored local roots: {allowed}."
        )
    return resolved


def render_raw_probe_plan(
    *,
    start_date: str,
    end_date: str,
    company_alias: str,
    ticker: str,
    max_files: int = DEFAULT_MAX_FILES,
    repo_root: Path = REPO_ROOT,
) -> str:
    """Render a dry-run plan for a tiny direct-download GDELT probe."""

    urls, total_file_count = candidate_gkg_urls(
        start_date=start_date,
        end_date=end_date,
        max_files=max_files,
    )
    raw_dir = validate_local_output_path(
        build_default_raw_dir(start_date=start_date, end_date=end_date),
        repo_root=repo_root,
    )
    filtered_output = validate_local_output_path(
        build_default_filtered_output_path(
            start_date=start_date,
            end_date=end_date,
            ticker=ticker,
        ),
        repo_root=repo_root,
    )

    lines = [
        "# GDELT raw-file metadata probe dry run",
        "query_method: gdelt_raw_gkg_direct_download_dry_run",
        f"start_date: {start_date}",
        f"end_date: {end_date}",
        f"matched_ticker: {ticker}",
        f"matched_company_alias: {company_alias}",
        f"candidate_file_count_uncapped: {total_file_count}",
        f"candidate_file_urls_shown: {len(urls)}",
        "candidate_file_urls:",
    ]
    lines.extend(f"- {url}" for url in urls)
    if len(urls) < total_file_count:
        lines.append(f"- ... {total_file_count - len(urls)} additional URL(s) omitted")
    lines.extend(
        [
            "local_paths_if_live_probe_is_later_approved:",
            f"- raw_download_dir: {raw_dir}",
            f"- filtered_metadata_jsonl: {filtered_output}",
            "filtering_rule:",
            "- decompress each selected GKG CSV locally",
            "- retain metadata rows whose relevant text fields contain the exact alias",
            "- keep URL/document identifier, source, timestamp, matched alias, ticker, and query window",
            "safety:",
            "- dry run only; no files downloaded",
            "- article text must not be stored",
            "- outputs, if later produced, must remain ignored local files",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Print a dry-run plan for a tiny zero-cost GDELT raw GKG metadata probe."
        )
    )
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD.")
    parser.add_argument("--company-alias", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Accepted for clarity; the command is always dry-run only.",
    )
    args = parser.parse_args(argv)

    try:
        plan = render_raw_probe_plan(
            start_date=args.start_date,
            end_date=args.end_date,
            company_alias=args.company_alias,
            ticker=args.ticker,
            max_files=args.max_files,
        )
    except GdeltProbeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(plan, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
