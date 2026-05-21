# Paper Reading Log

This file tracks papers read for the Quantitative Finance course project.

## Reading status

| Paper | Status | Role in project | Notes file | Key questions |
|---|---|---|---|---|
| LLM-Enhanced Black-Litterman Portfolio Optimization | Not started | Main reference for LLM-to-Black-Litterman view construction | `docs/papers/llm_enhanced_black_litterman.md` | How should `Q` and `Omega` be constructed and validated? |
| From News to Forecast | Not started | Reference for news filtering, event rationale, and reflection | `docs/papers/from_news_to_forecast.md` | How can filtered news be converted into portfolio views? |
| Nexus: An Agentic Framework for Time Series Forecasting | Not started | Reference for multi-agent forecasting decomposition | `docs/papers/nexus_time_series_forecasting.md` | Should macro/micro decomposition be used in this project? |

## Current synthesis

- The project architecture is not finalized yet.
- The first goal is to understand the three papers and identify what can realistically be reused.
- Implementation should wait until the baseline architecture is clearer.

## Open questions

1. Should the first baseline replicate the LLM-Black-Litterman paper as closely as possible?
2. Should live news be included in the first implementation phase?
3. Should `Omega` come only from repeated LLM predictions at first?
