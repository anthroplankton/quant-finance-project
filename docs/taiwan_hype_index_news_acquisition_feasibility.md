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
| Duplicate and syndicated rows | Counts may overstate attention. | Deduplicate by normalized URL / document identifier first, then evaluate source-domain and time-window rules. |
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
- one compressed GKG zip file is downloaded and processed at a time;
- temporary raw zip files are deleted immediately unless `--keep-raw` is set;
- only metadata-only outputs are written under ignored `data/processed/news/` or `data/raw/news/` paths;
- article full text is not stored.

This reduces peak disk usage because the local machine does not need to retain the full raw GDELT year. It does not reduce total network transfer. A one-year scan would still need to read every selected compressed GKG file over the network, so the estimated full-window compressed transfer remains large even when final stored outputs are small.

Recommended escalation sequence:

1. Run a 1-day dry run and inspect candidate file counts and output paths.
2. Run a 1-day execute probe with a small `--max-files` and `--max-download-mb` cap.
3. If match quality and output size are acceptable, run a 1-week probe.
4. If the 1-week probe is manageable, run a 1-month probe.
5. Do not attempt full-year collection until the 1-day, 1-week, and 1-month summaries are reviewed.

The probe writes:

- `probe_summary.json`;
- `matched_metadata_sample.csv`;
- `stock_day_counts.csv`.

The summary records files attempted, processed, and failed; download attempts; retry count; matched rows; unique URLs; output file size; elapsed seconds; estimated full-window download size; and whether streamed full-year processing appears feasible under the configured disk limit. That feasibility flag is a disk-footprint signal only; it does not mean the full-year network transfer is small.

Accounting convention:

- `files_downloaded` is retained only as a compatibility alias for `files_processed`; it counts files only after download, zip opening, and row parsing all succeed.
- `compressed_bytes_downloaded` is retained only as a compatibility alias for `compressed_bytes_processed_successful`.
- `compressed_bytes_processed_successful` is used for the clean-input full-window size estimate.
- `compressed_bytes_transferred_total` records actual network transfer, including failed or retried attempts.
- `download_attempts` and `retry_count` make transient partial-file or corrupt-zip retries auditable.
- `failed_files` is a bounded error list for URLs that fail after all retries.
