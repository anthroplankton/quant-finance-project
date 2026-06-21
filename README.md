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

For a bounded streaming feasibility probe that does not keep raw GDELT files by default:

```bash
uv run python scripts/probe_gdelt_raw_stream.py --start-date 2025-04-01 --end-date 2025-04-01 --max-files 8 --max-download-mb 50
```

Add `--execute` only for an explicit live probe.

## Planned direction

The project direction is:

1. a TEJ-based fixed top-50 market-cap universe and documented data-source plan;
2. stock and sector news-count Hype Index construction;
3. market-cap-adjusted Hype Index construction;
4. empirical analysis against events and realized volatility;
5. report-ready documentation of assumptions, risks, and limitations.

Sentiment, forecasting, LLM-assisted Black-Litterman, and portfolio workflows are outside the active first phase.

No live trading, broker integration, or financial advisory functionality is intended.
