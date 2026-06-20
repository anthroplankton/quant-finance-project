# Taiwan Hype Index News Source Feasibility Audit

## Purpose

This audit evaluates which public news sources are realistically usable for the next implementation step of the Taiwan Hype Index project. The goal is source feasibility only: no production news data is collected here, no news-count pipeline is implemented, and no Hype Index result is computed.

The active empirical setting remains a TEJ-based fixed top-50 market-cap listed-stock universe selected as of 2025-03-31, with the market panel covering 2025-04-01 to 2026-03-31. The report title may remain **Taiwan 50 Hype Index**, but the first implementation should continue to describe the universe as a TEJ-based operational proxy rather than an official Taiwan 50 constituent list.

Access date for this audit: 2026-06-20.

## Project News-Data Requirements

The next news-count implementation needs article-level metadata that can support stock-level and sector-level attention counts:

- Coverage period: 2025-04-01 to 2026-03-31.
- Taiwan top-50 company coverage.
- Search by Chinese and / or English company names, including official names and conservative short-name aliases.
- Headline or title.
- Publication timestamp, ideally with a timezone convention.
- URL or stable article identifier.
- Source name or domain.
- Duplicate handling feasibility through URL normalization, source domain, title similarity, and timestamp proximity.
- Terms-of-use and redistribution caveats, especially whether article text can be stored or redistributed.

For Phase 1, the project should store only the minimum metadata needed for reproducible counts unless a source's terms clearly allow broader retention. Raw article text is not required for the first Hype Index baseline and should not be downloaded or committed.

## Source Evaluation Table

| Source | Verification status | Official / source URL inspected | Historical search for 2025-04-01 to 2026-03-31 | Chinese company-name search | Fields that appear obtainable | Usage / redistribution risk | Recommendation |
|---|---|---|---|---|---|---|---|
| GDELT 2.0 BigQuery / GKG | Verified | `https://www.gdeltproject.org/data.html`; `https://blog.gdeltproject.org/gdelt-2-0-our-global-world-in-realtime/` | Feasible in principle. Official GDELT pages state that GDELT 2.0 Event, Mentions, and GKG tables are available in BigQuery and updated every 15 minutes; GDELT 2.0 data streams begin in 2015. | Partially feasible. GDELT monitors and translates non-English material, but Chinese company-name precision must be tested. | URL / document identifier, source, date-time, language / source metadata, organizations / names / themes depending on table. Not raw article text. | GDELT permits broad dataset use and redistribution with citation, but source article copyrights still matter; do not republish article text. | Primary candidate for retrospective baseline. |
| GDELT DOC 2.0 API | Partially verified | `https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/` | Unclear for the full period. The DOC API documentation says it supports `STARTDATETIME` / `ENDDATETIME`, JSON, RSS, and ArticleList output, but the same page also describes rolling-window constraints. A tiny local API probe for 2025-04-01 to 2025-04-08 returned HTTP 429, so live feasibility was not proven. | Feasible in query syntax; exact phrases and Boolean query syntax are documented. Chinese-language source behavior still needs a small successful test. | ArticleList mode documents title, source country, language, publication date, URL, and JSON output; raw text is not expected. | API rate limits / availability risk; redistribution should follow GDELT citation and avoid article-text storage. | Backup / exploratory tool, not the main retrospective source unless a small historical query succeeds. |
| Central News Agency (CNA) RSS and website | Verified for current RSS / public pages | `https://www.cna.com.tw/about/rss.aspx`; `https://www.cna.com.tw/` | RSS is current-feed oriented; historical bulk access for 2025-2026 was not verified. | Public pages include Taiwan business / securities categories and Chinese titles; search API was not verified. | Headline, URL, category, timestamp on public pages / RSS. Raw text should not be stored without permission. | Copyright and licensing review required before systematic collection; likely metadata-only use is safer for course work. | Backup candidate for current / forward collection or manual validation, not primary retrospective source. |
| Economic Daily News / money.udn.com | Partially verified | `https://money.udn.com/money/index`; sample public search page `https://money.udn.com/search/result/1001/%E5%8F%B0%E7%A9%8D%E9%9B%BB` | Public search page exposes result counts and UI filters including one-year and specified-period options, but no stable public API or RSS method was verified. | Verified at the UI level: a search for `台積電` returned public results and a related stock label `台積電 2330`. | Headline, URL, timestamp, snippets, category. Raw article text and some content may be subscription-protected. | High copyright / paywall / scraping risk. UDN pages link to news licensing and terms. | Backup / validation candidate only unless terms and access method are approved. |
| MoneyDJ | Partially verified | `https://www.moneydj.com/KMDJ/News/newshome.aspx` | Current public pages are visible; historical search / bulk access was not verified. | Likely feasible on public pages, but no stable API / RSS method was verified in this audit. | Headline, URL, source label, timestamp, category, short excerpt on public pages. | Redistribution and scraping risk; systematic use needs terms review. | Backup / validation candidate only. |
| Anue / Cnyes | Partially verified | `https://www.cnyes.com/` | Public site and finance-news orientation are verified; historical public API / RSS was not verified. | Likely feasible on public pages, but not verified as a stable method. | Headline, URL, source domain, timestamp on news pages if accessed. | Page footer states unauthorized reproduction is not allowed; systematic scraping would need explicit terms review. | Backup / validation candidate only. |
| Commercial Times / ctee.com.tw | Not verified | Attempted source-page verification, but accessible evidence was not obtained in this audit. | Not verified. | Not verified. | Not verified. | Unknown; do not assume usability. | Reject for now; revisit only with direct manual verification. |
| MOPS / public company announcements | Verified as event-context source | `https://mopsov.twse.com.tw/mops/web/t05st02` | Feasible for official disclosures. The page exposes real-time, daily, historical, and full-text material-information queries. | Company-specific official disclosure search is feasible by ticker / company context, not by market-news attention. | Official announcement title / subject, company, date, announcement text, URL / query result. | Official disclosures are not market news and should not be mixed into news-attention counts without changing the index definition. | Event-context only. |

## Candidate Notes

### GDELT 2.0 BigQuery / GKG

GDELT is the strongest primary candidate for the first retrospective baseline. Official GDELT documentation states that its datasets are available in Google BigQuery, with live datasets updated every 15 minutes, and that GDELT 2.0 includes Events, Mentions, and Global Knowledge Graph tables. The GDELT 2.0 announcement also states that the Event, Mentions, and GKG tables are available in BigQuery and that GDELT 2.0 data streams begin in 2015, which covers the required 2025-04-01 to 2026-03-31 period.

The main benefit is reproducibility: a BigQuery or raw-GKG workflow can be documented with query text, date windows, source-domain filters, and article-document identifiers. The main risk is matching quality. GDELT is broad global media infrastructure, not a curated Taiwan finance-news feed. It may include duplicates, syndicated reposts, weak company-name matches, and uneven Taiwan local-source coverage. The implementation should therefore start with a small subset of companies and manually inspect match precision before scaling.

For Phase 1, GDELT should be used for article metadata and counts, not for storing full copyrighted article text. Candidate fields are URL / document identifier, source common name or domain, date-time, language, title when using DOC API output, and organization / name features when using GKG.

### GDELT DOC API

The DOC 2.0 API is useful for quick exploration because the official documentation describes exact-phrase search, Boolean search, `sourcecountry`, `sourcelang`, ArticleList mode, JSON output, RSS output, `STARTDATETIME` / `ENDDATETIME`, and result sorting. It is less certain as the production source for the full project window. The documentation contains both historical-search language and rolling-window constraints, and a tiny attempted local probe for `台積電` over 2025-04-01 to 2025-04-08 returned HTTP 429 rather than usable metadata. No records were saved.

The next implementation should treat DOC API as a convenience layer only. If it is used, the first check should be a rate-limited, one-company, one-week query that records only article count and returned field names.

### Taiwanese Finance-News Websites

CNA, Economic Daily News, MoneyDJ, and Anue / Cnyes are valuable local-market sources because their headlines and categories are closer to Taiwan investor attention than broad global media. They are not yet recommended as the first primary source because this audit did not verify a stable historical API or clearly permitted bulk collection path for the full 2025-2026 period.

These sources are still useful in two ways:

- As manual validation sources for a GDELT prototype, especially for high-attention companies such as TSMC.
- As possible future source-specific pipelines if terms-of-use review and a stable RSS / API / archive method are documented.

For these sources, the first implementation should avoid downloading raw article bodies. If a small crawler is later approved, it should store only metadata needed for counts: title, URL, timestamp, source, and matched company aliases.

### Official Announcements / Exchange Disclosures

MOPS is verified and useful, but it is not a market-news attention source. It records official company announcements, not media attention. It should be used to annotate events, validate dates, or explain spikes after the Hype Index is built from news sources. Using MOPS announcements as the main count source would change the meaning of the project from news attention to disclosure activity.

## Small Feasibility Checks Run

This audit did not download or save news records. Two safe checks were performed:

- Public pages were opened for official documentation or source pages, including GDELT, CNA RSS, Economic Daily News search, MoneyDJ news, Cnyes, and MOPS.
- A one-line GDELT DOC API probe was attempted for `"台積電"` over 2025-04-01 to 2025-04-08 with `maxrecords=5`. The sandboxed run first failed due DNS restrictions; the approved network run reached GDELT but returned HTTP 429. Because it did not return records, it is evidence of rate-limit / access risk rather than evidence of coverage.

No raw news data file was created, and no article text or fetched records were committed.

## Final Recommendation

The next implementation goal should be a **small GDELT metadata prototype**, not a full news pipeline:

1. Use GDELT 2.0 BigQuery or raw GKG metadata as the primary source candidate for the retrospective 2025-04-01 to 2026-03-31 period.
2. Test 3 to 5 Taiwan top-50 companies over 2 to 4 short windows from the project period.
3. Retrieve only metadata needed for counts: document identifier / URL, source, timestamp, title if available, language, and matched company aliases.
4. Compare a small sample against CNA / Economic Daily News / MoneyDJ / Cnyes public pages manually to estimate false positives, duplicates, and missing Taiwan-local coverage.
5. Do not store article text, do not compute production news counts, and do not compute the Hype Index until the source choice and alias rules pass this small feasibility test.

Recommended primary candidate: **GDELT 2.0 BigQuery / GKG metadata**.

Backup candidates: **CNA RSS / public pages, Economic Daily News, MoneyDJ, and Anue / Cnyes** for manual validation or future source-specific pipelines after terms review.

Event-context source: **MOPS / public company announcements**.

Rejected for now: **Commercial Times / ctee.com.tw**, because this audit did not verify an accessible, stable, and permitted access path.
