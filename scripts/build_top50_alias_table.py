"""Build a local-only alias table for the TEJ-based top-50 universe."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd


def _add_src_to_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))


_add_src_to_path()

from quant_finance_project.news.aliases import (  # noqa: E402
    AliasGenerationError,
    GDELT_PROFILE_CONSERVATIVE,
    GDELT_PROFILE_EXPANDED_REVIEWED,
    GDELT_PROFILE_OUTPUT_NAMES,
    apply_gdelt_profile,
    build_alias_tables,
    gdelt_profile_summary,
    write_alias_outputs,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COMPANY_METADATA_PATH = Path("data/processed/tej/company_metadata.csv")
DEFAULT_UNIVERSE_PATH = Path("data/processed/tej/top50_universe_20250331.csv")
DEFAULT_OUTPUT_DIR = Path("data/processed/news/aliases")
ALLOWED_OUTPUT_ROOT = Path("data/processed/news")
PROFILE_CANDIDATES = "candidates"
PROFILE_CHOICES = (
    PROFILE_CANDIDATES,
    GDELT_PROFILE_CONSERVATIVE,
    GDELT_PROFILE_EXPANDED_REVIEWED,
)


def resolve_repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def validate_output_dir(output_dir: str | Path) -> Path:
    resolved = resolve_repo_path(output_dir).resolve(strict=False)
    allowed_root = (REPO_ROOT / ALLOWED_OUTPUT_ROOT).resolve(strict=False)
    if not (resolved == allowed_root or allowed_root in resolved.parents):
        raise AliasGenerationError(
            f"Alias outputs must stay under ignored local path {ALLOWED_OUTPUT_ROOT}."
        )
    return resolved


def require_input_file(path: Path, *, label: str) -> None:
    if path.exists():
        return
    raise AliasGenerationError(
        f"Missing required {label}: {path}\n"
        "Regenerate local TEJ processed outputs first with:\n"
        "  uv run python scripts/build_tej_market_data.py\n"
        "Do not create dummy TEJ files; TEJ-derived data must remain local-only."
    )


def build_top50_alias_table(
    *,
    company_metadata_path: str | Path = DEFAULT_COMPANY_METADATA_PATH,
    universe_path: str | Path = DEFAULT_UNIVERSE_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    allow_ambiguous_matching: bool = False,
    profile: str = PROFILE_CANDIDATES,
    write_profiles: bool = False,
) -> dict[str, Path]:
    """Build local alias candidates, review rows, and summary JSON."""

    if profile not in PROFILE_CHOICES:
        allowed = ", ".join(PROFILE_CHOICES)
        raise AliasGenerationError(f"Unknown alias profile {profile!r}: {allowed}")

    company_path = resolve_repo_path(company_metadata_path)
    universe_resolved_path = resolve_repo_path(universe_path)
    output_path = validate_output_dir(output_dir)

    require_input_file(company_path, label="company metadata file")
    require_input_file(universe_resolved_path, label="top-50 universe file")

    company_metadata = pd.read_csv(company_path, dtype=str).fillna("")
    universe = pd.read_csv(universe_resolved_path, dtype=str).fillna("")
    candidates, review, summary = build_alias_tables(
        universe,
        company_metadata,
        allow_ambiguous_matching=allow_ambiguous_matching,
    )

    profiles_to_write: list[str] = []
    if profile != PROFILE_CANDIDATES:
        profiles_to_write.append(profile)
    if write_profiles:
        profiles_to_write.extend(GDELT_PROFILE_OUTPUT_NAMES)
    profiles_to_write = list(dict.fromkeys(profiles_to_write))

    profile_frames = {
        profile_name: apply_gdelt_profile(candidates, profile=profile_name)
        for profile_name in profiles_to_write
    }
    profile_output_paths = {
        profile_name: output_path / GDELT_PROFILE_OUTPUT_NAMES[profile_name]
        for profile_name in profiles_to_write
    }
    summary = {
        **summary,
        "company_metadata_path": str(company_path),
        "universe_path": str(universe_resolved_path),
        "allow_ambiguous_matching": allow_ambiguous_matching,
        "selected_profile": profile,
        "profile_summaries": {
            profile_name: gdelt_profile_summary(profile_frame)
            for profile_name, profile_frame in profile_frames.items()
        },
        "profile_output_files": {
            profile_name: str(path)
            for profile_name, path in profile_output_paths.items()
        },
        "output_dir": str(output_path),
        "local_only": True,
    }
    output_paths = write_alias_outputs(
        candidates=candidates,
        review=review,
        summary=summary,
        output_dir=output_path,
    )
    for profile_name, profile_frame in profile_frames.items():
        output_path_for_profile = profile_output_paths[profile_name]
        profile_frame.to_csv(output_path_for_profile, index=False)
        output_paths[f"gdelt_{profile_name}"] = output_path_for_profile
    return output_paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build local-only top-50 company alias tables from TEJ outputs."
    )
    parser.add_argument(
        "--company-metadata",
        default=str(DEFAULT_COMPANY_METADATA_PATH),
        help="Path to local data/processed/tej/company_metadata.csv.",
    )
    parser.add_argument(
        "--universe",
        default=str(DEFAULT_UNIVERSE_PATH),
        help="Path to local data/processed/tej/top50_universe_20250331.csv.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Ignored local output directory under data/processed/news/.",
    )
    parser.add_argument(
        "--allow-ambiguous-matching",
        action="store_true",
        help=(
            "Keep ambiguous aliases flagged but set use_for_matching=true. "
            "Default is conservative false."
        ),
    )
    parser.add_argument(
        "--profile",
        choices=PROFILE_CHOICES,
        default=PROFILE_CANDIDATES,
        help=(
            "Additional GDELT allowlist profile to write. "
            "Use expanded_reviewed for the current top-50 GDELT route."
        ),
    )
    parser.add_argument(
        "--write-profiles",
        action="store_true",
        help="Write both GDELT conservative and expanded-reviewed allowlists.",
    )
    args = parser.parse_args(argv)

    try:
        outputs = build_top50_alias_table(
            company_metadata_path=args.company_metadata,
            universe_path=args.universe,
            output_dir=args.output_dir,
            allow_ambiguous_matching=args.allow_ambiguous_matching,
            profile=args.profile,
            write_profiles=args.write_profiles,
        )
    except AliasGenerationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("Alias table outputs written locally:")
    for label, path in outputs.items():
        print(f"- {label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
