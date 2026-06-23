# Taiwan Hype Index News Acquisition Feasibility Sprint

## Purpose

This sprint tests whether the Taiwan Hype Index project can obtain usable one-year news metadata for 2025-04-01 to 2026-03-31 without reaching the end of the project with no news data. It is source discovery and feasibility work only. It does not implement the production news-count pipeline, does not compute the Hype Index, and does not create a report notebook.

Search and probe date: 2026-06-21.

## Project Constraint

The first implementation must remain zero-cost and no-cloud:

- no Google Cloud or BigQuery;
- no paid APIs, billing setup, or cloud credentials;
- no proprietary news subscription;
- no paywall, login, captcha, robots.txt, or anti-scraping bypass;
- no article full-text storage unless a source clearly allows it.

Probe outputs and any later raw news files must stay under ignored local paths such as `data/raw/news/` or `data/processed/news/`. No raw news data, probe output, TEJ data, or processed data should be committed.

## Minimum Useful Metadata

The project needs metadata that can support company-level and sector-level attention counts:

- source name or domain;
- title or headline when available;
- publication date / time or stable ingestion timestamp;
- URL or stable document identifier;
- matched company alias;
- matched ticker;
- query or source method.

Full article text is not required for the first Hype Index baseline and should not be stored.

## Candidate Source Matrix

| Source | Verification status | Access / documentation checked | Historical 2025-04-01 to 2026-03-31 feasibility | Fields observed or documented | Company-name search feasibility | Main risk | Recommendation |
|---|---|---|---|---|---|---|---|
| GDELT 2.0 raw GKG files | Verified and live-tested | `https://www.gdeltproject.org/data.html`; raw files under `http://data.gdeltproject.org/gdeltv2/` | Feasible in principle. GDELT 2.0 starts in 2015 and raw 15-minute files exist for tested 2025 and 2026 timestamps. | Document identifier / URL, source common name, timestamp, GKG metadata fields. Stable title should not be assumed. | Feasible by local alias filtering after streaming / decompressing files. | Large volume, duplicate / syndicated rows, weak title support, noisy global coverage. | Primary zero-cost route. Use selective streaming, not full raw-file storage. |
| GDELT DOC API | Verified as recent-only, not live-usable for this historical window | `https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/` | Not suitable for production historical coverage because official documentation restricts `STARTDATETIME` / `ENDDATETIME` to the last 3 months. A previous tiny probe hit HTTP 429. | ArticleList JSON can include title, URL, source, language, source country, and publication date. | Query syntax supports exact phrases and Boolean terms. | Rolling-window limit and rate-limit risk. | Reject as historical production source; keep only for recent sanity checks. |
| GDELT BigQuery / GKG | Verified, rejected by project constraint | `https://www.gdeltproject.org/data.html` | Technically feasible, but not selected. | GKG metadata via SQL. | Feasible through SQL predicates. | Requires Google Cloud / BigQuery access and possibly billing / credentials. | Rejected for current zero-cost / no-cloud project. |
| Anue / Cnyes public category JSON | Live-tested, not yet policy-cleared | `https://www.cnyes.com/`; `https://api.cnyes.com/media/api/v1/newslist/category/tw_stock` | Tested date filters returned 2025-01-01, 2025-04-01, and 2026-01-05 metadata pages. | `newsId`, `publishAt`, `title`, `source`, `stock`, `categoryName`; response also includes `content`, which should be discarded. | Category feed can be filtered locally by stock metadata and aliases; a guessed search endpoint returned 404. | Public endpoint lacks official developer documentation; robots / terms review is unresolved and site paths disallow `/news/`. | Backup / manual-validation candidate only unless terms are approved. |
| CNA RSS / public pages | Source page verified; feed URLs not resolved in probe | `https://www.cna.com.tw/about/rss.aspx` | RSS appears current-feed oriented; tested guessed RSS URLs returned 404. Historical one-year metadata route not verified. | RSS / pages may expose title, URL, and publication date when reachable. | Company-name search route not verified. | No verified historical API; copyright / licensing review needed. | Backup / manual validation only. |
| Economic Daily News / money.udn.com | Partially verified; robots / terms risk | `https://money.udn.com/`; `https://money.udn.com/robots.txt` | Public search UI exists, but stable API route was not verified. | Search pages can show titles, URLs, snippets, timestamps. | UI-level company search appears possible. | Robots / terms restrict broad reuse; paywall and licensing risk. | Reject for automated collection without permission; manual validation only. |
| MoneyDJ | Partially verified | `https://www.moneydj.com/KMDJ/News/newshome.aspx` | Public news pages exist; stable historical API / RSS route not verified. | Headline, URL, category, timestamp may be visible on pages. | Likely possible on UI pages, but not verified as a stable route. | Terms and scraping risk; no verified bulk route. | Backup / manual validation only. |
| Common Crawl / CC-News | Documented only | `https://commoncrawl.org/get-started` | Public data are free and accessible by HTTP(S), but the scale is far beyond a small laptop workflow without an index. | WARC / WAT / WET records can include URLs and extracted text metadata, not a finance-news-specific title index. | Requires local or external indexing / filtering over large archives. | Very large storage and compute burden; no simple company-search endpoint. | Reject as the main course-project route. |
| MOPS / exchange disclosures | Verified as event-context source | `https://mopsov.twse.com.tw/mops/web/t05st02` | Historical official announcements are feasible. | Company, date, announcement subject / text, official disclosure identifiers. | Ticker / company search feasible. | This is disclosure activity, not media news attention. | Event-context fallback only, not a Hype Index news source. |

## Live Probe Results

### GDELT Raw GKG Availability And Size

The sprint first checked candidate raw GKG files with HTTP `HEAD` requests, without saving files:

| Timestamp file | Status | Compressed size |
|---|---:|---:|
| `20250401000000.gkg.csv.zip` | 200 | 6,681,075 bytes |
| `20250401001500.gkg.csv.zip` | 200 | 6,061,922 bytes |
| `20260105000000.gkg.csv.zip` | 200 | 2,515,651 bytes |
| `20260105001500.gkg.csv.zip` | 200 | 2,709,414 bytes |

The verified endpoint used plain HTTP. In this environment, the HTTPS version of the raw-file host produced a certificate-name mismatch, while `http://data.gdeltproject.org/gdeltv2/...` returned the expected files.

GDELT GKG v2 files are issued every 15 minutes, so the expected counts are:

| Window | File count | Approximate compressed storage using the four-file sample average |
|---|---:|---:|
| One day | 96 | about 411 MB |
| One week | 672 | about 2.8 GB |
| 2025-04-01 to 2026-03-31 | 35,040 | about 147 GB |

These estimates are compressed sizes only. Decompressed working size would be larger. A naive full-year local download is therefore not the right first step, but a selective streaming scan remains realistic.

### GDELT Raw GKG Alias Scan

Two small in-memory scans were run. The probe downloaded a few compressed GKG files into memory, parsed metadata rows, counted alias hits, and saved no records.

Aliases tested:

- `台積電`, `TSMC`, `Taiwan Semiconductor`, `Taiwan Semiconductor Manufacturing`, `2330`;
- `鴻海`, `Hon Hai`, `Hon Hai Precision`, `Foxconn`, `2317`;
- `聯發科`, `MediaTek`, `MediaTek Inc`, `2454`.

Probe windows:

- first two hours of 2025-04-01;
- first two hours of 2026-01-05.

Results:

| Window | Files scanned | Compressed bytes read in memory | Rows parsed | Alias-hit summary |
|---|---:|---:|---:|---|
| 2025-04-01 00:00-01:45 | 8 | 47,618,732 | 11,467 | TSMC / 2330: 1; Hon Hai / 2317: 1; MediaTek / 2454: 0 |
| 2026-01-05 00:00-01:45 | 8 | 23,851,142 | 5,865 | TSMC / 2330: 4; Hon Hai / 2317: 1; MediaTek / 2454: 1 |

The hits prove that the raw GKG route can produce retrospective company-related metadata for the project window. The results also show expected weaknesses: hit volume can be sparse for a short window, source domains can be global rather than Taiwan-local, and GKG is better suited for URL / source / timestamp counts than headline review.

### Anue / Cnyes Public JSON

A small public endpoint probe checked the Taiwan stock news category:

`https://api.cnyes.com/media/api/v1/newslist/category/tw_stock`

Small date-filtered requests returned metadata for 2025 and 2026 dates. The response contained paginated `data` items and fields such as `newsId`, `publishAt`, `title`, `source`, `stock`, and `categoryName`. The endpoint also returned `content`; this field should be explicitly discarded and not stored.

Observed one-day availability checks:

| Requested day | Result |
|---|---|
| 2025-01-01 | HTTP 200; metadata page returned; total count reported by endpoint |
| 2025-04-01 | HTTP 200; metadata page returned; total count reported by endpoint |
| 2026-01-05 | HTTP 200; metadata page returned; total count reported by endpoint |

This is technically promising because it has local Taiwan finance news metadata with titles and timestamps. However, it is not yet selected as the production route because the endpoint does not appear to have stable official developer documentation, a guessed search endpoint returned 404, and robots / terms review is unresolved. It should be treated as a backup or manual-validation route until terms are clarified.

### CNA RSS Probe

The CNA RSS information page was verified, but guessed feed URLs such as `https://www.cna.com.tw/rss/aafe.xml` and `https://www.cna.com.tw/rss/aall.xml` returned 404 during the sprint. No stable historical RSS route was verified.

### UDN / MoneyDJ / Common Crawl / MOPS

UDN and MoneyDJ remain useful for manual validation but were not selected for automated collection because no stable, permitted, historical metadata route was verified. UDN's robots / terms surface also increases risk for systematic scraping.

Common Crawl is free and no-cloud in the narrow sense that files are downloadable by HTTP(S), but it is too large and not finance-news-specific. It would require a separate indexing workflow before company-name search is practical.

MOPS is a reliable official disclosure source but should remain event-context material. It measures company disclosure activity, not market-news attention.

## Selected Route

The selected primary route is:

**GDELT 2.0 raw GKG direct-download metadata, processed through a selective local streaming filter.**

This route is the only candidate verified as all of the following:

- free;
- no Google Cloud, BigQuery, billing setup, or cloud credentials;
- retrospective enough for 2025-04-01 to 2026-03-31;
- accessible through public raw files;
- capable of yielding URL / document identifier, source, timestamp, and company-alias hits.

It is not yet a production news-count pipeline. The next step should still be a bounded local acquisition prototype.

## First Implementation Pilot Window

The first implementation should not immediately scan the full 2025-04-01 to 2026-03-31 market panel. The chosen news and Hype Index pilot window is an 8-week calendar window:

- news calendar window: 2025-04-05 to 2025-05-30 inclusive;
- weekly bins: Saturday-to-Friday, ending on Fridays;
- length: exactly 56 calendar days, or 8 full 7-day weeks;
- first week: 2025-04-05 to 2025-04-11;
- last week: 2025-05-24 to 2025-05-30;
- expected fixed-universe stock-week panel size: 50 × 8 = 400 rows.

The pilot window starts at the first complete Saturday-to-Friday weekly bin after the 2025-04-01 TEJ market-panel start. It does not exclude the 2025-04-03 to 2025-04-06 holiday/weekend period entirely; news is collected on calendar days, including weekends and holidays. It avoids partial weeks, includes important April 2025 Taiwan market/news events, and keeps raw GDELT transfer volume manageable for the first implementation. It gives 8 weekly observations, which are enough for bounded descriptive Hype Index construction but not enough for strong time-series inference.

Market-cap weights should continue to come from the TEJ-derived weekly market-cap weights built from the full TEJ market panel. For each Saturday-to-Friday news week, the market-cap weight convention is the last available TEJ trading day within that week. Do not assume each Friday is a trading day; if the Friday is a market holiday or otherwise absent from TEJ trading data, use the last available trading day in the same week.

The 8-week GDELT pilot uses the two completed 4-week chunks:

| Chunk | Calendar window | Days | Expected GDELT files |
|---|---|---:|---:|
| 1 | 2025-04-05 to 2025-05-02 | 28 | 2,688 |
| 2 | 2025-05-03 to 2025-05-30 | 28 | 2,688 |

Each chunk fits the bounded month-scale `--max-files` cap. The full-year run remains inappropriate for the first implementation because it would require about 35,040 raw GKG files and a large total network transfer before alias precision, duplicate handling, and weekly aggregation are fully reviewed.

The previously planned 2025-05-31 to 2025-06-27 chunk is not selected for the first implementation. It encountered a severe GDELT raw GKG archive availability problem: early scattered missing files included `20250424213000`, `20250429110000`, `20250503003000`, and `20250506134500`; a short missing segment appeared around `20250612181500` to `20250612201500`; and the major block after `20250614180000` through `20250627234500` was almost continuously missing. This is documented as a data-source limitation. It is the reason the first implementation window is revised to 8 weeks rather than 12 weeks.

Completed local probe summaries for the selected two chunks are:

| Window | Completed | Candidate files | Files processed | Files missing | Files failed | Matched rows | Unique URLs |
|---|---|---:|---:|---:|---:|---:|---:|
| 2025-04-05 to 2025-05-02 | true | 2,688 | 2,686 | 2 | 0 | 4,141 | 3,572 |
| 2025-05-03 to 2025-05-30 | true | 2,688 | 2,686 | 2 | 0 | 2,966 | 2,401 |
| Combined selected manual-v5 pilot | true | 5,376 | 5,372 | 4 | 0 | 7,107 | 5,973 |

The combined missing-file ratio is about 0.074%. The local summaries did not show a full-day or full-week zero-news failure. The unique URL count in the combined row is the sum of chunk-summary unique URLs. The retained pilot artifact for aggregation is `stock_day_counts.csv`, which stores daily aggregate counts rather than URL-level matched rows, so it cannot support full ticker-week cross-day URL deduplication after the fact. These outputs remain local-only under ignored `data/processed/news/` paths and should not be committed.

The selected manual-v5 outputs have now passed the local Goal 3A / Goal 3B /
Goal 3C pipeline. Goal 3A wrote a zero-filled 50 × 8 stock-week news-count
panel with 400 rows and validation passed. Goal 3B joined the panel to TEJ
weekly market-cap weights with 400 Hype-ready rows and validation passed. Goal
3C computed raw and market-cap-adjusted Hype Index outputs with 400 rows, 8
weeks, 50 stocks, validation passed, and zero missing Hype weeks. The weekly
total `news_count_unique_urls` values are 1,225, 1,343, 737, 836, 646, 808,
884, and 628.

Goal 4A / 4B report artifacts now consume those completed local outputs under
`report/results/pilot_8w_manual_v5/` and `report/figures/pilot_8w_manual_v5/`.
Goal 4B adds one-year TEJ market-background tables, sector-level Hype
aggregation, revised heatmap and scatter figures, return / volatility
diagnostics, and key-stock case-study figures for notebook preparation. This is
a reporting and visualization layer only: it does not run live GDELT downloads,
does not recompute Goal 3A / 3B / 3C, and does not change GDELT matching or
Hype methodology.

`scripts/build_gdelt_weekly_counts.py` reads the selected chunks'
`probe_summary.json` and `stock_day_counts.csv`, validates that the chunks
completed without failed files or threshold failures, rejects capped probe
summaries, validates that processed plus missing plus failed file counts account
for the uncapped GDELT candidate file grid, reconciles `stock_day_counts.csv`
`matched_rows` totals against the paired probe summary, validates that the
selected chunk date ranges continuously cover the full 2025-04-05 to
2025-05-30 pilot without gaps or overlaps, rejects overlapping stock-day rows,
validates tickers against the TEJ-based top-50 universe, and writes a
zero-filled 50 × 8 stock-week news-count panel under ignored
`data/processed/news/` paths. Capped, stale, or truncated probe outputs are
useful diagnostics only and must not be used as aggregation inputs.

The original Hype Index paper counts news articles in the measurement period. This bounded 8-week pilot uses a Taiwan-market weekly adaptation in which `news_count_unique_urls` is the main count and is defined as the sum of stock-day unique GDELT document counts within each stock-week. `matched_rows` remains diagnostic only. This is not a fully deduplicated article-level weekly count: if the same `document_identifier` appears for the same ticker on multiple days in the same Saturday-to-Friday bin, the weekly count can overstate exact article-level attention. Full ticker-week URL deduplication would require retaining URL-level matched rows, not only `stock_day_counts.csv`, and is documented as a future improvement.

The selected alias file for the next full selected 8-week rerun is the local
manual v5 file:

```text
data/processed/news/aliases/top50_alias_allowlist_gdelt_manual_reviewed_v5_recommended.csv
```

The v2 / v3 / v4 diagnostic comparison used the same 2025-05-10 to 2025-05-16
window with audit-enabled GDELT probe outputs. Manual v2 fixed the severe TSMC
undercount but introduced broad false positives, including `2382` matches for
Quanta Services / unrelated Quanta contexts and broad `2892` First Financial
matches. Manual v3 reduced those risks: `2382` fell from 46 to 24 and `2892`
fell from 29 to 0, but Quanta Computer matching remained broader than ideal.
Manual v4 kept TSMC fixed at 232, MediaTek at 176, and Hon Hai / Foxconn at
132; Latin token-boundary matching removed the ASUS false positives; `2382`
fell to 13 with sampled evidence showing `Quanta Computer Inc` in GKG
Organizations; and `2892` remained 0.

Manual v5 is the selected conservative precision-oriented alias set. It is
based on v4 and disables only three additional bare aliases with clear
false-positive evidence: `Largan` for `3008`, `Yuanta` for `2885`, and
`Novatek` for `3034`. The precise variants remain enabled, including `Largan
Precision`, `Yuanta Financial`, `Yuanta Financial Holding`, `Novatek
Microelectronics`, and the corresponding Chinese names. Manual v5 also keeps
the v4 decisions for TSMC, MediaTek, Hon Hai / Foxconn, ASUS with Latin
token-boundary matching, and `Quanta Computer Inc` / `Quanta Computer Inc.`.

Review dry runs by omitting `--execute`. When ready for a bounded live run, use separate ignored output directories so chunk outputs do not overwrite one another:

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

All GDELT outputs from these commands remain local-only under ignored `data/processed/news/` paths. They should not be committed.

For local manual diagnostics or a later selected-chunk rerun, the probe can use
bounded file-level parallelism with `--workers`. The default `--workers 1`
preserves the original sequential behavior. Recommended local starting values
are `--workers 8`, `--workers 12`, or `--workers 16`; start with 12 or lower
unless local network, CPU, and disk pressure have already been checked. The
default `--worker-backend thread` path keeps the existing downloader/parser
behavior. The optional `--worker-backend process` path is for CPU-bound parsing
and alias-matching diagnostics: the parent process downloads each bounded raw
zip and tracks transfer / disk accounting, then a process worker parses exactly
one local temporary zip and returns metadata-only matches and timing metrics.
Process-pool startup or submission failures are controlled probe errors that
suggest `--worker-backend thread` as a fallback; the code does not silently
switch backends because benchmark interpretation depends on the configured
backend.
Parallel mode is an acquisition-speed setting only: it does not change the
alias policy, GKG matching scope, stock-day counting definition, weekly
aggregation method, or Hype Index methodology. Long-running live GDELT downloads
should be launched manually in a terminal rather than inside Codex.

The current matcher also uses a token-to-candidate alias index as a narrow
acquisition-speed optimization. Latin aliases are indexed by a deterministic
anchor token and still confirmed by the token-boundary regex, so `ASUS` still
does not match strings such as `Caucasus`, `Pegasus`, `Argus`, or `nexus`.
Phrase aliases such as `Taiwan Semiconductor Manufacturing` still require the
full phrase regex confirmation. CJK aliases may be selected by first CJK
character but are still confirmed with substring matching. This reduces alias
scanning inside each GKG content / entity / name field without changing matching
scope, alias policy, stock-day count semantics, or Hype methodology.

Bounded 2025-05-14 manual v5 process-backend benchmarks show the impact:

| Files | Workers | Backend | Elapsed seconds | Download seconds | Parse seconds | Alias-match seconds | Matched rows | Unique URLs |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 12 | 8 | process | 13.963 | 12.031 | 29.040 | 13.651 | 14 | 4 |
| 24 | 8 | process | 20.231 | 18.173 | 60.370 | 28.691 | 21 | 11 |
| 96 | 8 | process | 119.105 | 103.206 | 594.855 | 283.456 | 153 | 117 |

The comparable pre-index 96-file process benchmark completed in 164.295 seconds
with the same matched-row and unique-URL totals; alias-match time fell from
623.668 seconds to 283.456 seconds. The remaining bottleneck is still GKG
decompression / CSV scanning plus confirmed alias matching, not final merging.

The probe also supports audit and performance options before any full selected
8-week rerun. `matched_metadata_sample.csv` now records the exact
`matched_alias`, source `matched_alias_type` from the alias table when present,
the allowed GKG `matched_field_name`, and a bounded `matched_text_excerpt`
around the alias. The excerpt is taken only from content / entity / name fields
used for matching; URL, source, `DocumentIdentifier`, dates, and record IDs
remain excluded from matching evidence. These audit fields are for alias review
only and do not change `matched_rows`, `unique_urls`, or stock-day counts.

`--matched-sample-size` preserves the previous global sample behavior by
default. `--sample-per-ticker` can instead keep up to a fixed number of
deterministic sample rows per ticker so lower-volume tickers are visible in
manual review.

`--profile-performance` writes per-file timing fields to `probe_summary.json`
and `per_file_metrics.csv`, including elapsed, download, parse, and match time
summaries. The current parser streams through `zipfile`, so decompression is not
fully separable from parse time and is reported as a separate zero field where
it cannot be isolated.

`--shard-output-dir` enables a per-file shard workflow. Each candidate GKG file
writes one small JSON shard with status, counts, timing metrics, and bounded
matched metadata sample rows. Shards are written atomically through a temporary
file and then renamed. Each shard records a run fingerprint that includes the
alias-content digest, alias path for audit, matching-semantics version,
output/audit schema versions, sample options, and explicit candidate identity
fields: candidate index, URL, file name, and timestamp. `--resume` skips only
completed shards and recorded missing-archive shards whose fingerprint and
candidate identity match the current run; failed, malformed, copied, or stale
shards are recomputed.
`--merge-only` downloads nothing and rebuilds
`probe_summary.json`, `matched_metadata_sample.csv`, `stock_day_counts.csv`,
and optional `per_file_metrics.csv` from existing shards, but it fails with a
controlled error if any required shard has a mismatched fingerprint, mismatched
candidate identity, is malformed, or records a failed attempt. This is an
auditability and acquisition-speed workflow, not a methodology change.

The one-week manual v5 process-backend diagnostic for 2025-05-10 to 2025-05-16
completed successfully with 672 of 672 candidate files processed, no missing or
failed files, 808 matched rows, 624 global unique URLs, and about 615.3 seconds
elapsed with `--workers 8`. This supports keeping manual v5 and the current
process-backend plus indexed-matcher workflow for the next selected 8-week
rerun.

## Fallback Route

The least-bad fallback is:

**Anue / Cnyes public Taiwan stock news metadata as a backup / manual-validation source, pending terms review.**

It appears to provide local Taiwan finance metadata, including title and publication timestamp, for historical dates. It should not be automated at scale until terms-of-use, robots implications, and stable access assumptions are reviewed. If terms are not acceptable, it should be used only for manual validation of a few GDELT hits.

MOPS remains the event-context fallback for explaining spikes or validating official announcement dates, not the main attention-count source.

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| GDELT raw volume is large | Full-year naive download can exceed reasonable laptop storage. | Stream file-by-file, filter immediately, and save only minimal metadata under ignored paths. |
| Missing title in GKG | Title-level false-positive review may be harder. | Use URL / source / timestamp for counts first; use local news pages only for manual validation when allowed. |
| Duplicate and syndicated rows | Counts may overstate attention. | Current pilot reports this as a limitation; a future exact article-count implementation should retain URL-level matched rows and deduplicate by ticker-week using normalized URL / document identifier. |
| Alias false positives | Company names such as short names or brands may match unrelated articles. | Start with conservative aliases and synthetic alias tests; manually review tiny samples before scaling. |
| Missing Taiwan-local coverage | GDELT may under-cover local finance sites. | Compare small samples against Cnyes / CNA / UDN / MoneyDJ manually. |
| Terms uncertainty for local websites | Automated collection may be inappropriate. | Avoid full-text scraping and postpone automation until terms review is documented. |

## Next Implementation Recommendation

Implement a bounded GDELT raw-file acquisition prototype, not the full news-count pipeline:

1. Use the streaming probe helper to enumerate raw GKG URLs for one day and 3 companies.
2. Use explicit `--execute` opt-in only after the dry run is reviewed.
3. Decompress each file, filter rows locally by conservative aliases, and write metadata-only outputs under `data/processed/news/gdelt_probe/`.
4. Store only document identifier / URL, source, timestamp, matched alias, matched ticker, query window, and query method.
5. Save no article text.
6. Run manual precision checks before scaling beyond one day.

The first full-year production collection should wait until the one-day prototype confirms match precision, duplicate behavior, local storage requirements, and source-domain coverage.

## Bounded Streaming Probe

The next implementation step is a streaming probe, implemented in `scripts/probe_gdelt_raw_stream.py`. It is designed for limited local disk space:

- dry-run is the default;
- live requests require explicit `--execute`;
- compressed GKG zip files are processed through a bounded worker pool, with
  `--workers 1` preserving the original one-file-at-a-time behavior;
- temporary raw zip files are deleted immediately unless `--keep-raw` is set;
- only metadata-only outputs are written under ignored `data/processed/news/` or `data/raw/news/` paths;
- article full text is not stored.

This reduces peak disk usage because the local machine does not need to retain the full raw GDELT year. Bounded parallelism can reduce elapsed wall-clock time for local diagnostics, but it does not reduce total network transfer. A one-year scan would still need to read every selected compressed GKG file over the network, so the estimated full-window compressed transfer remains large even when final stored outputs are small.

Recommended escalation sequence:

1. Run a 1-day dry run and inspect candidate file counts and output paths.
2. Run a 1-day execute probe with a small `--max-files` and `--max-download-mb` cap.
3. If match quality and output size are acceptable, run a 1-week probe.
4. If the 1-week probe is manageable, run a 1-month probe.
5. Do not attempt full-year collection until the 1-day, 1-week, and 1-month summaries are reviewed.

The CLI hard cap allows up to 3,500 candidate GKG files, enough for a 30-day month-scale probe at 96 files per day. A full-window run of roughly 35,040 files is intentionally rejected by this cap. Live execution still requires explicit `--execute`, remains bounded by `--max-download-mb` for network transfer and `--disk-limit-gb` for local probe storage, and deletes raw zip files unless `--keep-raw` is selected. If the local storage budget would be exceeded during a raw download, the probe stops with `completed=false` and records `disk_limit_gb_exceeded` in the summary.

`--workers` must be a positive integer and is capped at 32. The cap is
intentional so a local run cannot accidentally create an unbounded number of
parallel downloads. The summary records the configured worker count, and the
main process merges worker results deterministically before writing
`matched_metadata_sample.csv`, `stock_day_counts.csv`, and `probe_summary.json`.

Occasional missing GDELT raw archive files are treated as a data-source limitation rather than a transient download failure. If a candidate raw GKG URL returns HTTP 404, the probe records it under `missing_files`, increments `files_missing`, skips retries for that URL, and continues to the next candidate file. Missing files are not counted as successfully processed files and do not contribute to `compressed_bytes_processed_successful`. The default `--max-missing-files 10` threshold allows a small number of archive gaps in a chunk; if the threshold is exceeded, the probe stops with `completed=false` and records `missing_file_threshold_exceeded`. Missing-file counts and ratios should be reported with any pilot-window results.

The probe writes:

- `probe_summary.json`;
- `matched_metadata_sample.csv`;
- `stock_day_counts.csv`.

When `--profile-performance` is enabled, it also writes
`per_file_metrics.csv`. When `--shard-output-dir` is enabled, it writes one
per-candidate JSON shard under that ignored directory.

The summary records files attempted, processed, and failed; download attempts; retry count; matched rows; unique URLs; output file size; elapsed seconds; estimated full-window download size; and whether streamed full-year processing appears feasible under the configured disk limit. That feasibility flag is a disk-footprint signal only; it does not mean the full-year network transfer is small.

Accounting convention:

- `files_downloaded` is retained only as a compatibility alias for `files_processed`; it counts files only after download, zip opening, and row parsing all succeed.
- `compressed_bytes_downloaded` is retained only as a compatibility alias for `compressed_bytes_processed_successful`.
- `compressed_bytes_processed_successful` is used for the clean-input full-window size estimate.
- `compressed_bytes_transferred_total` records actual network transfer, including failed partial downloads and retried attempts.
- `download_attempts` and `retry_count` make transient partial-file or corrupt-zip retries auditable.
- `failed_files` is a bounded error list for URLs that fail after all retries.
- `files_missing`, `missing_files`, and `missing_file_ratio` record HTTP 404 raw-file gaps separately from transient failures.

## Top-50 Alias Table Workflow

Before scaling from the three-company GDELT probe to the full TEJ-based top-50 universe, the project should build and review a local alias table. Alias quality is a data-control step: broad Chinese short names, group names, and generic English short names can create false positives in raw GKG matching.

The local alias generator is `scripts/build_top50_alias_table.py`. It reads TEJ-derived processed outputs:

- `data/processed/tej/company_metadata.csv`;
- `data/processed/tej/top50_universe_20250331.csv`.

Those inputs and generated alias outputs are local-only and ignored by Git. If the TEJ processed inputs are missing, regenerate them first:

```bash
uv run python scripts/build_tej_market_data.py
```

Then build the alias candidates:

```bash
uv run python scripts/build_top50_alias_table.py
```

For the current GDELT route, also generate the expanded-reviewed allowlist:

```bash
uv run python scripts/build_top50_alias_table.py --profile expanded_reviewed
```

The alias script writes:

- `data/processed/news/aliases/top50_alias_candidates.csv`;
- `data/processed/news/aliases/top50_alias_review.csv`;
- `data/processed/news/aliases/alias_summary.json`;
- `data/processed/news/aliases/top50_alias_allowlist_gdelt_expanded_reviewed.csv` when `--profile expanded_reviewed` is selected.

The generated schema includes ticker, stock ID, alias text, alias type, language, source column, ambiguity flag, matching flag, review reason, profile, and notes. The GDELT expanded-reviewed policy disables pure ticker aliases by default because numeric aliases such as `2330` and `2454` can match unrelated numbers in raw GKG rows. Official Chinese and English full names are generally enabled for matching.

The GDELT high-risk short-name policy keeps `統一`, `長榮`, `台塑`, `南亞`, `國泰`, `富邦`, `第一`, `合庫`, and `台新` disabled unless explicitly overridden in a later reviewed table. The expanded-reviewed policy enables official full names plus short or brand aliases only when they are explicitly curated. The current curated Chinese list includes core standard short names such as `台積電`, `聯發科`, `鴻海`, `聯電`, `中華電`, `台達電`, `日月光投控`, `國巨`, `華碩`, `廣達`, `瑞昱`, `智邦`, `緯創`, `緯穎`, `萬海`, `遠傳`, `和碩`, `聯詠`, `陽明`, and `彰銀`, plus precise non-generic financial or airline aliases such as `玉山金`, `兆豐金`, `中信金`, `元大金`, `開發金`, `第一金`, `合庫金`, and `長榮航`. The current curated English / brand list includes `TSMC`, `MediaTek`, `Hon Hai`, `Foxconn`, and `Yageo`. Unlisted short aliases, including broad English words or acronyms such as `DELTA`, `FIRST`, and `CSC`, remain disabled and are marked for review. The script also normalizes TEJ display marks, for example using `國巨` for a source value such as `國巨*`, while preserving the source column and notes for review.

The GDELT streaming probe can read the expanded-reviewed CSV and will use only rows where `use_for_matching` is true.
