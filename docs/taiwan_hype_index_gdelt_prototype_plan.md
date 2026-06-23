# Taiwan Hype Index GDELT Raw-File Prototype Plan

## Purpose

This note defines the next small prototype after the revised news-source feasibility audit. The prototype should test whether GDELT 2.0 raw data files can support a zero-cost Taiwan Hype Index news-count baseline for a TEJ-based fixed top-50 market-cap universe.

This is not the production news-count pipeline. It should not compute the Hype Index, should not download a full-year news panel, and should not store article text. Its job is to verify file selection, metadata availability, alias matching risk, local parsing burden, and local output boundaries before any larger collection step.

## Why Raw GDELT Files First

The project now has a hard zero-cost / no-cloud constraint: the first implementation should not require Google Cloud, BigQuery, paid APIs, billing setup, or cloud credentials. Under that constraint, GDELT raw data files are the preferred GDELT route because they are publicly downloadable without BigQuery.

GDELT BigQuery remains technically feasible, but it is not selected for this project. The GDELT DOC API remains useful only for recent exploratory checks and should not be treated as the production historical source for 2025-04-01 to 2026-03-31 when official documentation limits start/end datetime search to the last 3 months.

The 2026-06-21 acquisition feasibility sprint confirmed that selected 2025 and 2026 raw GKG files were reachable through the public raw-file host and that tiny in-memory scans can find Taiwan large-cap company aliases. The same sprint estimated that a naive full-window GKG download would involve about 35,040 compressed files and roughly 147 GB using a small sample average, so the prototype should stream, filter, and discard non-matching rows rather than storing the full raw year locally.

## What The Tiny Prototype Should Test

The first prototype should be a dry run by default:

1. Select 3 to 5 high-visibility companies from the TEJ top-50 universe.
2. Use conservative aliases, such as official Chinese name, common Chinese short name, official English name, and ticker.
3. Select a very small date window inside 2025-04-01 to 2026-03-31, such as one trading day or one week.
4. Enumerate the candidate GDELT raw GKG file URLs and local ignored output paths.
5. Do not download files unless the user explicitly approves a live tiny probe.
6. If a live probe is later approved, download only a small number of compressed metadata files and filter locally.
7. Manually inspect returned metadata for false positives, duplicates, and missing local Taiwan coverage.

The first prototype should answer:

- Are the expected raw GDELT file names available for the selected window?
- Which metadata fields are practical to parse locally?
- Are URLs or document identifiers stable enough for deduplication?
- Are source domains concentrated in a few syndicated feeds?
- Do Chinese short aliases create false positives?
- How large is the local storage and parsing burden for a small window?

## Required Metadata Fields

The prototype should attempt to retain only metadata needed for feasibility review and later count construction:

| Field | Purpose |
|---|---|
| `document_identifier` or `url` | Stable article/document key for deduplication and manual review. |
| `source` | Source name or domain for source-bias and duplicate checks. |
| `timestamp` | Publication or ingestion time for date-window assignment. |
| `source_country` or `language` | Coverage diagnostics when available. |
| `matched_company_alias` | Alias that triggered the local filter. |
| `matched_ticker` | TEJ ticker associated with the alias. |
| `query_window` | Start and end dates used for the probe. |
| `query_method` | Raw-file list / GKG local-filter method and filter version. |

If the selected GKG raw files do not expose a stable title field, the prototype should not invent one. A later source-specific validation step may be needed for headline-level review.

## Local-Only Output Rule

Article text should not be stored. Query results, if any are produced, are local-only until redistribution constraints are reviewed. Live outputs must go only under ignored local directories such as:

- `data/raw/news/gdelt/`
- `data/processed/news/gdelt/`

No GDELT result files, article metadata exports, raw article pages, or derived news-count tables should be committed at this stage.

## Key Risks

- Large data volume: raw GDELT files are frequent and compressed; full-period collection can become large quickly.
- Local parsing burden: direct files require download, decompression, schema handling, and local filtering.
- Duplicate articles: the same story may appear through multiple URLs, mirrors, or translated / syndicated copies.
- Syndicated reposts: a single source feed may create many rows that inflate attention counts.
- Alias false positives: short Chinese company names, brand names, and group names can match unrelated articles.
- Missing local Taiwan coverage: GDELT's global scope may not fully cover Taiwan finance media.
- No stable title field: GKG metadata may be enough for counts and URL review but not for title-level filtering.
- Terms / redistribution: even if GDELT metadata is public, original article text and publisher content remain copyrighted.

## Prototype Tooling

The active prototype should be a raw-file dry run:

```bash
uv run python scripts/probe_gdelt_metadata.py --dry-run --company-alias 台積電 --ticker 2330 --start-date 2025-04-01 --end-date 2025-04-02
```

Dry-run mode prints candidate raw GDELT GKG URLs, the conservative alias filter, and the ignored local output path that would be used if a live tiny probe is later approved. It does not download files and does not require BigQuery credentials.

The dry-run helper uses the verified raw-file route under `http://data.gdeltproject.org/gdeltv2/`. Live downloading is intentionally not implemented in this helper.

The SQL templates under `queries/gdelt/` are archived reference material only. They are not part of the selected zero-cost route because they require BigQuery.

## Next Implementation Boundary

The next implementation goal should be a local dry run over a tiny date window, followed only by an explicitly approved tiny raw-file download/filter test if the dry run is acceptable. It should not implement production collection, cross-source scraping, duplicate grouping, news counts, Hype Index formulas, report notebooks, or empirical results.
