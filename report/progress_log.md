# Progress Log

## 2026-06-23

### Goal 4B market quant and notebook-ready artifacts

* Extended the report-artifact builder to add Goal 4B notebook-ready outputs on
  top of the selected manual-v5 Goal 4A artifacts.
* Added one-year TEJ market-background tables, TEJ validation summary,
  universe and sector market-structure summaries, full-sample versus
  Hype-window equal-weight return statistics, contemporaneous Hype / return /
  volatility correlations, key-stock case-study rows, and sector-level Hype
  summaries.
* Regenerated revised Hype figures with shorter two-line week labels for
  heatmaps, added a zoomed attention-versus-size scatter, and added an
  attention-size imbalance chart.
* Added market quant figures for sector structure, equal-weight cumulative
  return, 20-day rolling volatility, return distributions, Hype versus weekly
  return / volatility, sector Hype, and key-stock case studies for `2330`,
  `2454`, `2317`, and `2357`.
* Updated the Markdown notebook plan to use the final-notebook structure:
  one-year TEJ market background plus 8-week Hype main analysis.
* This step did not rerun live GDELT downloads, did not recompute Goal 3A,
  Goal 3B, or Goal 3C, did not change Hype formulas or weekly market-cap weight
  conventions, and did not create the final `.ipynb` notebook.

### Manual-v5 Goal 4A report artifacts

* Built report-ready artifacts for the selected manual-v5 8-week Taiwan Hype
  Index pilot from existing Goal 3C outputs and the two manual-v5 GDELT chunk
  summaries.
* The Goal 4A artifacts are under `report/results/pilot_8w_manual_v5/` and
  `report/figures/pilot_8w_manual_v5/`. Required tables, Matplotlib figures,
  `artifact_manifest.json`, `figure_index.csv`, and
  `figure_visual_qa_manifest.json` were generated.
* The two selected GDELT chunks covered 2025-04-05 to 2025-05-02 and
  2025-05-03 to 2025-05-30. They processed 5,372 of 5,376 candidate files,
  missed 4 files, failed 0 files, and produced 7,107 diagnostic matched rows.
* Goal 3A, Goal 3B, and Goal 3C each produced 400 rows with validation passed.
  Goal 3C produced 8 weekly summaries, 50 stock summaries, and
  `missing_hype_week_count` 0.
* Weekly total `news_count_unique_urls` values are 1,225, 1,343, 737, 836, 646,
  808, 884, and 628.
* This reporting step did not rerun live GDELT downloads, Goal 3A, Goal 3B,
  Goal 3C, or any prediction / sentiment / LLM / portfolio workflow, and it did
  not create the final notebook.

### Shard candidate validation and report command fix

* Fixed the remaining shard reuse issue in `scripts/probe_gdelt_raw_stream.py`: each shard now stores explicit candidate identity fields, and `--resume` / `--merge-only` validate candidate index, URL, file name, and timestamp before reuse.
* `--resume` recomputes shards whose candidate identity does not match the current candidate list. `--merge-only` rejects mismatched-candidate shards with a controlled `GdeltRawStreamError`.
* Updated the README Goal 4A artifact command to include the two manual-v5 GDELT chunk `probe_summary.json` inputs via `--chunk-summary-json`, so the documented command can reproduce report tables that include acquisition diagnostics.
* Manual v5 remains selected. No alias file was changed, no manual v6 alias file was created, no live GDELT download was run, no full one-week or 8-week rerun was run, no Goal 3A / Goal 3B / Goal 3C / Goal 4A command was run, and no report artifacts were regenerated.

### Failed-shard resume reliability fix

* Fixed the remaining shard/resume review issue in `scripts/probe_gdelt_raw_stream.py`: `--resume` now reuses only matching-fingerprint completed shards and recorded missing-archive shards. Failed or malformed shards are scheduled again and overwritten atomically only after the new attempt completes.
* `--merge-only` now rejects failed or malformed shard results with controlled `GdeltRawStreamError` messages instead of silently merging stale failures.
* Manual v5 remains the selected alias file. No alias file was changed, no manual v6 alias file was created, no live GDELT download was run, no full one-week or 8-week rerun was run, and no Goal 3A / Goal 3B / Goal 3C / Goal 4A output was recomputed.

### GDELT probe review fixes before full rerun

* Fixed two review issues in `scripts/probe_gdelt_raw_stream.py` before the full selected 8-week rerun.
* Added shard provenance validation: each shard and `probe_summary.json` now record a run fingerprint with alias-content digest, alias path for audit, matching-semantics version, output/audit schema versions, and sample options. `--resume` reuses only matching-fingerprint reusable shards and recomputes stale shards; `--merge-only` fails with a controlled error on mismatched shards.
* Added controlled process-backend startup/submission errors. If the process pool cannot start or accept work, the probe raises a controlled error that suggests `--worker-backend thread`; it does not silently fall back from process to thread.
* Manual v5 remains the selected alias file. The one-week v5 process-backend diagnostic for 2025-05-10 to 2025-05-16 completed successfully with 672 / 672 candidate files processed, no missing or failed files, 808 matched rows, 624 global unique URLs, and about 615.3 seconds elapsed with `--workers 8`.
* No alias file was changed, no manual v6 alias file was created, no full one-week diagnostic was rerun, no full 8-week pilot rerun was run, and no Goal 3A / Goal 3B / Goal 3C / Goal 4A output was recomputed.

### GDELT raw probe indexed matcher benchmark

* Added a token-to-candidate alias matcher index to reduce per-row alias scanning in the GDELT raw streaming probe. Latin aliases are selected by deterministic anchor tokens and still confirmed with token-boundary regex; CJK aliases are selected by first CJK character when possible and still confirmed with substring matching.
* Preserved the existing matching scope: only GKG content / entity / name fields are matched, while URL / source / `DocumentIdentifier` metadata remains excluded. Manual v5 alias policy was not changed and no manual v6 alias file was created.
* Re-ran bounded live benchmarks only for 2025-05-14 under `data/processed/news/perf_diagnostics/` with manual v5, `--workers 8`, and `--worker-backend process`: 12 files completed in 13.963 seconds, 24 files completed in 20.231 seconds, and 96 files completed in 119.105 seconds.
* The comparable pre-index 96-file process benchmark took 164.295 seconds. The indexed matcher kept 153 matched rows and 117 unique URLs, with identical `stock_day_counts.csv` for the comparable 96-file output; alias-match time fell from 623.668 seconds to 283.456 seconds.
* Updated the documented future full selected 8-week rerun commands to use manual v5 with `--matched-sample-size 5000`, `--sample-per-ticker 50`, shard output, profiling, process workers, and `--resume`.
* No one-week diagnostic was run, no full 8-week pilot rerun was run, no Goal 3A / Goal 3B / Goal 3C / Goal 4A output was recomputed, and no notebook or figure was created.

### Bounded GDELT probe performance benchmark

* Ran bounded live GDELT performance benchmarks only for 2025-05-14 under `data/processed/news/perf_diagnostics/`; no one-week diagnostic and no 8-week pilot rerun was executed.
* The first 12-file, 12-worker thread run was interrupted after it produced no completed-file progress within the initial observation window, which exposed that terminal quietness can occur while the first in-flight worker wave is still running.
* A completed 12-file, one-worker baseline showed the bottleneck was alias matching / parsing, not download: 264.655 seconds elapsed, 11.972 seconds downloading, 252.663 seconds parsing, and 237.786 seconds in alias matching.
* Optimized the probe by preparing alias matchers once per parsed file and casefolding each GKG match field once per row, preserving CJK substring matching, Latin token-boundary matching, and exclusion of URL / source / `DocumentIdentifier` metadata from matching.
* The same 12-file, one-worker benchmark after the optimization completed in 51.203 seconds with identical `stock_day_counts.csv` and `matched_metadata_sample.csv`; alias-match time fell to 23.710 seconds.
* Additional optimized 12-file thread benchmarks completed cleanly with identical counts: workers=4 completed in 47.314 seconds and workers=12 completed in 46.563 seconds. The small wall-clock gain from threads suggests remaining parsing work is CPU-bound under Python threads.
* The optimized 24-file, 12-worker benchmark completed cleanly in 87.560 seconds, with 24 files processed, no missing files, no failed files, 21 matched rows, and 11 unique URLs.
* No alias file was modified, no manual v5 alias file was created, no Goal 3A / Goal 3B / Goal 3C / Goal 4A output was recomputed, and no notebook or figure was created.

### GDELT raw probe process backend benchmark

* Added `--worker-backend process` as a bounded process-pool parse / match option for CPU-bound GDELT raw probe diagnostics. The parent process still downloads each raw zip and owns transfer / disk accounting; parser processes receive one local temporary zip path each and return metadata-only matches and metrics.
* Kept `--worker-backend thread` as the default path and preserved deterministic candidate-order merging, match-audit fields, `--sample-per-ticker`, and shard / resume / merge-only behavior.
* Re-ran bounded live benchmarks only for 2025-05-14 under `data/processed/news/perf_diagnostics/`: 12 files with thread workers=12 completed in 59.448 seconds; 12 files with process workers=4 completed in 26.099 seconds; 12 files with process workers=8 completed in 19.454 seconds.
* The matching 12-file thread and process outputs produced identical `stock_day_counts.csv` and identical `matched_metadata_sample.csv`, with 14 matched rows and 4 unique URLs.
* The 24-file process workers=8 benchmark completed in 27.058 seconds, with 24 files processed, 0 missing, 0 failed, 21 matched rows, and 11 unique URLs.
* The capped 96-file process workers=8 benchmark completed in 164.295 seconds, with all 96 files processed, 0 missing, 0 failed, 153 matched rows, and 117 unique URLs.
* This change does not modify alias files, does not create a manual v5 alias file, does not change matching scope or Hype methodology, does not run a full one-week diagnostic, and does not run the 8-week pilot.

### Manual v5 alias decision for selected 8-week rerun

* Verified the local manual v5 alias file exists and loads through the GDELT raw probe CLI: `data/processed/news/aliases/top50_alias_allowlist_gdelt_manual_reviewed_v5_recommended.csv`.
* Manual v5 is selected for the next full selected 8-week GDELT rerun. It is a conservative precision-oriented alias set based on v4.
* The v2 / v3 / v4 comparison used the same 2025-05-10 to 2025-05-16 diagnostic window. v2 fixed the TSMC undercount but had broad false positives for `2382` Quanta and `2892` First Financial; v3 reduced `2382` from 46 to 24 and `2892` from 29 to 0; v4 kept `2330` TSMC at 232, `2454` MediaTek at 176, `2317` Hon Hai / Foxconn at 132, fixed ASUS substring false positives through Latin token-boundary matching, reduced `2382` to 13, and kept `2892` at 0.
* Manual v5 keeps the v4 TSMC, MediaTek, Hon Hai / Foxconn, ASUS, and Quanta Computer decisions. It disables only three additional bare aliases with clear false-positive evidence: `Largan` for `3008`, `Yuanta` for `2885`, and `Novatek` for `3034`, while keeping precise variants such as `Largan Precision`, `Yuanta Financial`, `Yuanta Financial Holding`, and `Novatek Microelectronics`.
* The GDELT probe code still preserves Latin token-boundary matching, CJK substring matching, URL / source / `DocumentIdentifier` exclusion from matching, matched audit fields, performance profiling, process backend support, and shard / resume / merge-only support.
* No full 8-week GDELT rerun was run, no Goal 3A / Goal 3B / Goal 3C / Goal 4A output was recomputed, and no notebook or figure was created.

## 2026-06-22

### GDELT raw probe audit and performance diagnostics

* Added match-audit fields to the GDELT raw streaming probe metadata sample: `matched_alias`, `matched_alias_type`, `matched_field_name`, and bounded `matched_text_excerpt`.
* Added deterministic sample controls through `--matched-sample-size` and `--sample-per-ticker` so low-volume tickers can be reviewed without changing count semantics.
* Added `--profile-performance` timing summaries and `per_file_metrics.csv` for per-file elapsed, download, parse, and match-time diagnosis.
* Added optional per-file JSON shard output with `--shard-output-dir`, plus `--resume` and `--merge-only` workflows for interrupted diagnostics.
* Replaced batch-at-a-time worker scheduling with a continuously fed bounded executor while preserving deterministic final aggregation in candidate-file order.
* This update keeps manual v4 alias policy unchanged, does not create a v5 alias file, does not run live GDELT downloads, does not recompute Goal 3A, Goal 3B, Goal 3C, or Goal 4A outputs, and does not create a notebook or figure.

### GDELT raw probe bounded parallelism

* Added bounded file-level worker support to `scripts/probe_gdelt_raw_stream.py` through `--workers`, defaulting to `1` to preserve the original sequential execution path.
* The worker pool processes independent compressed GKG zip files, then the main process merges metadata-only matches and stock-day counts deterministically into the existing output files.
* The change is for local acquisition speed only. It does not change GDELT alias policy, matching scope, count definitions, weekly aggregation, or Hype Index formulas.
* Added synthetic offline tests comparing `--workers 1` with `--workers 4`, validating deterministic count output, parallel HTTP 404 handling, Latin token-boundary matching, CJK matching, metadata-field exclusion, explicit alias-file errors, and invalid worker-count errors.
* No live GDELT download was run, no Goal 3A, Goal 3B, Goal 3C, or Goal 4A output was recomputed, and no notebook or figure was created.

### Goal 4A report-ready 8-week Hype artifacts

* Added a reporting-only artifact builder for the 8-week Taiwan Hype Index pilot.
* The builder consumes existing Goal 3C Hype Index outputs and writes curated
  tables under `report/results/pilot_8w_manual_v5/` plus Matplotlib PNG figures
  and visual-QA manifests under `report/figures/pilot_8w_manual_v5/` for the
  selected manual-v5 run.
* Required outputs include pipeline, weekly, top-stock, zero-news, and methodology-note tables; required figures include weekly news counts, top-stock bar charts, raw and market-cap-adjusted Hype heatmaps, and the raw-Hype-versus-market-cap-weight scatter plot.
* The figure manifest and figure index provide objective visual-QA checks for file existence, image size, labels, and top-N label limits, but subjective aesthetics still require human review.
* This step does not download live GDELT data, does not rerun Goal 3A, Goal 3B, or Goal 3C, does not change Hype formulas, and does not create the final notebook.

### Goal 3D-lite methodology cleanup

* Clarified the first implementation as a bounded 8-week, paper-inspired Taiwan-market weekly adaptation rather than an exact article-level or full-year replication.
* Documented `news_count_unique_urls` as the sum of stock-day unique GDELT document counts within each stock-week, with `matched_rows` preserved as diagnostic only.
* Documented the current limitation that full ticker-week cross-day URL deduplication cannot be retrofitted from aggregate `stock_day_counts.csv`; future exact article-level counts require retaining URL-level matched rows.
* Updated Goal 3A and Goal 3C summaries to record count-definition metadata for later report-table work.
* Aligned Goal 3C zero-denominator behavior with the missing-data rule: zero-news weeks remain in the panel and get missing Hype values instead of aborting the whole build.
* No live GDELT download was run, no selected chunk changed, and no notebook or figure was created.

### Goal 3C weekly Hype Index computation

* Added a local-only Goal 3C pipeline that computes weekly raw Hype Index and market-cap-adjusted Hype Index values from the Goal 3B Hype-ready input panel.
* The implementation follows the local reference paper's core Hype Index definitions and adapts them to the project window, weekly frequency, TEJ-based fixed top-50 universe, GDELT `news_count_unique_urls`, and TEJ `weekly_market_cap_weight`.
* `raw_hype` is computed as each stock's weekly news-count share. `market_cap_adjusted_hype` is computed as `raw_hype / weekly_market_cap_weight` and is not normalized to sum to 1.
* The pipeline validates panel row counts, weekly news totals, market-cap weight sums, zero-news behavior, finite nonnegative positive-week Hype values, and missing zero-denominator Hype values before writing outputs.
* Invalid Goal 3C pilot-window inputs now fail through controlled `HypeIndexError` / CLI `Error:` handling rather than surfacing a traceback from the shared input-panel weekly-bin validator.
* Fractional or malformed count fields now fail validation before integer casting, so values such as `1.9` cannot be silently truncated before Hype calculation.
* Outputs remain local-only under ignored `data/processed/hype_index/` paths. No live GDELT download was run, no notebook or figure was created, and no forecast or portfolio result was computed.

### Goal 3B Hype-ready input panel join

* Added a local-only Goal 3B pipeline that joins the Goal 3A stock-week GDELT news-count panel with TEJ weekly market-cap weights for the active 8-week pilot.
* The join validates the 50 × 8 stock-week news-count panel, validates the selected TEJ weekly weights, checks that each selected week has exactly 50 tickers, confirms positive weights summing to 1, and requires each TEJ `weight_date` to fall inside the corresponding Saturday-to-Friday week.
* The join validates any existing news-count `week_index` against canonical Saturday-to-Friday weekly bins, then writes canonical `week_index` labels to the Hype-ready panel.
* The resulting panel includes `weekly_total_news_count_unique_urls` only as a diagnostic denominator candidate for a later raw Hype calculation. Goal 3B does not compute raw Hype Index, market-cap-adjusted Hype Index, or any news-count-to-weight ratio.
* Outputs are written under ignored `data/processed/hype_index/` paths. No live GDELT download was run, no notebook or figure was created, and no Hype Index result has been computed.

### Goal 3A local stock-week news-count aggregation

* Added a local-only aggregation pipeline that converts selected GDELT chunk-level `stock_day_counts.csv` files into a zero-filled stock-week news-count panel for the 8-week pilot.
* The aggregation validates each input chunk's `probe_summary.json`, rejects failed or incomplete chunks, rejects overlapping stock-day rows, validates matched tickers against the TEJ-based top-50 universe, and builds Saturday-to-Friday weekly bins.
* Hardened the aggregation so selected chunk date ranges must continuously cover the full pilot window before zero filling; omitted chunks, gaps, overlaps, or out-of-window chunks now fail validation instead of being interpreted as zero-news weeks.
* Hardened per-chunk file-grid validation so capped probe summaries and incomplete `files_processed + files_missing + files_failed` accounting now fail before zero filling. This prevents unattempted GDELT raw files from being interpreted as zero-news observations.
* Hardened per-chunk stock-day validation so stale or mismatched `stock_day_counts.csv` rows outside their own chunk's `probe_summary.json` date range now fail before aggregation.
* Hardened count reconciliation so empty, header-only, stale, or truncated `stock_day_counts.csv` files fail when they disagree with the paired `probe_summary.json` `matched_rows`. This prevents real matches from being converted into zero-news observations.
* The first implementation window remains 2025-04-05 to 2025-05-30, exactly 8 full weeks, so the fixed top-50 panel should contain 50 × 8 = 400 stock-week rows.
* `news_count_unique_urls` is defined as the sum of stock-day unique GDELT document counts within each stock-week. It is not full cross-day URL deduplication because the current probe output stores daily aggregate counts rather than a URL-level table.
* `matched_rows` is preserved as a diagnostic count. This step does not compute raw Hype Index, does not compute market-cap-adjusted Hype Index, and does not join TEJ weekly market-cap weights.
* Outputs are written under ignored `data/processed/news/` paths. No live GDELT download was run, no notebook was created, and no Hype Index result has been computed.

### First implementation window revised to 8 weeks

* Revised the first implementation GDELT / Hype Index pilot from the previously planned 12 weeks to an 8-week window: 2025-04-05 to 2025-05-30 inclusive.
* The selected window has exactly 56 calendar days and 8 full Saturday-to-Friday weekly bins, so the fixed top-50 stock-week panel should contain 50 × 8 = 400 rows before any missing-data exclusions.
* Selected only the two completed 4-week GDELT chunks: 2025-04-05 to 2025-05-02 and 2025-05-03 to 2025-05-30.
* Manual-v5 chunk 1 summary: completed=true, candidate files=2,688, files processed=2,686, files missing=2, files failed=0, matched rows=4,141, unique URLs=3,572.
* Manual-v5 chunk 2 summary: completed=true, candidate files=2,688, files processed=2,686, files missing=2, files failed=0, matched rows=2,966, unique URLs=2,401.
* Combined selected manual-v5 8-week evidence: candidate files=5,376, files processed=5,372, files missing=4, files failed=0, missing-file ratio about 0.074%, matched rows=7,107, and chunk-summary unique URLs=5,973.
* The previously planned 2025-05-31 to 2025-06-27 chunk is excluded from the first implementation because GDELT raw GKG files are almost continuously missing after `20250614180000` through `20250627234500`, with additional earlier missing files and a short missing segment around `20250612181500` to `20250612201500`.
* The 8-week pilot remains a bounded descriptive first implementation, not a full-year replication. Avoid strong time-series inference from only 8 weekly observations.
* GDELT outputs remain local-only under ignored `data/processed/news/` paths. At
  this window-selection documentation stage, no live GDELT download was run, no
  notebook was created, and the Hype Index result had not yet been computed.

## 2026-06-21

### GDELT expanded-reviewed alias policy hardening

* Added core Chinese short names such as `台積電`, `聯發科`, and `鴻海` to the explicit `expanded_reviewed` GDELT alias allowlist so standard Chinese company mentions are not dropped from pilot news counts.
* Kept pure ticker aliases disabled for GDELT matching and kept broad or ambiguous aliases such as `統一`, `長榮`, `台塑`, `南亞`, `國泰`, `富邦`, `第一`, `合庫`, and `台新` disabled.
* Kept generic English short names and acronyms such as `DELTA`, `FIRST`, and `CSC` disabled unless they appear as precise official full names or are explicitly curated later.
* Added synthetic regression tests confirming that curated Chinese and English aliases are enabled, unlisted short aliases remain disabled, GDELT matching stays limited to content / entity / name fields, and HTTP 404 missing-file handling remains intact.
* This update did not run a live GDELT download, did not create a notebook, and did not compute a Hype Index result.

### GDELT matching-scope hardening

* Restricted the GDELT raw streaming probe so alias matching uses only GKG content / entity / name fields such as themes, locations, persons, organizations, and `AllNames`.
* URL and source metadata fields such as `DocumentIdentifier`, `SourceCommonName`, source domains, record IDs, dates, and source collection identifiers are not used for company alias matching.
* Verified the existing HTTP 404 missing-file behavior with synthetic tests: missing raw GKG archive files are skipped without retrying, recorded in `files_missing` / `missing_files`, and tolerated only within the configured missing-file threshold.
* Corrected the pilot-window rationale: the window starts at the first full Saturday-to-Friday weekly bin after the TEJ market-panel start and still includes calendar news days during the Apr 5-6 holiday/weekend period.
* This update did not run a live GDELT download, did not create a notebook, and did not compute a Hype Index result.

### Superseded pilot window decision

* Initial planning shortened the first implementation research window from the full 2025-04-01 to 2026-03-31 market panel to a bounded pilot news window. This was later revised on 2026-06-22 to the active 8-week window: 2025-04-05 to 2025-05-30 inclusive.
* Defined weekly news bins as Saturday-to-Friday, ending on Fridays; the active window has exactly 56 calendar days and 8 full 7-day weeks.
* The active chunked GDELT acquisition plan uses two 28-day windows: 2025-04-05 to 2025-05-02 and 2025-05-03 to 2025-05-30.
* Market-cap weights should use the last available TEJ trading day within each weekly bin rather than assuming Friday is always a trading day.
* This is a documentation-only decision update. No notebook was created, and no Hype Index result has been computed.

### GDELT missing archive-file handling

* During the bounded GDELT acquisition attempt, chunk 2 initially hit a missing raw archive file at `20250503003000.gkg.csv.zip`.
* Updated the streaming probe so HTTP 404 raw GKG files are recorded as missing source files, skipped without retrying, and summarized separately from transient failures.
* Added a conservative missing-file threshold so occasional archive gaps can be tolerated while broader source-availability problems still stop the probe with `completed=false`.
* This update did not run a live GDELT download, did not create a notebook, and did not compute a Hype Index result.

### Goal 2F-Review GDELT expanded-reviewed alias allowlist

* Extended the local alias workflow so it can write a GDELT-specific `expanded_reviewed` allowlist under ignored `data/processed/news/aliases/`.
* The GDELT allowlist disables pure ticker aliases by default, keeps documented high-risk short names disabled, and enables only explicitly curated high-confidence Chinese short names and English brand aliases when present in the TEJ-derived metadata.
* Hardened `expanded_reviewed` so unlisted short aliases such as broad English words or acronyms remain disabled instead of being enabled by fallback logic.
* The workflow normalizes TEJ display marks such as trailing `*` before alias output while preserving source-column traceability and review notes.
* This step did not run a live GDELT probe, did not create a notebook, and did not compute a Hype Index result. Generated alias CSV files remain local-only and must not be committed.

### Goal 2F local top-50 alias table generator

* Added reusable alias-generation code for the TEJ-based top-50 universe.
* The alias generator reads local TEJ processed `company_metadata.csv` and `top50_universe_20250331.csv` files, then writes local-only alias candidates, review rows, and summary JSON under ignored `data/processed/news/aliases/`.
* Candidate aliases are generated from ticker, official Chinese name, Chinese short name, official English name, and English short name while preserving the source column.
* Short or broad aliases are flagged for review, including known ambiguous Taiwan-market aliases such as `統一`, `長榮`, `台塑`, `中鋼`, `國泰`, `富邦`, `第一`, `合庫`, and `台新`.
* The GDELT streaming probe can read alias CSV rows and only uses aliases where `use_for_matching` is true.
* This step did not create a committed alias table, did not run a 50-company GDELT probe, did not create a notebook, and did not compute a Hype Index result.

### Bounded GDELT raw streaming probe

* Added a streaming GDELT raw GKG feasibility probe that can dry-run by default or execute only with explicit `--execute`.
* The probe processes one compressed raw GKG zip file at a time, filters by a small alias list, writes metadata-only summaries under ignored `data/processed/news/` paths, and deletes temporary raw files unless `--keep-raw` is explicitly set.
* Fixed large-field CSV parsing by raising the CSV field-size limit before any GKG reader is created.
* Raised the explicit `max_files` safety cap enough for a 3,500-file month-scale probe while keeping a hard cap that rejects full-year-sized runs.
* Enforced `disk_limit_gb` during raw-file probing so local storage exhaustion stops the probe with `completed=false` and `disk_limit_gb_exceeded` instead of only being reported after completion.
* Added bounded retry handling for transient per-file download / partial-file errors, including transfer accounting for failed partial download attempts.
* Added synthetic offline tests for alias matching, large GKG fields, temporary raw-file cleanup, `max_files` and `max_download_mb` limits, ignored output-path enforcement, and complete count aggregation beyond the metadata sample cap.
* Stage A live smoke probe completed for 2025-04-01 with 8 / 8 files downloaded, 47,618,732 compressed bytes, 2 matched rows, 1 unique URL, and no kept raw zip files.
* Stage B full-day probe stopped at the configured 500 MB download cap while downloading `20250401193000.gkg.csv.zip`, before the 96-file day could complete. Stage C was not attempted because the ordered bounded run failed at Stage B.
* Fixed the raw headerless GKG schema mapping after review: the parser now treats fields as `GKGRECORDID`, `DATE`, `SourceCollectionIdentifier`, `SourceCommonName`, and `DocumentIdentifier`, keeping source domain separate from URL / document identifier.
* Fixed headered GKG detection so standard headered files are parsed by column names instead of falling back to raw positional indices.
* Reran the one-day live probe with a higher 800 MB cap. It completed 96 / 96 files, downloaded 635,221,763 compressed bytes, found 118 matched rows and 113 unique document identifiers, and wrote only ignored local metadata outputs. The matched sample now uses URL-like `document_identifier` values rather than source domains.
* This remains feasibility tooling only. It is not a full-year acquisition, not a production news-count pipeline, and not a Hype Index computation.
* No real news data files were created or committed.

### Goal 2D zero-cost news acquisition feasibility sprint

* Actively checked zero-cost / no-cloud news-data routes for the 2025-04-01 to 2026-03-31 Taiwan Hype Index window.
* Live-tested GDELT raw GKG file availability with small `HEAD` checks and tiny in-memory metadata scans for TSMC, Hon Hai, and MediaTek aliases. The probe found company-alias hits in the project period and saved no records.
* Estimated GDELT raw GKG size from a small sample: 96 files per day, 672 files per week, and 35,040 files for the full project window; a naive full-window compressed download would be roughly 147 GB using the sample average, so the next step should stream and filter selectively.
* Live-tested the Anue / Cnyes public Taiwan stock news metadata endpoint. It appears technically promising for historical metadata but remains a backup / manual-validation route until terms and stable access assumptions are reviewed.
* Checked CNA RSS, UDN / Economic Daily News, MoneyDJ, Common Crawl, GDELT DOC API, GDELT BigQuery, and MOPS as alternative or fallback routes.
* Selected GDELT raw GKG direct download as the recommended primary zero-cost route for the next bounded acquisition prototype.
* BigQuery remains rejected for this project because it requires Google Cloud / BigQuery access.
* No production news data was collected, no probe output files were saved, no notebook was created, and no Hype Index result was produced.

## 2026-06-20

### Zero-cost news-source route revision

* Revised the GDELT source plan to satisfy the zero-cost / no-cloud constraint.
* Reclassified GDELT BigQuery / GKG as technically feasible but not selected, because it requires Google Cloud / BigQuery access and may require billing or credentials.
* Reclassified GDELT DOC API as recent exploratory only, not the production historical source for the 2025-04-01 to 2026-03-31 project window.
* Promoted GDELT raw data files / direct download as the recommended zero-cost route for a tiny local feasibility probe.
* Updated the prototype plan and dry-run helper to enumerate raw GDELT file URLs without downloading files or requiring cloud credentials.
* No production news data was collected, no raw GDELT files were downloaded, and no Hype Index result was produced.

### Goal 2B GDELT metadata prototype plan

* Added a GDELT metadata prototype plan for a small feasibility step. This section has been superseded by the zero-cost route revision above.
* Added SQL templates for one-company and multi-company metadata probes under `queries/gdelt/`; these are now archived reference only.
* Added an optional dry-run-first probe script; it now enumerates raw GDELT file URLs without requiring BigQuery credentials.
* Added synthetic tests for dry-run rendering and ignored local output-path guards.
* No production news data was collected, no news-count pipeline was implemented, and no Hype Index result was produced.

### Goal 2A news-source feasibility audit

* Added a web-researched feasibility audit for candidate Taiwan Hype Index news sources.
* Initially identified GDELT 2.0 BigQuery / GKG metadata as the primary candidate for the next small retrospective prototype; this was superseded by the zero-cost / no-cloud route revision above.
* Recorded GDELT DOC API as an exploratory backup because official documentation is useful but a tiny local query hit HTTP 429.
* Recorded CNA RSS / public pages, Economic Daily News, MoneyDJ, and Anue / Cnyes as backup or manual-validation candidates, pending terms-of-use and stable access-method review.
* Recorded MOPS / public company announcements as event-context material only, not as the main Hype Index news-attention source.
* No production news data was collected, no news-count pipeline was implemented, and no Hype Index result was produced.

## 2026-06-19

### TEJPro data workflow update

* Shifted the first implementation plan to TEJPro manual exports only.
* Recorded the Phase 1 universe as a TEJ-based fixed top-50 market-cap listed-stock universe selected with TEJ market capitalization as of 2025-03-31.
* Recorded the market panel period as 2025-04-01 to 2026-03-31.
* Recorded `data/raw/tej/tej_company_basic_tse_current_minimal_20260615.csv` as the TEJ Company DB / 基本資料 export used for company metadata, ticker-name mapping, English / Chinese names, and industry classification.
* Recorded `data/raw/tej/tej_top50_daily_market_panel_20250401_20260331.csv` as the TEJ 股價資料庫 / 未調整股價(日) export used for daily close, shares outstanding, market cap, volume, and traded value.
* The Company DB basic data export passed format checks locally.
* The top-50 daily market panel export passed completeness checks locally.
* The raw TEJPro files are stored under `data/raw/tej/` and remain ignored by Git.
* TEJ raw data and TEJ-derived processed outputs should stay local; processed outputs should be regenerated under `data/processed/tej/` when the cleaning pipeline is implemented.
* No news data has been collected yet, and no Hype Index result has been produced yet.

## 2026-05-29

### Data-source and universe design

* Added a Phase 1 data-source and universe plan for Taiwan Hype Index replication.
* Clarified that Phase 1 uses current Taiwan 50 constituents as a fixed large-cap universe for descriptive replication.
* Documented planned schemas for the universe table, news table, and market data table, plus alias matching, counting rules, frequency choice, and missing-data rules.
* This was a documentation-only design step. No data was downloaded, no Python code was implemented, and no empirical results were produced.

### Project pivot to Taiwan Hype Index

* Instructor suggested moving the project toward market sentiment / market attention.
* Current first-phase plan is specifically a Taiwan-market replication and adaptation of `The Hype Index: an NLP-driven Measure of Market News Attention` (arXiv:2506.06329).
* The proposed initial universe is Taiwan 50 constituents, with raw news-count Hype Index and market-cap-adjusted Hype Index as the first deliverables.
* Current scope is based on the Hype Index paper only; broader LLM, agentic, or portfolio papers are not part of the active first-phase direction.
* This is a documentation and design pivot only. No data pipeline, experiment, backtest, prediction test, LLM run, or portfolio result has been executed yet.
* Next steps are data-source selection, Taiwan 50 universe construction, company-name and ticker-alias matching design, and news-count pipeline design.

## 2026-05-22

### Documentation framing revision

* 將 reading log 與 architecture notes 的主軸調整為 news-aware LLM view generation for Black-Litterman portfolio optimization。
* 釐清 BL baseline 是工程驗證步驟，news/event-informed view generation 才是主要 modeling direction。
* 這次只屬於 documentation/design framing revision；沒有執行 code、backtest、LLM experiment 或 portfolio result。

### Human-facing documentation polish

* 將部分 Markdown 從 agent-instruction style 改成較適合課程報告閱讀的 project notes。
* 清理 fenced code/text blocks 中不會 render 的 LaTeX notation，改在一般 Markdown prose 使用 `$P$`、`$Q$`、`$\Omega$` 等符號。
* 這次仍然只屬於 documentation polish；沒有執行實作、backtest、LLM call 或投資組合實驗。

### Documentation cleanup

* 將 paper-reading notes 與 architecture synthesis 改成較清楚的 Taiwan Traditional Chinese wording，同時保留 English technical terms、formulas、schemas 與 prompt sketches。
* 參考 `references/local/` 底下的 local-only paper source folders，用來確認 metadata 與 architecture details。
* 這次只屬於 documentation cleanup；沒有執行 code、backtest、LLM experiment 或 portfolio result。

### Done

* Created the initial course/research documentation scaffold.
* Added placeholders for paper reading, architecture notes, and progress tracking.

### Stage recorded on 2026-05-22

* Repository 仍在 course/research scaffolding stage。
* Model architecture 尚未 finalized。
* 目前文件主軸已調整為 news-aware LLM views 進入 Black-Litterman；下一步是把設計收斂成可實作的 offline baseline 與 mocked/news-aware view examples。

### Next steps recorded on 2026-05-22

1. 整理 BL baseline 的 data split、return scale、$\pi$、$\Sigma$、$P$、$Q$、$\Omega$ 與 optimizer assumptions。
2. 建立 fixed / mocked views 的 deterministic example。
3. 設計 selected news + rationality 的 offline fixture。
4. 評估 Nexus-style macro/micro synthesis 是否放入實作，或先作為 report/design extension。
