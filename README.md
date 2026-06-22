# Quant Finance Course Project

This repository is for a Quantitative Finance course project.

The active first-phase project direction is a Taiwan-market replication and adaptation of **The Hype Index: an NLP-driven Measure of Market News Attention** (arXiv:2506.06329). The report title may remain Taiwan 50 Hype Index, while the first implementation operationalizes the universe as a TEJ-based fixed top-50 market-cap listed-stock universe selected as of 2025-03-31.

## Current stage

- Course assignments
- Paper reading notes
- Taiwan Hype Index architecture design notes
- Taiwan Hype Index data-source and universe plan
- Taiwan Hype Index news-source feasibility audit
- Taiwan Hype Index news-acquisition feasibility sprint
- GDELT metadata prototype plan
- Minimal Python project setup

## Repository layout

- `AGENTS.md`: repository-wide instructions for Codex and AI-assisted contributors
- `docs/`: paper summaries, formulas, architecture notes, and Taiwan Hype Index data plans
- `assignments/`: course assignments
- `report/`: progress logs, report drafts, curated results, and figures
- `data/`: local data area; raw and processed data are not committed by default

## Local TEJ cleaning

When the licensed TEJPro manual exports are present under `data/raw/tej/`, regenerate the ignored processed market-data files with:

```bash
uv run python scripts/build_tej_market_data.py
```

The script writes cleaned metadata, the daily market panel, the fixed top-50 universe, weekly market-cap weights, and a date-labeled validation summary under `data/processed/tej/`. These files remain local-only and are not Hype Index or news-count results.

Build the local-only top-50 alias review tables after TEJ processed outputs exist:

```bash
uv run python scripts/build_top50_alias_table.py
```

For the current GDELT raw GKG probe route, generate the expanded-reviewed allowlist:

```bash
uv run python scripts/build_top50_alias_table.py --profile expanded_reviewed
```

The alias tables are TEJ-derived and are written under ignored `data/processed/news/aliases/`. Pure ticker aliases and uncurated short aliases are disabled by default for GDELT matching.

## Optional GDELT metadata dry run

The GDELT prototype is a metadata feasibility step only. It follows the zero-cost route: no Google Cloud, BigQuery, paid API, billing setup, or cloud credentials are required. The dry run prints candidate raw GDELT file URLs and local ignored output paths without downloading files:

```bash
uv run python scripts/probe_gdelt_metadata.py --dry-run --company-alias 台積電 --ticker 2330 --start-date 2025-04-01 --end-date 2025-04-02
```

Any later live GDELT outputs must remain local under ignored `data/raw/news/gdelt/` or `data/processed/news/gdelt/` paths.

The current source-discovery result is documented in `docs/taiwan_hype_index_news_acquisition_feasibility.md`: GDELT raw GKG direct download is the recommended zero-cost route for the next bounded metadata prototype; BigQuery remains rejected for this project.

The first implementation uses an 8-week pilot news window, 2025-04-05 to 2025-05-30, with Saturday-to-Friday weekly bins. The selected GDELT acquisition uses two completed 4-week chunks; the previously planned third chunk is excluded because of a sustained missing raw GKG archive block. See `docs/taiwan_hype_index_news_acquisition_feasibility.md` for the selected chunk commands and local-only output paths.

For a bounded streaming feasibility probe that does not keep raw GDELT files by default:

```bash
uv run python scripts/probe_gdelt_raw_stream.py --start-date 2025-04-01 --end-date 2025-04-01 --max-files 8 --max-download-mb 50
```

Add `--execute` only for an explicit live probe.

After the two selected 8-week pilot chunks exist locally, build the zero-filled stock-week news-count panel with explicit input directories:

```bash
uv run python scripts/build_gdelt_weekly_counts.py \
  --pilot-start-date 2025-04-05 \
  --pilot-end-date 2025-05-30 \
  --universe-file data/processed/tej/top50_universe_20250331.csv \
  --input-dir data/processed/news/gdelt_pilot_8w/chunk_20250405_20250502 \
  --input-dir data/processed/news/gdelt_pilot_8w/chunk_20250503_20250530 \
  --output-dir data/processed/news/gdelt_pilot_8w/weekly_counts
```

If the local chunk directories still live under `data/processed/news/gdelt_pilot_12w/`, keep that parent in the two `--input-dir` paths; the script does not assume a fixed parent directory name.

This aggregation writes local-only count tables. It does not compute a Hype Index or join market-cap weights.
Capped GDELT probe outputs are diagnostics only; aggregation inputs must account
for the uncapped GDELT candidate file grid before zero-filled weeks are valid.

After the Goal 3A news-count panel and TEJ weekly market-cap weights both exist
locally, build the Hype-ready input panel:

```bash
uv run python scripts/build_hype_input_panel.py \
  --pilot-start-date 2025-04-05 \
  --pilot-end-date 2025-05-30 \
  --news-counts-file data/processed/news/gdelt_pilot_8w/weekly_counts/stock_week_news_counts_20250405_20250530.csv \
  --market-weights-file data/processed/tej/weekly_market_cap_weights_20250401_20260331.csv \
  --universe-file data/processed/tej/top50_universe_20250331.csv \
  --output-dir data/processed/hype_index/pilot_8w
```

This join writes local-only Hype-ready inputs under ignored
`data/processed/hype_index/` paths. It joins TEJ weekly market-cap weights and
adds a weekly total news-count diagnostic, but it still does not compute raw
Hype Index or market-cap-adjusted Hype Index values.

After the Hype-ready input panel exists locally, compute the weekly raw Hype and
market-cap-adjusted Hype Index outputs:

```bash
uv run python scripts/build_hype_indices.py \
  --pilot-start-date 2025-04-05 \
  --pilot-end-date 2025-05-30 \
  --input-panel-file data/processed/hype_index/pilot_8w/hype_input_panel_20250405_20250530.csv \
  --output-dir data/processed/hype_index/pilot_8w/indices
```

These outputs remain local-only under ignored `data/processed/hype_index/`
paths. The script writes stock-week Hype Index values and summary diagnostics;
it does not create figures, notebooks, forecasts, or portfolio results.

## Planned direction

The project direction is:

1. a TEJ-based fixed top-50 market-cap universe and documented data-source plan;
2. stock and sector news-count Hype Index construction;
3. market-cap-adjusted Hype Index construction;
4. empirical analysis against events and realized volatility;
5. report-ready documentation of assumptions, risks, and limitations.

Sentiment, forecasting, LLM-assisted Black-Litterman, and portfolio workflows are outside the active first phase.

No live trading, broker integration, or financial advisory functionality is intended.
