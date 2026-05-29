# Taiwan Hype Index Data Plan

## Purpose

這份文件定義 Taiwan Hype Index replication 的 data-source 與 universe 設計。它的目的不是立即下載資料或實作 pipeline，而是先把 Phase 1 需要的資料表、資料來源選擇、matching 規則、counting rule 與 missing-data rule 寫清楚，讓後續實作能保持可重現、可檢查，也適合寫進課程報告。

本文件只服務於 **The Hype Index: an NLP-driven Measure of Market News Attention** (arXiv:2506.06329) 的台灣市場 replication / adaptation。它不引入 sentiment model、LLM workflow、prediction test 或 portfolio application。

## Current Phase 1 Scope

Phase 1 使用 **current Taiwan 50 constituents** 作為固定 large-cap universe，目標是做 descriptive Hype Index replication。這個選擇讓第一版可以專注在 news counts、company matching、raw Hype Index 與 market-cap-adjusted Hype Index，而不是先處理完整 historical index membership。

Historical constituent reconstruction 先延後。原因是 Phase 1 不主張 predictive result、portfolio result 或 backtest result；使用 current constituents 作為固定 universe 足以支撐 descriptive replication。若後續進入 predictive tests 或 returns analysis，historical constituents 會成為重要改進，以降低 survivorship bias。

Phase 1 應產出：

- fixed Taiwan 50 universe table；
- documented alias table；
- sample news-count pipeline design；
- raw Hype Index；
- capitalization-adjusted Hype Index；
- descriptive plots only。

Phase 1 不包含 sentiment、LLM、prediction test 或 portfolio application。

## Universe Source Plan

Universe 的 primary source 應優先使用 official 或 index-provider 的 Taiwan 50 constituent / constituent-weight source。例如官方交易所、index provider、或可追溯到 index provider 的 constituent / weight disclosure。若使用 ETF holdings 作為輔助來源，報告中應清楚標示它是 proxy source，而不是 index methodology 本身。

Universe source record 應至少保存下列資訊：

- access date；
- constituent selection date；
- source name；
- source URL；
- ticker；
- official Chinese company name；
- official English company name；
- constituent weight if available；
- notes on whether the source is official, index-provider, ETF disclosure, or manually reconciled.

如果 Phase 1 使用 current constituents，文件和結果都應標示 as-of date。Historical constituents 是後續 improvement；若未來進行 predictive tests，應補上 historical constituent table 或明確描述無法取得時的限制。

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

## News Source Candidates

The news source has not been finalized. Candidate source types are listed here so the project can compare coverage and reproducibility before implementation.

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

Phase 1 default rule: **one article mentioning multiple companies counts once for each matched company**. This rule is transparent, easy to audit, and directly supports stock-level and sector-level news-share construction. It also matches the intuition that one article can allocate attention to more than one company.

Two alternatives should remain documented:

- **Fractional counting**: one article with multiple matched companies contributes `1 / number_of_matches` to each company. This reduces broad-market article inflation but is less intuitive for attention exposure.
- **Primary-company-only counting**: one article contributes only to the main matched company. This can reduce noise, but it requires reliable primary-entity detection and may be too subjective for Phase 1.

The default rule should be revisited if sector-wide articles dominate the counts or if duplicate broad-market articles distort sector-level Hype Index.

## Market Cap and Price Data Source Plan

Capitalization-adjusted Hype Index needs market-cap weights. The preferred input is direct market capitalization for each stock at the chosen frequency. If direct market capitalization is not available, the fallback is:

$$
market\ cap = close\ price \times shares\ outstanding.
$$

The project should record:

- source name;
- access date;
- data frequency;
- whether prices are close or adjusted close;
- adjusted-price assumptions;
- shares outstanding assumptions;
- corporate action handling;
- missing-data handling;
- whether market cap is direct or reconstructed.

No market data has been downloaded yet. Any later implementation should document the source and access date before producing capitalization-adjusted Hype Index.

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

Daily data should aggregate into weekly counts by summing matched article counts within the week. Weekly market-cap weight should use a documented convention, such as the last available trading day of the week or the average market cap across trading days. The first implementation should choose one convention and keep it consistent across all stocks and sectors.

## Missing-Data and Zero-Denominator Rules

Zero news-count denominator: if no matched news appears for the entire universe in a period, raw Hype Index and capitalization-adjusted Hype Index should be marked missing for that period rather than forced to zero.

Missing market cap: if a stock lacks market cap for a period, the project should first try a documented fallback using close price and shares outstanding. If that is not possible, the stock-period should be marked missing and the denominator convention should be reported.

Missing shares outstanding: if market cap must be reconstructed but shares outstanding is missing, do not silently forward-fill without a rule. Any forward-fill or interpolation must be documented.

Missing price: if price is missing on a trading day, use the selected data source's official missing-data convention where possible. For weekly frequency, the project may use the last available trading day within the week if documented.

Non-trading days: news may arrive on non-trading days. Weekly aggregation can include weekend news in the relevant calendar week. For daily event-study plots, non-trading-day news should be assigned according to a documented rule, such as the publication date for attention plots and the next trading day for market reaction comparisons.

Duplicate news: duplicate, syndicated, or reposted articles should be grouped with `duplicate_group_id`. Phase 1 should compute the main index after excluding duplicates, while optionally reporting how many duplicates were removed.

## First Implementation Decision

The first implementation should produce the following design-backed outputs only:

- fixed Taiwan 50 universe table;
- documented alias table;
- sample news-count pipeline design;
- raw Hype Index;
- capitalization-adjusted Hype Index;
- descriptive plots only.

The first implementation should not include sentiment, LLM calls, prediction tests, portfolio application, live trading logic, or claims about empirical predictive performance.
