# Quant Finance Course Project

This repository is for a Quantitative Finance course project.

The active first-phase project direction is a Taiwan-market replication and adaptation of **The Hype Index: an NLP-driven Measure of Market News Attention** (arXiv:2506.06329). The report title may remain Taiwan 50 Hype Index, while the first implementation operationalizes the universe as a TEJ-based fixed top-50 market-cap listed-stock universe selected as of 2025-03-31.

## Current stage

- Course assignments
- Paper reading notes
- Taiwan Hype Index architecture design notes
- Taiwan Hype Index data-source and universe plan
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

## Planned direction

The project direction is:

1. a TEJ-based fixed top-50 market-cap universe and documented data-source plan;
2. stock and sector news-count Hype Index construction;
3. market-cap-adjusted Hype Index construction;
4. empirical analysis against events and realized volatility;
5. report-ready documentation of assumptions, risks, and limitations.

Sentiment, forecasting, LLM-assisted Black-Litterman, and portfolio workflows are outside the active first phase.

No live trading, broker integration, or financial advisory functionality is intended.
