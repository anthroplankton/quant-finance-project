# Taiwan Hype Index Data Plan

## Purpose

這份文件定義 Taiwan Hype Index paper-inspired implementation 的 data-source 與 universe 設計。它的目的不是主張 fully paper-faithful article-level replication，而是把 Phase 1 需要的資料表、資料來源選擇、matching 規則、counting rule 與 missing-data rule 寫清楚，讓後續 bounded pilot 能保持可重現、可檢查，也適合寫進課程報告。

本文件只服務於 **The Hype Index: an NLP-driven Measure of Market News Attention** (arXiv:2506.06329) 的 Taiwan-market weekly adaptation。它不引入 sentiment model、LLM workflow、prediction test 或 portfolio application。

## Current Phase 1 Scope

Phase 1 的報告題目可以維持 **Taiwan 50 Hype Index**，但第一版 implementation 會把 universe operationalize 成 **TEJ-based fixed top-50 market-cap listed-stock universe**。因為目前 TEJPro UI 沒有提供可直接取得、可在本專案中檢查的 official Taiwan 50 constituent flag，Phase 1 先使用 TEJ market capitalization 在 **2025-03-31** 的截面選出上市普通股前 50 名，作為固定 large-cap universe。

這個 universe 是 Taiwan 50 report framing 下的 TEJ-based operational proxy，不應寫成官方 Taiwan 50 指數成分股清單。Historical constituent reconstruction 先延後。原因是 Phase 1 不主張 predictive result、portfolio result 或 backtest result；使用固定 large-cap universe 足以支撐 descriptive replication。若後續進入 predictive tests 或 returns analysis，official / historical constituents 會成為重要改進，以降低 survivorship bias 與 index-membership mismatch。

Phase 1 應產出：

- fixed Taiwan 50 universe table；
- documented alias table；
- sample news-count pipeline design；
- raw Hype Index；
- capitalization-adjusted Hype Index；
- descriptive plots only。

Phase 1 不包含 sentiment、LLM、prediction test 或 portfolio application。

## First Implementation Pilot Window

The first implementation will use an 8-week pilot window for news collection and Hype Index construction rather than immediately processing the full 2025-04-01 to 2026-03-31 market panel.

- News calendar window: **2025-04-05 to 2025-05-30 inclusive**.
- Weekly bins: **Saturday-to-Friday**, ending on Fridays.
- Length: **56 calendar days**, or exactly **8 full 7-day weeks**.
- First week: **2025-04-05 to 2025-04-11**.
- Last week: **2025-05-24 to 2025-05-30**.
- Expected stock-week panel size for the fixed top-50 universe: **50 × 8 = 400 rows**.

The pilot window starts at the first complete Saturday-to-Friday weekly bin after the 2025-04-01 TEJ market-panel start. It does not exclude the 2025-04-03 to 2025-04-06 holiday/weekend period entirely; news is collected on calendar days, including weekends and holidays. It avoids partial weeks, includes important April 2025 Taiwan market/news events, and keeps raw GDELT network volume manageable for a first descriptive pilot. The first report should treat the 8 weekly observations as bounded descriptive evidence only and should avoid strong time-series inference.

The full TEJ market panel remains the market-data source for the project. The first report window is only the 8-week news / Hype Index pilot window. Weekly market-cap weights should be aligned using the last available TEJ trading day within each Saturday-to-Friday week. Do not assume each Friday is a trading day; if Friday is absent because of a market holiday or missing trading date, use the last available trading day in that same week.

Goal 3A aggregates the completed local GDELT chunk-level `stock_day_counts.csv` files into a zero-filled **50 × 8 = 400 row** stock-week news-count panel. Before zero filling, the selected chunk `probe_summary.json` date ranges must cover the full pilot window continuously, without gaps or overlaps; otherwise, an omitted chunk could be mistaken for zero-news weeks. Goal 3A also validates GDELT file-grid coverage: capped probes are rejected, `candidate_file_count_capped` must equal `candidate_file_count_uncapped`, and `files_processed + files_missing + files_failed` must equal the uncapped candidate count. Each chunk's `stock_day_counts.csv` rows must also fall inside that same chunk's inclusive `probe_summary.json` `start_date` to `end_date` range, so stale count files cannot be counted under the wrong chunk. The chunk count file must reconcile with its paired probe summary: `sum(stock_day_counts.matched_rows)` must equal `probe_summary.matched_rows`, and an empty count file is valid only when the summary also reports zero matched rows. After date, file-grid, per-chunk row-date, ticker, duplicate, and count-reconciliation validation all pass, zero-filled stock-week rows mean the data source covered that week but the stock had no matched news.

The original Hype Index paper counts news articles in the measurement period. This bounded 8-week pilot uses a Taiwan-market weekly adaptation based on the retained aggregate GDELT probe artifacts. The main count column is `news_count_unique_urls`, operationalized as:

\[
N_{i,w} = \sum_{d \in w}
\text{stock-day unique GDELT document count}_{i,d}.
\]

`matched_rows` is diagnostic only and is not the main news-count input. The current pilot does **not** perform full ticker-week cross-day URL deduplication. If the same `document_identifier` appears for the same ticker on multiple days in the same Saturday-to-Friday week, `news_count_unique_urls` can overcount relative to an exact article-level weekly count. Full ticker-week URL deduplication would require retaining URL-level matched rows, not only `stock_day_counts.csv`. This is a first-implementation limitation and future improvement, not a blocker for the current bounded descriptive pilot. Goal 3A is still not raw Hype Index computation, market-cap-adjusted Hype Index computation, or a join with TEJ weekly market-cap weights.

Goal 3B aligns the Goal 3A stock-week news-count panel with the TEJ weekly market-cap weights. The join key is `ticker` plus `week_end`, and the TEJ `weight_date` must fall inside the same Saturday-to-Friday bin, with weights summing to 1 for each selected week. The output uses canonical Saturday-to-Friday weekly bin labels, including `week_index`; any stale input `week_index` must match the canonical bins or the join fails. The output is a **Hype-ready input panel** under ignored `data/processed/hype_index/` paths. It includes `weekly_total_news_count_unique_urls` only as a diagnostic denominator candidate for the later raw Hype calculation; Goal 3B still does not compute `raw_hype`, `hype_index`, capitalization-adjusted Hype, or any news-count-to-weight ratio.

Goal 3C computes a paper-inspired Hype Index implementation based on the local reference paper in `references/local/arXiv-2506.06329v1`, with a Taiwan-market weekly adaptation. In the original paper, the Hype Index is defined as a daily news-attention share for the S&P 100 setting, and the Capitalization Adjusted Hype Index divides that news-attention share by market capitalization weight. In this project, the frequency is weekly, the universe is the TEJ-based fixed top-50 listed-stock universe, the window is **2025-04-05 to 2025-05-30**, the main count is the Goal 3A `news_count_unique_urls` approximation above, and the size denominator is TEJ `weekly_market_cap_weight`.

For stock \(i\) and week \(w\), the project uses:

\[
N_{i,w}
= \sum_{d \in w}
\text{stock-day unique GDELT document count}_{i,d}
= \texttt{news\_count\_unique\_urls}_{i,w}, \quad
N_w = \sum_i N_{i,w}
\]

\[
\text{raw\_hype}_{i,w} = \frac{N_{i,w}}{N_w}
\]

\[
\text{market\_cap\_adjusted\_hype}_{i,w}
= \frac{\text{raw\_hype}_{i,w}}
{\texttt{weekly\_market\_cap\_weight}_{i,w}}
\]

For weeks with \(N_w > 0\), `raw_hype` sums to 1 within each week. `market_cap_adjusted_hype` is an attention-to-size ratio and is not normalized to sum to 1; a value above 1 means the stock receives more news attention than its market-cap weight, and a value below 1 means it receives less. For weeks with \(N_w = 0\), `raw_hype`, `market_cap_adjusted_hype`, and `raw_hype_minus_market_cap_weight` are marked missing rather than forced to zero.

## Universe Source Plan

Universe 的 first implementation source 是 local TEJPro manual exports。若未來取得 official 或 index-provider Taiwan 50 constituent / constituent-weight source，應另行記錄 source、as-of date、methodology 差異，並決定是否替換或對照目前的 TEJ-based top-50 proxy。若使用 ETF holdings 作為輔助來源，報告中應清楚標示它是 proxy source，而不是 index methodology 本身。

Universe source record 應至少保存下列資訊：

- access date；
- constituent selection date；
- source name；
- source interface or file path；
- ticker；
- official Chinese company name；
- official English company name；
- market capitalization used for top-50 selection if available；
- notes on whether the source is official, index-provider, TEJ-based proxy, ETF disclosure, or manually reconciled.

目前 Phase 1 應標示 constituent selection date 為 **2025-03-31**。Market panel period 是 **2025-04-01 to 2026-03-31**。Historical constituents 是後續 improvement；若未來進行 predictive tests，應補上 historical constituent table 或明確描述無法取得時的限制。

## Local TEJPro Raw Files

TEJPro data are licensed local files and must stay outside Git. The current workflow uses two user-provided manual exports under `data/raw/tej/`:

| Local file | TEJ source | Role in Phase 1 |
|---|---|---|
| `data/raw/tej/tej_company_basic_tse_current_minimal_20260615.csv` | TEJ Company DB / 基本資料 | Company metadata, ticker-name mapping, Chinese and English company names, and industry classification. It is not the source of the top-50 selection itself. |
| `data/raw/tej/tej_top50_daily_market_panel_20250401_20260331.csv` | TEJ 股價資料庫 / 未調整股價(日) | Daily close, shares outstanding, market capitalization, volume, and traded value for the fixed top-50 universe selected by TEJ market capitalization as of 2025-03-31. |

The raw files under `data/raw/tej/` are local-only and ignored by Git. TEJ-derived processed outputs should be regenerated locally under `data/processed/tej/` and should also remain ignored. Any exception would require a separate explicit approval and license / redistribution review; the current Phase 1 documentation update does not approve committing raw TEJ files or TEJ-derived processed files.

The selected 8-week GDELT probe evidence remains local-only under ignored `data/processed/news/` paths. No Hype Index has been computed yet.

## Universe Table Schema

| Field | Description |
|---|---|
| `stock_id` | Project-internal stable identifier. |
| `ticker` | Listed ticker, with suffix convention documented separately if needed. |
| `exchange` | Exchange or market, such as TWSE. |
| `official_chinese_name` | Official Chinese company name from the selected source. |
| `official_english_name` | Official English company name when available. |
| `short_names` | Common Chinese or English short names. |
| `aliases` | Other names used in news, including brands, group names, or ticker aliases. |
| `industry` | More granular industry classification. |
| `sector_group` | Coarser sector group used for sector-level Hype Index. |
| `constituent_source` | Source name for constituent membership. |
| `constituent_as_of_date` | Date represented by the constituent list. |
| `notes` | Manual reconciliation notes, ambiguity flags, or source caveats. |

## Company-Name and Alias Matching Design

Company matching should combine official names and documented aliases. For each stock, the alias table should include official Chinese name, official English name, common Chinese short names, ticker aliases, major brand names, and group names when they are frequently used in news.

Alias rules must be inspectable and documented. A later implementation should make it possible to answer why a news item matched a stock: exact official-name match, short-name match, ticker match, brand-name match, or manually reviewed alias match.

Chinese company-name matching has several risks. Some short names are common words; some group names may refer to multiple listed firms; some brand names may refer to products rather than the listed parent company; and some industry phrases may produce false positives. Ambiguous aliases should be flagged in the universe table or a separate alias-review note before they are used for production counts.

Phase 1 should prefer conservative matching rules. It is better to miss some uncertain mentions in the first descriptive version than to inflate counts with broad, hard-to-audit aliases.

For the 8-week GDELT pilot, the `expanded_reviewed` allowlist should enable official full names and only explicitly curated high-confidence short or brand aliases. Core Chinese short names such as `台積電`, `聯發科`, and `鴻海` are enabled when present, while pure tickers, generic English acronyms, and broad aliases such as `統一`, `長榮`, `台塑`, `南亞`, `國泰`, `富邦`, `第一`, `合庫`, and `台新` remain disabled unless a later manual review explicitly changes the policy.

## News Source Candidates

The news source has not been finalized. Candidate source types are listed here so the project can compare coverage and reproducibility before implementation.

A separate feasibility audit has been added at `docs/taiwan_hype_index_news_source_audit.md`. That audit is the current reference for verified, partially verified, rejected, and event-context-only source candidates. This data plan keeps only the high-level design role of news sources.

**GDELT** is an open-data candidate. Its advantages are scale, reproducibility, public availability, and global news coverage. Its risks are entity-matching noise, uneven Chinese-language coverage, duplicate or syndicated news, and possible mismatch between global news attention and Taiwan local-market attention.

**Selected Taiwanese finance news RSS/web sources** are possible local-market candidates. They may better capture Taiwan-specific market events, company news, and Chinese-language naming conventions. Their risks are source bias, coverage limits, duplicate reposts, changing website structure, RSS availability, copyright / terms-of-use constraints, and lower reproducibility if historical archives are incomplete.

**Official announcements and exchange disclosures** may be useful for event-study context, but they are not a substitute for market news attention. They can help annotate events, but using them as the main news-count source would change the meaning of the Hype Index.

The final source choice should compare:

- reproducibility and historical availability;
- coverage of Taiwan 50 companies;
- Chinese-language quality;
- source bias across sectors;
- duplicate-news behavior;
- URL and metadata stability;
- terms-of-use and redistribution constraints.

This project should not implement scraping until the source choice and terms-of-use constraints are documented.

## News Table Schema

| Field | Description |
|---|---|
| `news_id` | Stable identifier from source, or project-generated hash if allowed. |
| `source` | News source name. |
| `title` | Article title or headline. |
| `published_at` | Publication timestamp with timezone convention documented. |
| `url` | Article URL when available and legally recordable. |
| `language` | Language code or label. |
| `matched_stock_ids` | Stock IDs matched by documented rules. |
| `matched_company_names` | Company names or aliases that triggered the match. |
| `match_rule` | Exact rule used for the match. |
| `duplicate_group_id` | Identifier for deduplicated article groups. |
| `is_duplicate` | Whether the row is treated as a duplicate. |
| `notes` | Ambiguity flags, manual review notes, or source caveats. |

## Counting Rules to Decide

The reference Hype Index idea counts media attention by stock or sector. For Taiwan news, a single article may mention multiple Taiwan 50 companies, especially in sector-wide electronics, AI, financial, or market-summary articles. The counting rule must therefore be fixed before producing indices.

Phase 1 conceptual rule: **one article mentioning multiple companies counts once for each matched company**. This rule is transparent, easy to audit, and directly supports stock-level and sector-level news-share construction. It also matches the intuition that one article can allocate attention to more than one company.

The current bounded 8-week pilot approximates that article-level rule with aggregate GDELT `stock_day_counts.csv` outputs. It uses `news_count_unique_urls` as the sum of stock-day unique document counts by ticker-week. It does not yet have the URL-level matched table needed to deduplicate the same ticker-document pair across multiple days inside a week.

Two alternatives should remain documented:

- **Fractional counting**: one article with multiple matched companies contributes `1 / number_of_matches` to each company. This reduces broad-market article inflation but is less intuitive for attention exposure.
- **Primary-company-only counting**: one article contributes only to the main matched company. This can reduce noise, but it requires reliable primary-entity detection and may be too subjective for Phase 1.

The default rule should be revisited if sector-wide articles dominate the counts or if duplicate broad-market articles distort sector-level Hype Index. A later exact article-count implementation should retain URL-level matched rows and deduplicate by ticker-week before computing \(N_{i,w}\).

## Market Cap and Price Data Source Plan

Capitalization-adjusted Hype Index needs market-cap weights. For the current first implementation, TEJ 股價資料庫 / 未調整股價(日) is the planned market-data source for daily close, shares outstanding, market capitalization, volume, and traded value. The top-50 universe is selected using TEJ market capitalization as of 2025-03-31, and the daily market panel covers 2025-04-01 to 2026-03-31.

The preferred input is direct market capitalization for each stock at the chosen frequency. If direct market capitalization is not available or fails validation, the fallback is:

$$
market\ cap = close\ price \times shares\ outstanding.
$$

The project should record:

- source name and local file path;
- access date;
- data frequency;
- whether prices are close or adjusted close;
- adjusted-price assumptions;
- shares outstanding assumptions;
- corporate action handling;
- missing-data handling;
- whether market cap is direct or reconstructed.

The current market data are local TEJPro manual exports, not committed project artifacts. Processed market-data outputs should be regenerated locally under `data/processed/tej/` and must not be treated as report results until validation and index construction code are implemented.

## Market Data Table Schema

| Field | Description |
|---|---|
| `stock_id` | Project-internal stable identifier. |
| `date` | Trading date or period-end date. |
| `close` | Close price from selected source. |
| `adjusted_close` | Adjusted close price if available. |
| `shares_outstanding` | Shares outstanding used for market-cap reconstruction. |
| `market_cap` | Direct or reconstructed market capitalization. |
| `market_cap_source` | Source for market cap or shares outstanding. |
| `price_source` | Source for price data. |
| `notes` | Missing-data notes, corporate action caveats, or manual adjustments. |

## Frequency Decision

Weekly frequency should be the default first implementation. Weekly aggregation reduces sparse news-count problems, smooths day-to-day source noise, and is easier to interpret for a descriptive Phase 1 replication.

Daily frequency can still be used for event-study plots. For example, a major market event can be shown with daily Hype Index and price / volatility context around the event window, while the main descriptive tables use weekly measures.

Daily data should aggregate into weekly counts by a documented rule. The current pilot sums stock-day unique GDELT document counts within each week; a future URL-level implementation should deduplicate ticker-document pairs across days before computing exact article-level weekly counts. Weekly market-cap weight should use a documented convention, such as the last available trading day of the week or the average market cap across trading days. The first implementation should choose one convention and keep it consistent across all stocks and sectors.

## Missing-Data and Zero-Denominator Rules

Zero news-count denominator: if no matched news appears for the entire universe in a period, raw Hype Index and capitalization-adjusted Hype Index should be marked missing for that period rather than forced to zero.

Missing market cap: if a stock lacks market cap for a period, the project should first try a documented fallback using close price and shares outstanding. If that is not possible, the stock-period should be marked missing and the denominator convention should be reported.

Missing shares outstanding: if market cap must be reconstructed but shares outstanding is missing, do not silently forward-fill without a rule. Any forward-fill or interpolation must be documented.

Missing price: if price is missing on a trading day, use the selected data source's official missing-data convention where possible. For weekly frequency, the project may use the last available trading day within the week if documented.

Non-trading days: news may arrive on non-trading days. Weekly aggregation can include weekend news in the relevant calendar week. For daily event-study plots, non-trading-day news should be assigned according to a documented rule, such as the publication date for attention plots and the next trading day for market reaction comparisons.

Duplicate news: duplicate, syndicated, or reposted articles should eventually be grouped with `duplicate_group_id` or a normalized URL / document identifier. The current bounded pilot does not perform full ticker-week cross-day URL deduplication because only aggregate `stock_day_counts.csv` is retained. This limitation should be reported with any table based on the first implementation.

## First Implementation Decision

The first implementation should produce the following design-backed outputs locally:

- TEJ-based fixed top-50 market-cap universe table as of 2025-03-31;
- documented alias table;
- sample news-count pipeline design;
- raw Hype Index;
- capitalization-adjusted Hype Index;
- descriptive plots only.

The first implementation should not include sentiment, LLM calls, prediction tests, portfolio application, live trading logic, or claims about empirical predictive performance. At the manual-v5 Goal 4A stage, the local bounded 8-week pilot pipeline has passed Goal 3A, Goal 3B, and Goal 3C validation. The pipeline remains a bounded descriptive pilot, not a full-year replication.

Goal 4A adds report-ready tables and figures that summarize the already-computed manual-v5 Goal 3C Hype Index outputs under `report/results/pilot_8w_manual_v5/` and `report/figures/pilot_8w_manual_v5/`; it does not rerun news aggregation, rebuild the Hype-ready input panel, recompute Hype formulas, or create the final notebook.

Goal 4B extends the same reporting layer with notebook-ready market-quant
artifacts. It uses the one-year TEJ market background from 2025-04-01 to
2026-03-31 together with the selected 8-week Hype main analysis. The
Hype-window TEJ trading-date comparison is 2025-04-07 to 2025-05-29, so the
2025-05-30 news date is not forced into TEJ market data when it is not a
trading day. Goal 4B adds sector-level reporting aggregation, descriptive
return / realized-volatility diagnostics, revised heatmaps and scatter figures,
and key-stock case-study figures. It does not change the Hype formulas, does
not replace the existing last-available-trading-day weekly market-cap weight
convention with weekly average market cap, and does not create the final
notebook.

Goal 4C revises the report layer so stock-level and sector-level
cross-sectional Hype rankings use pooled pilot-window quantities only. For
stocks, pooled raw Hype is \(\sum_w N_{i,w} / \sum_w \sum_j N_{j,w}\), pooled
market-cap weight is \(\sum_w MC_{i,w} / \sum_w \sum_j MC_{j,w}\), and pooled
market-cap-adjusted Hype is their ratio. Sector pooled Hype uses the same
construction after aggregating news counts and market capitalization over
stocks in each TEJ industry group. Equal-week arithmetic mean Hype is no longer
used for report cross-sectional rankings because it does not generally equal
the pilot-window pooled news share. Weekly Hype remains available only for
time-path heatmaps, key-stock weekly case studies, and contemporaneous
descriptive return / volatility comparisons.

Manual-v5 completion facts for the selected 8-week pilot:

- selected chunks: 2025-04-05 to 2025-05-02 and 2025-05-03 to 2025-05-30;
- chunk candidate files: 2,688 + 2,688;
- files processed: 2,686 + 2,686;
- files missing: 2 + 2;
- files failed: 0 + 0;
- diagnostic matched rows: 4,141 + 2,966 = 7,107;
- Goal 3A stock-week rows: 400, validation passed;
- Goal 3B Hype-ready rows: 400, validation passed;
- Goal 3C Hype Index rows: 400, validation passed, missing Hype weeks: 0;
- weekly total `news_count_unique_urls`: 1,225, 1,343, 737, 836, 646, 808, 884, and 628.
