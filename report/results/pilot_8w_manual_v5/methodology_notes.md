# Methodology Notes

- This is a Taiwan-market weekly adaptation, not an exact full-year replication.
- N_{i,w} is operationalized as the sum of stock-day unique GDELT document counts within week w.
- The current pilot does not perform full ticker-week cross-day URL deduplication.
- matched_rows is diagnostic only.
- GDELT captures global media/entity attention, not pure Taiwan local financial-news attention.
- market_cap_adjusted_hype is an attention-to-size ratio and is not normalized to sum to 1.
- Cross-sectional report rankings use pooled 8-week Hype: total stock news divided by total pilot news, with pooled market-cap weight from aligned weekly TEJ market caps.
- Equal-week arithmetic mean Hype is not used for stock or sector cross-sectional ranking because it does not generally equal pooled news share over the pilot window.
- Weekly Hype is retained for time-path heatmaps, case studies, and contemporaneous descriptive return / volatility comparisons.
- No forecasting, backtesting, portfolio optimization, or investment advice is produced.
