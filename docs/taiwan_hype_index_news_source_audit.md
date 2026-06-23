# Taiwan Hype Index News Source Feasibility Audit

## Purpose

This audit evaluates which public news sources are realistically usable for the next implementation step of the Taiwan Hype Index project. The goal is source feasibility only: no production news data is collected here, no news-count pipeline is implemented, and no Hype Index result is computed.

The active empirical setting remains a TEJ-based fixed top-50 market-cap listed-stock universe selected as of 2025-03-31, with the market panel covering 2025-04-01 to 2026-03-31. The report title may remain **Taiwan 50 Hype Index**, but the first implementation should continue to describe the universe as a TEJ-based operational proxy rather than an official Taiwan 50 constituent list.

Access date for this audit revision: 2026-06-20.

Follow-up live feasibility sprint: 2026-06-21, documented in `docs/taiwan_hype_index_news_acquisition_feasibility.md`. That sprint checked raw GDELT file availability, ran tiny in-memory GKG metadata scans, and tested selected Taiwanese public metadata routes without saving production news data.

## Project Constraint

The first implementation should not require Google Cloud, BigQuery, paid APIs, billing setup, or cloud credentials. Sources that are technically feasible only through a paid account, cloud project, or credentialed cloud client are not selected for the current zero-cost route.

## Project News-Data Requirements

The next news-count implementation needs article-level metadata that can support stock-level and sector-level attention counts:

- Coverage period: 2025-04-01 to 2026-03-31.
- Taiwan top-50 company coverage.
- Search by Chinese and / or English company names, including official names and conservative short-name aliases.
- Headline or title when available.
- Publication timestamp, ideally with a timezone convention.
- URL or stable article identifier.
- Source name or domain.
- Duplicate handling feasibility through URL normalization, source domain, title similarity when available, and timestamp proximity.
- Terms-of-use and redistribution caveats, especially whether article text can be stored or redistributed.

For Phase 1, the project should store only the minimum metadata needed for reproducible counts unless a source's terms clearly allow broader retention. Raw article text is not required for the first Hype Index baseline and should not be downloaded or committed.

## Source Evaluation Table

| Source | Verification status | Official / source URL inspected | Historical search for 2025-04-01 to 2026-03-31 | Chinese company-name search | Fields that appear obtainable | Usage / redistribution risk | Recommendation |
|---|---|---|---|---|---|---|---|
| GDELT raw data files / direct download | Verified | `https://www.gdeltproject.org/data.html`; `https://blog.gdeltproject.org/gdelt-2-0-our-global-world-in-realtime/` | Feasible in principle. Official pages document GDELT 2.0 raw data files and master file lists, and GDELT 2.0 streams begin in 2015. | Feasible only after local parsing/filtering. Chinese aliases can be searched in downloaded metadata fields, but match precision must be tested. | GKG metadata such as document identifier / URL, source common name, timestamp, themes, organizations / names depending on table. A stable title field should not be assumed. | Fully free and no cloud required, but files can be large. Keep outputs local and metadata-only until redistribution constraints are reviewed. | Primary zero-cost candidate for a tiny retrospective prototype. |
| GDELT 2.0 BigQuery / GKG | Verified, rejected for this project | `https://www.gdeltproject.org/data.html`; `https://blog.gdeltproject.org/gdelt-2-0-our-global-world-in-realtime/` | Technically feasible; official GDELT pages document BigQuery-hosted tables. | Technically feasible through SQL predicates. | Similar GKG metadata to the raw route, easier to query. | Not selected because it requires Google Cloud / BigQuery access and may require billing / credentials. | Rejected / not selected under the zero-cost, no-cloud constraint. |
| GDELT DOC 2.0 API | Partially verified | `https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/` | Not suitable as the production historical source for 2025-04-01 to 2026-03-31. The official DOC API page describes `STARTDATETIME` / `ENDDATETIME` as available only within the last 3 months. | Useful for recent exact-phrase exploratory checks, including Chinese aliases, when rate limits allow. | ArticleList mode documents title, source country, language, publication date, URL, and JSON output. | API rate limits / availability risk; previous tiny probe reached HTTP 429. Do not rely on it for full historical coverage. | Recent exploratory checks only, not production historical source. |
| Central News Agency (CNA) RSS and website | Verified for current RSS / public pages | `https://www.cna.com.tw/about/rss.aspx`; `https://www.cna.com.tw/` | RSS is current-feed oriented; historical bulk access for 2025-2026 was not verified. | Public pages include Taiwan business / securities categories and Chinese titles; search API was not verified. | Headline, URL, category, timestamp on public pages / RSS. Raw text should not be stored without permission. | Copyright and licensing review required before systematic collection; likely metadata-only use is safer for course work. | Backup / manual-validation candidate, not assumed production source. |
| Economic Daily News / money.udn.com | Partially verified | `https://money.udn.com/money/index`; sample public search page `https://money.udn.com/search/result/1001/%E5%8F%B0%E7%A9%8D%E9%9B%BB` | Public search page exposes result counts and UI filters, but no stable public API or RSS method was verified. | Verified at the UI level for `台積電`; broader systematic search is not verified. | Headline, URL, timestamp, snippets, category. Raw article text and some content may be subscription-protected. | High copyright / paywall / scraping risk. | Backup / manual-validation candidate only unless terms and access method are approved. |
| MoneyDJ | Partially verified | `https://www.moneydj.com/KMDJ/News/newshome.aspx` | Current public pages are visible; historical search / bulk access was not verified. | Likely feasible on public pages, but no stable API / RSS method was verified in this audit. | Headline, URL, source label, timestamp, category, short excerpt on public pages. | Redistribution and scraping risk; systematic use needs terms review. | Backup / manual-validation candidate only. |
| Anue / Cnyes | Partially verified; later live-tested as backup | `https://www.cnyes.com/`; later probe endpoint documented in `docs/taiwan_hype_index_news_acquisition_feasibility.md` | The later 2026-06-21 sprint found a public Taiwan-stock category JSON route returning 2025 and 2026 metadata, but stable official developer documentation was not verified. | Feasible through returned metadata and local filtering, subject to terms review. | `newsId`, title, timestamp, source/category, and stock metadata appear obtainable; article content should be discarded. | Public endpoint / terms / robots risk remains unresolved; systematic scraping would need explicit review. | Backup / manual-validation candidate only unless terms and stable access method are approved. |
| Commercial Times / ctee.com.tw | Not verified | Attempted source-page verification, but accessible evidence was not obtained in this audit. | Not verified. | Not verified. | Not verified. | Unknown; do not assume usability. | Reject for now; revisit only with direct manual verification. |
| MOPS / public company announcements | Verified as event-context source | `https://mopsov.twse.com.tw/mops/web/t05st02` | Feasible for official disclosures. The page exposes real-time, daily, historical, and full-text material-information queries. | Company-specific official disclosure search is feasible by ticker / company context, not by market-news attention. | Official announcement title / subject, company, date, announcement text, URL / query result. | Official disclosures are not market news and should not be mixed into news-attention counts without changing the index definition. | Event-context only. |

## Candidate Notes

### GDELT Raw Data Files / Direct Download

The revised primary route is GDELT raw data files downloaded directly from the public GDELT file lists. This keeps the project free and avoids Google Cloud, BigQuery, billing, paid APIs, and cloud credentials. It also preserves retrospective feasibility because GDELT 2.0 begins in 2015, covering the 2025-04-01 to 2026-03-31 project window.

The trade-off is engineering burden. Raw GDELT files are frequent, compressed, and potentially large. The prototype must therefore use a very small date window, download selectively only if the user explicitly approves a live probe, and filter locally by conservative company aliases. The first dry run should not download files; it should only list candidate file URLs, expected local paths, and filtering rules.

This route should use metadata only. It should not store article bodies. It also should not assume a stable title field in GKG files; if headline-level review is needed later, a separate source-specific or recent DOC API validation step may be required.

### GDELT BigQuery / GKG

GDELT BigQuery remains technically feasible, but it is rejected for this project because the first implementation must not require Google Cloud, BigQuery, billing setup, or cloud credentials. Existing SQL templates under `queries/gdelt/` are retained only as archived reference material, not as the selected implementation path.

### GDELT DOC API

The DOC 2.0 API is useful for recent exploratory checks because the official documentation describes exact-phrase search, Boolean search, `sourcecountry`, `sourcelang`, ArticleList mode, JSON output, RSS output, `STARTDATETIME` / `ENDDATETIME`, and result sorting. It is not the production historical route for the current project window because the same official page describes `STARTDATETIME` / `ENDDATETIME` as restricted to the last 3 months. A previous tiny attempted local probe for `台積電` over 2025-04-01 to 2025-04-08 returned HTTP 429 rather than usable metadata. No records were saved.

The next implementation should treat DOC API as a recent-only convenience check. It should not be used to claim full 2025-2026 coverage unless official documentation or a successful verified query proves otherwise.

### Taiwanese Finance-News Websites

CNA, Economic Daily News, MoneyDJ, and Anue / Cnyes are valuable local-market sources because their headlines and categories are closer to Taiwan investor attention than broad global media. They are not yet recommended as the first production source because this audit did not verify a stable historical API or clearly permitted bulk collection path for the full 2025-2026 period.

These sources remain useful as manual validation sources for a small GDELT raw-file prototype, especially for high-attention companies such as TSMC. Any source-specific crawler should wait until terms-of-use review and a stable RSS / API / archive method are documented.

### Official Announcements / Exchange Disclosures

MOPS is verified and useful, but it is not a market-news attention source. It records official company announcements, not media attention. It should be used to annotate events, validate dates, or explain spikes after the Hype Index is built from news sources. Using MOPS announcements as the main count source would change the meaning of the project from news attention to disclosure activity.

## Small Feasibility Checks Run

This audit did not download or save news records. Public pages were opened for official documentation or source pages, including GDELT, CNA RSS, Economic Daily News search, MoneyDJ news, Cnyes, and MOPS. A previous one-line GDELT DOC API probe was attempted for `"台積電"` over 2025-04-01 to 2025-04-08 with `maxrecords=5`; the sandboxed run first failed due DNS restrictions, and the approved network run reached GDELT but returned HTTP 429. Because it did not return records, it is evidence of rate-limit / access risk rather than evidence of coverage.

No raw news data file was created, and no article text or fetched records were committed.

## Final Recommendation

The next implementation goal should be a **small GDELT raw-file direct-download feasibility probe**, not a BigQuery prototype and not a full news pipeline:

1. Use GDELT 2.0 raw GKG file lists as the zero-cost primary route.
2. Start with a dry run that enumerates candidate raw file URLs for a very small date window and a few Taiwan top-50 aliases.
3. If a live probe is later approved, download only a tiny number of compressed files into ignored local paths.
4. Filter locally for conservative company aliases and retain only metadata needed for feasibility review.
5. Compare a small sample against CNA / Economic Daily News / MoneyDJ / Cnyes public pages manually to estimate false positives, duplicates, and missing Taiwan-local coverage.
6. Do not store article text, do not compute production news counts, and do not compute the Hype Index until the source choice and alias rules pass this small feasibility test.

Recommended zero-cost route: **GDELT raw data files / direct download, with tiny local filtering only**.

Rejected for this project: **GDELT BigQuery / GKG**, because it requires Google Cloud / BigQuery access.

Recent exploratory only: **GDELT DOC API**.

Backup / manual validation: **CNA RSS / public pages, Economic Daily News, MoneyDJ, and Anue / Cnyes** after terms review.

Event-context source: **MOPS / public company announcements**.

The follow-up prototype plan is documented in `docs/taiwan_hype_index_gdelt_prototype_plan.md`. A later acquisition feasibility sprint is documented in `docs/taiwan_hype_index_news_acquisition_feasibility.md`; it selects GDELT raw GKG direct download as the primary zero-cost route for the next bounded implementation step.
