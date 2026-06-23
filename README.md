# Quant Finance Course Project

This repository is for a Quantitative Finance course project.

The active first-phase project direction is a Taiwan-market replication and adaptation of **The Hype Index: an NLP-driven Measure of Market News Attention** (arXiv:2506.06329). The report title may remain Taiwan 50 Hype Index, while the first implementation operationalizes the universe as a TEJ-based fixed top-50 market-cap listed-stock universe selected as of 2025-03-31.

## Current stage

- Course assignments
- Paper reading notes
- Taiwan Hype Index architecture design notes
- Taiwan Hype Index data-source and universe plan
- Taiwan Hype Index news-source feasibility audit
- Taiwan Hype Index news-acquisition feasibility sprint
- GDELT metadata prototype plan
- Minimal Python project setup

## Repository layout

- `AGENTS.md`: repository-wide instructions for Codex and AI-assisted contributors
- `docs/`: paper summaries, formulas, architecture notes, and Taiwan Hype Index data plans
- `assignments/`: course assignments
- `report/`: progress logs, report drafts, curated results, and figures
- `data/`: local data area; raw and processed data are not committed by default

## Local TEJ cleaning

When the licensed TEJPro manual exports are present under `data/raw/tej/`, regenerate the ignored processed market-data files with:

```bash
uv run python scripts/build_tej_market_data.py
```

The script writes cleaned metadata, the daily market panel, the fixed top-50 universe, weekly market-cap weights, and a date-labeled validation summary under `data/processed/tej/`. These files remain local-only and are not Hype Index or news-count results.

Build the local-only top-50 alias review tables after TEJ processed outputs exist:

```bash
uv run python scripts/build_top50_alias_table.py
```

For the current GDELT raw GKG probe route, generate the expanded-reviewed allowlist:

```bash
uv run python scripts/build_top50_alias_table.py --profile expanded_reviewed
```

The alias tables are TEJ-derived and are written under ignored `data/processed/news/aliases/`. Pure ticker aliases and uncurated short aliases are disabled by default for GDELT matching.

## Optional GDELT metadata dry run

The GDELT prototype is a metadata feasibility step only. It follows the zero-cost route: no Google Cloud, BigQuery, paid API, billing setup, or cloud credentials are required. The dry run prints candidate raw GDELT file URLs and local ignored output paths without downloading files:

```bash
uv run python scripts/probe_gdelt_metadata.py --dry-run --company-alias 台積電 --ticker 2330 --start-date 2025-04-01 --end-date 2025-04-02
```

Any later live GDELT outputs must remain local under ignored `data/raw/news/gdelt/` or `data/processed/news/gdelt/` paths.

The current source-discovery result is documented in `docs/taiwan_hype_index_news_acquisition_feasibility.md`: GDELT raw GKG direct download is the recommended zero-cost route for the next bounded metadata prototype; BigQuery remains rejected for this project.

The first implementation uses an 8-week pilot news window, 2025-04-05 to 2025-05-30, with Saturday-to-Friday weekly bins. The selected GDELT acquisition uses two completed 4-week chunks; the previously planned third chunk is excluded because of a sustained missing raw GKG archive block. See `docs/taiwan_hype_index_news_acquisition_feasibility.md` for the selected chunk commands and local-only output paths.

For a bounded streaming feasibility probe that does not keep raw GDELT files by default:

```bash
uv run python scripts/probe_gdelt_raw_stream.py --start-date 2025-04-01 --end-date 2025-04-01 --max-files 8 --max-download-mb 50
```

Add `--execute` only for an explicit live probe. The raw-stream probe also accepts
`--workers` for bounded file-level parallelism; the default `--workers 1`
preserves sequential behavior, while local diagnostics can start with
`--workers 8`, `--workers 12`, or `--workers 16`. Start with `--workers 12` or
lower unless the machine, network, and disk budget have already been checked.
Use `--worker-backend thread` for the default downloader/parser worker path, or
`--worker-backend process` when CPU-bound parse / alias-match profiling shows
that Python threads are not scaling. The process backend keeps transfer and disk
accounting in the parent process, then parses one local temporary zip per worker
process. Process-pool startup or submission failures are reported as controlled
probe errors with an explicit `--worker-backend thread` fallback suggestion;
the probe does not silently fall back because that would make timing comparisons
ambiguous.
Long-running live GDELT downloads should be started manually in a terminal, not
inside Codex.

For alias-review diagnostics, add audit and profiling options as needed:

- `--matched-sample-size N` controls the global matched metadata sample size
  when per-ticker sampling is not enabled.
- `--sample-per-ticker N` writes up to `N` deterministic sample rows per ticker,
  which helps inspect lower-volume tickers such as `2382`.
- `--profile-performance` writes timing fields to `probe_summary.json` and a
  `per_file_metrics.csv` file for download / parse / match bottleneck review.
- `--shard-output-dir DIR` writes one small JSON result shard per candidate
  GKG file, including per-file counts, timing, and matched metadata samples with
  audit fields.
- `--resume` reuses validated successful / missing-archive shard results and
  recomputes missing, stale, malformed, or failed shards.
- `--merge-only` rebuilds final outputs from existing shard results without
  downloading or parsing files.

Shard reuse is guarded by a run fingerprint. Each shard and the final
`probe_summary.json` record the alias-content digest, alias path for audit,
matching-semantics version, output/audit schema versions, and sample options.
Each shard also records the expected candidate index, URL, file name, and
timestamp, and these candidate fields are validated before reuse.
`--resume` reuses only matching-fingerprint completed shards and recorded
missing-archive shards; stale, malformed, or failed shards are recomputed.
`--merge-only` fails with a controlled error if a required shard has a
mismatched fingerprint, mismatched candidate identity, is malformed, or records
a failed attempt, so alias-policy changes, copied shards, and stale failures
cannot be silently mixed.

The matched metadata sample includes `matched_alias`, `matched_alias_type`,
`matched_field_name`, and a bounded `matched_text_excerpt` from the allowed GKG
content / entity / name fields. It does not use URL, source, or
`DocumentIdentifier` metadata for matching and does not store article text.

The raw probe uses a token-to-candidate alias matcher index for acquisition
speed. Latin aliases are indexed by a deterministic anchor token and still
confirmed with the existing token-boundary regex; CJK aliases can be selected by
their first CJK character and still use substring confirmation. This reduces
per-row alias scanning without changing the matching scope or count semantics.
On the bounded 2025-05-14 manual v5 process-backend benchmark, the 96-file run
improved from 164.295 seconds before the index to 119.105 seconds after it,
with the same stock-day counts, matched-row total, and unique-URL total.

The selected alias file for the next full 8-week rerun is the local manual v5
allowlist:

```text
data/processed/news/aliases/top50_alias_allowlist_gdelt_manual_reviewed_v5_recommended.csv
```

Manual v5 keeps the v4 TSMC / MediaTek / Hon Hai / Foxconn / ASUS / Quanta
Computer decisions and disables only the additional bare aliases with clear
false-positive evidence: `Largan`, `Yuanta`, and `Novatek`. Use the process
backend for the next selected 8-week rerun:

```bash
uv run python scripts/probe_gdelt_raw_stream.py \
  --execute \
  --start-date 2025-04-05 \
  --end-date 2025-05-02 \
  --max-files 2688 \
  --max-download-mb 20000 \
  --disk-limit-gb 5 \
  --max-missing-files 20 \
  --workers 8 \
  --worker-backend process \
  --profile-performance \
  --matched-sample-size 5000 \
  --sample-per-ticker 50 \
  --aliases-file data/processed/news/aliases/top50_alias_allowlist_gdelt_manual_reviewed_v5_recommended.csv \
  --output-dir data/processed/news/gdelt_pilot_8w_manual_v5/chunk_20250405_20250502 \
  --shard-output-dir data/processed/news/gdelt_pilot_8w_manual_v5/shards_20250405_20250502 \
  --resume

uv run python scripts/probe_gdelt_raw_stream.py \
  --execute \
  --start-date 2025-05-03 \
  --end-date 2025-05-30 \
  --max-files 2688 \
  --max-download-mb 20000 \
  --disk-limit-gb 5 \
  --max-missing-files 20 \
  --workers 8 \
  --worker-backend process \
  --profile-performance \
  --matched-sample-size 5000 \
  --sample-per-ticker 50 \
  --aliases-file data/processed/news/aliases/top50_alias_allowlist_gdelt_manual_reviewed_v5_recommended.csv \
  --output-dir data/processed/news/gdelt_pilot_8w_manual_v5/chunk_20250503_20250530 \
  --shard-output-dir data/processed/news/gdelt_pilot_8w_manual_v5/shards_20250503_20250530 \
  --resume
```

After the two selected 8-week pilot chunks exist locally, build the zero-filled stock-week news-count panel with explicit input directories:

```bash
uv run python scripts/build_gdelt_weekly_counts.py \
  --pilot-start-date 2025-04-05 \
  --pilot-end-date 2025-05-30 \
  --universe-file data/processed/tej/top50_universe_20250331.csv \
  --input-dir data/processed/news/gdelt_pilot_8w_manual_v5/chunk_20250405_20250502 \
  --input-dir data/processed/news/gdelt_pilot_8w_manual_v5/chunk_20250503_20250530 \
  --output-dir data/processed/news/gdelt_pilot_8w_manual_v5/weekly_counts
```

If the local chunk directories still live under `data/processed/news/gdelt_pilot_12w/`, keep that parent in the two `--input-dir` paths; the script does not assume a fixed parent directory name.

This aggregation writes local-only count tables. It does not compute a Hype Index or join market-cap weights.
Capped GDELT probe outputs are diagnostics only; aggregation inputs must account
for the uncapped GDELT candidate file grid before zero-filled weeks are valid.
The current `news_count_unique_urls` definition is the sum of stock-day unique
GDELT document counts within each stock-week. It is the main count used by the
bounded 8-week pilot, while `matched_rows` is diagnostic only. This is not full
ticker-week cross-day URL deduplication; exact article-level weekly counts would
require retaining URL-level matched rows, not only `stock_day_counts.csv`.

After the Goal 3A news-count panel and TEJ weekly market-cap weights both exist
locally, build the Hype-ready input panel:

```bash
uv run python scripts/build_hype_input_panel.py \
  --pilot-start-date 2025-04-05 \
  --pilot-end-date 2025-05-30 \
  --news-counts-file data/processed/news/gdelt_pilot_8w_manual_v5/weekly_counts/stock_week_news_counts_20250405_20250530.csv \
  --market-weights-file data/processed/tej/weekly_market_cap_weights_20250401_20260331.csv \
  --universe-file data/processed/tej/top50_universe_20250331.csv \
  --output-dir data/processed/hype_index/pilot_8w_manual_v5
```

This join writes local-only Hype-ready inputs under ignored
`data/processed/hype_index/` paths. It joins TEJ weekly market-cap weights and
adds a weekly total news-count diagnostic, but it still does not compute raw
Hype Index or market-cap-adjusted Hype Index values.

After the Hype-ready input panel exists locally, compute the weekly raw Hype and
market-cap-adjusted Hype Index outputs:

```bash
uv run python scripts/build_hype_indices.py \
  --pilot-start-date 2025-04-05 \
  --pilot-end-date 2025-05-30 \
  --input-panel-file data/processed/hype_index/pilot_8w_manual_v5/hype_input_panel_20250405_20250530.csv \
  --output-dir data/processed/hype_index/pilot_8w_manual_v5/indices
```

These outputs remain local-only under ignored `data/processed/hype_index/`
paths. The script writes stock-week Hype Index values and summary diagnostics;
zero-news weeks are retained with missing Hype values. It does not create
figures, notebooks, forecasts, or portfolio results.

After the Goal 3C outputs exist locally, build the report-ready 8-week pilot
tables and figures:

```bash
uv run --group report python scripts/build_hype_report_artifacts.py \
  --hype-panel-file data/processed/hype_index/pilot_8w_manual_v5/indices/hype_index_panel_20250405_20250530.csv \
  --weekly-summary-file data/processed/hype_index/pilot_8w_manual_v5/indices/weekly_hype_summary_20250405_20250530.csv \
  --stock-summary-file data/processed/hype_index/pilot_8w_manual_v5/indices/stock_hype_summary_20250405_20250530.csv \
  --hype-summary-json data/processed/hype_index/pilot_8w_manual_v5/indices/hype_index_summary_20250405_20250530.json \
  --chunk-summary-json data/processed/news/gdelt_pilot_8w_manual_v5/chunk_20250405_20250502/probe_summary.json \
  --chunk-summary-json data/processed/news/gdelt_pilot_8w_manual_v5/chunk_20250503_20250530/probe_summary.json \
  --include-market-quant \
  --daily-market-panel-file data/processed/tej/daily_market_panel_20250401_20260331.csv \
  --weekly-market-weights-file data/processed/tej/weekly_market_cap_weights_20250401_20260331.csv \
  --universe-file data/processed/tej/top50_universe_20250331.csv \
  --company-metadata-file data/processed/tej/company_metadata.csv \
  --tej-validation-json data/processed/tej/validation_summary_20250401_20260331.json \
  --raw-tej-return-file data/raw/tej/tej_top50_daily_adjusted_price_exrights_panel_20250401_20260331.csv \
  --market-background-start 2025-04-01 \
  --market-background-end 2026-03-31 \
  --hype-trading-start 2025-04-07 \
  --hype-trading-end 2025-05-29 \
  --results-dir report/results/pilot_8w_manual_v5 \
  --figures-dir report/figures/pilot_8w_manual_v5 \
  --top-n 10 \
  --figure-dpi 160
```

This reporting step consumes existing Hype outputs and writes curated artifacts
under `report/results/pilot_8w_manual_v5/` and
`report/figures/pilot_8w_manual_v5/`. It does not recompute Goal 3A, Goal 3B,
or Goal 3C, and it does not create the final notebook. With
`--include-market-quant`, Goal 4B adds notebook-ready one-year TEJ market
background tables, sector-level Hype aggregation, return / volatility
diagnostics, revised heatmap and scatter figures, and key-stock case-study
figures. The market background period is 2025-04-01 to 2026-03-31, while the
Hype-window TEJ trading-date comparison is 2025-04-07 to 2025-05-29; the
2025-05-30 news date is not forced into TEJ market data. The
`--chunk-summary-json` inputs are optional for the script in general, but they
are required to reproduce the current report tables that include GDELT
acquisition diagnostics.

Goal 4C converts stock-level and sector-level cross-sectional reporting to
pooled Hype only. Report rankings, tables, and attention-versus-size scatter
figures use total pilot-window news share divided by pooled market-cap weight,
not the arithmetic mean of weekly Hype values. Weekly Hype remains in the
report artifacts only for time-path heatmaps, key-stock weekly case studies,
and contemporaneous descriptive return / volatility comparisons.

The completed manual-v5 local pilot has 400 Goal 3A stock-week news-count rows,
400 Goal 3B Hype-ready input rows, and 400 Goal 3C Hype Index rows. All three
validation summaries passed. The two selected GDELT chunks processed 5,372 of
5,376 candidate files, missed 4 archive files, failed 0 files, and produced
7,107 diagnostic matched rows. Weekly total `news_count_unique_urls` values are
1,225, 1,343, 737, 836, 646, 808, 884, and 628.

## Planned direction

The project direction is:

1. a TEJ-based fixed top-50 market-cap universe and documented data-source plan;
2. stock and sector news-count Hype Index construction;
3. market-cap-adjusted Hype Index construction;
4. empirical analysis against events and realized volatility;
5. report-ready documentation of assumptions, risks, and limitations.

Sentiment, forecasting, LLM-assisted Black-Litterman, and portfolio workflows are outside the active first phase.

No live trading, broker integration, or financial advisory functionality is intended.
