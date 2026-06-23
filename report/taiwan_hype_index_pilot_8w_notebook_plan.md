# Taiwan Hype Index 8-Week Pilot Notebook Plan

This is a Markdown outline for a future final notebook. It is not an `.ipynb`
and does not add computation beyond the selected manual-v5 report artifacts.

## 1. Executive Summary

- Summarize the one-year TEJ market background and the selected manual-v5
  8-week Taiwan Hype Index pilot.
- Report the fixed 50-stock universe, 400 stock-week Hype panel rows, zero
  missing Hype weeks, and the pooled Hype cross-sectional results.
- State that the analysis is descriptive and report-ready, not predictive,
  portfolio-oriented, or investment advice.

## 2. Introduction and Research Scope

- Explain the Taiwan-market weekly adaptation of the Hype Index idea.
- Define the report scope: market structure, news attention, pooled
  market-cap-adjusted attention, weekly Hype dynamics, and contemporaneous
  return / volatility context.
- Exclude sentiment, forecasting, LLM, portfolio, Black-Litterman, and trading
  workflows.

## 3. Data Sources and Sample Alignment

- TEJ market data: use `data_source_summary.csv`,
  `tej_market_validation_summary.csv`, `universe_summary.csv`, and
  `sector_market_structure_summary.csv`.
- TEJ adjusted return data: document the Big5 semicolon-separated export and
  the conversion of TEJ percent fields into return fractions.
- TEJ industry code / Chinese label mapping: use
  `tej_industry_label_mapping.csv`; figures use ASCII-safe industry codes while
  tables retain full Chinese labels.
- GDELT manual-v5 news data: use `news_acquisition_summary.csv` and
  `pipeline_validation_summary.csv`.
- Calendar-day vs trading-day alignment: keep the news calendar period
  2025-04-05 to 2025-05-30 separate from the TEJ trading comparison period
  2025-04-07 to 2025-05-29. Do not force 2025-05-30 into market data if it is
  not a TEJ trading day.

## 4. Universe and Market Structure

- Use `universe_summary.csv`, `sector_market_structure_summary.csv`,
  `sector_stock_count.png`, and `sector_market_cap_weight.png`.
- Describe the fixed TEJ-based top-50 universe as of 2025-03-31.
- Discuss sector composition and market-cap concentration.

## 5. Basic Quantitative Market Analysis

- Define simple return, log return, and the equal-weight daily market proxy:
  `R_EW,t = mean_i R_i,t`.
- Use `basic_return_statistics_full_vs_hype_window.csv` to compare the
  2025-04-01 to 2026-03-31 market background with the 2025-04-07 to
  2025-05-29 Hype trading window.
- Use `equal_weight_cumulative_return_hype_window.png`,
  `equal_weight_rolling_volatility_20d_hype_window.png`, and the curated
  return-statistics table. The return-distribution histogram is not part of
  the core notebook figure set.

## 6. News Acquisition and Matching Validation

- Report the manual-v5 GDELT chunk diagnostics: 5,376 candidate files, 5,372
  processed, 4 missing, 0 failed, and 7,107 diagnostic matched rows.
- State that `news_count_unique_urls` is the main pilot count and `matched_rows`
  is diagnostic only.
- Explain manual-v5 alias selection and the remaining GDELT coverage and
  deduplication limitations.

## 7. Pooled Hype Index Methodology

- Weekly count primitive: `N_{i,w}` is the sum of stock-day unique GDELT
  document counts for stock `i` in Saturday-to-Friday week `w`.
- Pooled raw Hype:
  `pooled_raw_hype_i = sum_w N_{i,w} / sum_w sum_j N_{j,w}`.
- Pooled market-cap weight:
  `pooled_market_cap_weight_i = sum_w MC_{i,w} / sum_w sum_j MC_{j,w}`.
- Pooled market-cap-adjusted Hype:
  `pooled_market_cap_adjusted_hype_i = pooled_raw_hype_i /
  pooled_market_cap_weight_i`.
- Pooled sector Hype: aggregate each numerator and denominator over stocks in
  industry group `G` before taking ratios.
- Explain why arithmetic mean weekly Hype is not used for cross-sectional
  rankings: `(1/T) sum_w (N_{i,w} / N_w)` does not generally equal
  `sum_w N_{i,w} / sum_w N_w`.

## 8. Stock-Level Pooled Hype Results

- Use `stock_pooled_hype_summary.csv`, `top_pooled_raw_hype_stocks.csv`,
  `top_pooled_market_cap_adjusted_hype_stocks.csv`, and
  `top_pooled_attention_size_imbalance_stocks.csv`.
- Use `top_pooled_raw_hype_stocks.png`,
  `top_pooled_market_cap_adjusted_hype_stocks.png`,
  `pooled_raw_hype_vs_pooled_market_cap_weight_scatter.png`,
  `pooled_raw_hype_vs_pooled_market_cap_weight_scatter_zoom.png`, and
  `pooled_attention_size_imbalance_top_stocks.png`.

## 9. Sector-Level Pooled Hype Results

- Use `sector_pooled_hype_summary.csv`,
  `top_pooled_sector_market_cap_adjusted_hype.csv`,
  `tej_industry_label_mapping.csv`, and `sector_weekly_hype_summary.csv`.
- Use `pooled_sector_raw_hype_vs_pooled_market_cap_weight_scatter.png`,
  `pooled_sector_raw_hype_vs_pooled_market_cap_weight_scatter_zoom.png`,
  `pooled_sector_market_cap_adjusted_hype_ranking.png`, and
  `pooled_sector_attention_size_imbalance.png`.
- Explain sector-level aggregation as a reporting aggregation over existing
  stock-level Hype rows, not a change to the Goal 3C weekly Hype formulas.

## 10. Weekly Hype Dynamics

- Use `weekly_news_totals.csv`, `weekly_hype_summary.csv`,
  `weekly_news_counts.png`, `raw_hype_heatmap_top_stocks.png`,
  `market_cap_adjusted_hype_heatmap_top_stocks.png`, and
  `sector_market_cap_adjusted_hype_heatmap.png`.
- Treat these as weekly time-path diagnostics, not mean-based
  cross-sectional rankings.

## 11. Descriptive Relation with Returns and Volatility

- Use `hype_return_volatility_correlation_summary.csv`.
- Use `hype_vs_weekly_return_scatter.png`,
  `hype_vs_weekly_volatility_scatter.png`,
  `cap_adjusted_hype_vs_weekly_return_scatter.png`, and
  `cap_adjusted_hype_vs_weekly_volatility_scatter.png`.
- Emphasize: contemporaneous descriptive correlation only; not a predictive
  test.

## 12. Key Stock Case Studies

- Use `key_stock_case_study_summary.csv`.
- Include `key_stock_case_study_2330.png`,
  `key_stock_case_study_2454.png`, `key_stock_case_study_2317.png`, and
  `key_stock_case_study_2357.png`.
- Discuss weekly news count, weekly raw Hype versus market-cap weight, weekly
  market-cap-adjusted Hype, weekly return, and weekly realized volatility.

## 13. Limitations

- The pilot is 8 weeks, not a full-year Hype replication.
- `news_count_unique_urls` is not full ticker-week cross-day URL deduplication.
- GDELT entity extraction and media-coverage limits remain.
- Return and volatility analysis is descriptive and contemporaneous.
- Future work could study alternative transformed attention ratios, but those
  extensions are not part of this notebook plan.

## 14. References

- Cao, Wunkaew, and Geman (2025), *The Hype Index: an NLP-driven Measure of
  Market News Attention*, arXiv:2506.06329.
- GDELT Project data documentation.
- Taiwan Economic Journal / TEJ local exports.
- Project documentation: `docs/taiwan_hype_index_data_plan.md`,
  `docs/taiwan_hype_index_news_acquisition_feasibility.md`, and
  `report/progress_log.md`.
