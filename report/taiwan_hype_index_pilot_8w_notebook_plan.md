# Taiwan Hype Index 8-Week Pilot Notebook Plan

This is a Markdown outline for a future final notebook. It is not an `.ipynb`
and does not add computation beyond the selected manual-v5 report artifacts.

## 1. Executive Summary

- Summarize the one-year TEJ market background and the selected manual-v5
  8-week Hype Index pilot.
- Report the validated 50-stock universe, 400 stock-week Hype panel rows, and
  zero missing Hype weeks.
- State that the analysis is descriptive and report-ready, not predictive or
  investment advice.

## 2. Introduction and Research Scope

- Explain the Taiwan-market weekly adaptation of the Hype Index idea.
- Define the main research scope: news attention, market-cap-adjusted attention,
  market structure, and contemporaneous return / volatility context.
- Exclude sentiment, forecasting, LLM, portfolio, Black-Litterman, and trading
  workflows.

## 3. Data Sources and Sample Alignment

### TEJ Market Data

- Use `data_source_summary.csv` and `tej_market_validation_summary.csv`.
- Describe the one-year market background period: 2025-04-01 to 2026-03-31.
- Report 50 tickers, 243 trading dates, 12,150 daily market-panel rows, and 52
  weekly market-cap weight dates.

### Adjusted Return Data

- Describe the Big5 semicolon-separated TEJ adjusted return file as the source
  for daily simple returns and log returns.
- Define return units as fractions in the report artifacts after converting TEJ
  percent fields.

### GDELT News Data

- Summarize the two manual-v5 GDELT chunks and their acquisition diagnostics.
- State that `matched_rows` is diagnostic and `news_count_unique_urls` is the
  main pilot count.

### Calendar-Day vs Trading-Day Alignment

- Separate the news calendar window, 2025-04-05 to 2025-05-30, from the Hype
  trading-date comparison window, 2025-04-07 to 2025-05-29.
- Note that 2025-05-30 is not forced into TEJ market data if it is not a trading
  day.

## 4. Universe and Market Structure

- Use `universe_summary.csv`, `sector_market_structure_summary.csv`,
  `sector_stock_count.png`, and `sector_market_cap_weight.png`.
- Describe the fixed TEJ-based top-50 universe as of 2025-03-31.
- Discuss sector composition and market-cap concentration.

## 5. Basic Quantitative Market Analysis

- Use `basic_return_statistics_full_vs_hype_window.csv`.
- Define the equal-weight daily market proxy:
  `R_EW,t = mean_i R_i,t`.
- Compare full-sample and Hype-window mean return, volatility, annualized
  volatility, distribution shape, drawdown-relevant extremes, and cumulative
  return.
- Use `equal_weight_cumulative_return_hype_window.png`,
  `equal_weight_rolling_volatility_20d_hype_window.png`, and
  `return_distribution_full_vs_hype_window.png`.

## 6. News Acquisition and Matching Validation

- Use `news_acquisition_summary.csv` and `pipeline_validation_summary.csv`.
- Report 5,376 candidate GDELT files, 5,372 processed, 4 missing, 0 failed, and
  7,107 diagnostic matched rows.
- Explain manual-v5 alias selection and the remaining GDELT coverage /
  deduplication limitations.

## 7. Hype Index Methodology

- Define `N_{i,w}` as the sum of stock-day unique GDELT document counts.
- Define `raw_hype = stock weekly news-count share`.
- Define `market_cap_adjusted_hype = raw_hype / weekly_market_cap_weight`.
- State that `weekly_market_cap_weight` uses the existing last-available
  TEJ trading day convention within each Saturday-to-Friday week.
- Make clear that weekly average market cap is not used in the current formula
  and would be a separate future alternative.

## 8. Stock-Level Hype Results

- Use `weekly_news_totals.csv`, `top_stock_news_counts.csv`,
  `top_raw_hype_stocks.csv`, and `top_market_cap_adjusted_hype_stocks.csv`.
- Use `weekly_news_counts.png`, `top_stock_news_counts.png`,
  `top_mean_raw_hype.png`, `top_mean_market_cap_adjusted_hype.png`,
  `raw_hype_heatmap_top_stocks.png`, and
  `market_cap_adjusted_hype_heatmap_top_stocks.png`.
- Interpret `raw_hype_vs_market_cap_weight_scatter.png`,
  `raw_hype_vs_market_cap_weight_scatter_zoom.png`, and
  `attention_size_imbalance_top_stocks.png`.

## 9. Sector-Level Hype Results

- Use `sector_hype_summary.csv` and `sector_weekly_hype_summary.csv`.
- Use `sector_news_attention_vs_market_cap_weight.png` and
  `sector_market_cap_adjusted_hype_heatmap.png`.
- Explain sector-level aggregation as a reporting aggregation over existing
  stock-level Hype rows, not a change to the stock-level Hype methodology.

## 10. Descriptive Relation with Returns and Volatility

- Use `hype_return_volatility_correlation_summary.csv`.
- Use `hype_vs_weekly_return_scatter.png` and
  `hype_vs_weekly_volatility_scatter.png`.
- Emphasize that all correlations are contemporaneous descriptive correlations,
  not prediction tests.

## 11. Key Stock Case Studies

- Use `key_stock_case_study_summary.csv`.
- Include the four default case-study figures:
  `key_stock_case_study_2330.png`, `key_stock_case_study_2454.png`,
  `key_stock_case_study_2317.png`, and `key_stock_case_study_2357.png`.
- Discuss weekly news count, weekly return, and weekly realized volatility for
  each selected stock.

## 12. Limitations

- Report that the pilot is 8 weeks, not a full-year replication.
- Report that `news_count_unique_urls` is not full ticker-week cross-day URL
  deduplication.
- Discuss GDELT entity extraction and media-coverage limitations.
- Clarify that the return and volatility analysis is descriptive and
  contemporaneous.

## 13. Conclusion and Next Steps

- Summarize what the manual-v5 pilot establishes for Taiwan-market news
  attention measurement.
- Identify report-safe next steps: manual review of outliers, event annotation,
  and possible extension to a longer window after data assumptions are stable.
