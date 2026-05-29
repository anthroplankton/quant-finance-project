# Progress Log

## 2026-05-29

### Data-source and universe design

* Added a Phase 1 data-source and universe plan for Taiwan Hype Index replication.
* Clarified that Phase 1 uses current Taiwan 50 constituents as a fixed large-cap universe for descriptive replication.
* Documented planned schemas for the universe table, news table, and market data table, plus alias matching, counting rules, frequency choice, and missing-data rules.
* This was a documentation-only design step. No data was downloaded, no Python code was implemented, and no empirical results were produced.

### Project pivot to Taiwan Hype Index

* Instructor suggested moving the project toward market sentiment / market attention.
* Current first-phase plan is specifically a Taiwan-market replication and adaptation of `The Hype Index: an NLP-driven Measure of Market News Attention` (arXiv:2506.06329).
* The proposed initial universe is Taiwan 50 constituents, with raw news-count Hype Index and market-cap-adjusted Hype Index as the first deliverables.
* Current scope is based on the Hype Index paper only; broader LLM, agentic, or portfolio papers are not part of the active first-phase direction.
* This is a documentation and design pivot only. No data pipeline, experiment, backtest, prediction test, LLM run, or portfolio result has been executed yet.
* Next steps are data-source selection, Taiwan 50 universe construction, company-name and ticker-alias matching design, and news-count pipeline design.

## 2026-05-22

### Documentation framing revision

* 將 reading log 與 architecture notes 的主軸調整為 news-aware LLM view generation for Black-Litterman portfolio optimization。
* 釐清 BL baseline 是工程驗證步驟，news/event-informed view generation 才是主要 modeling direction。
* 這次只屬於 documentation/design framing revision；沒有執行 code、backtest、LLM experiment 或 portfolio result。

### Human-facing documentation polish

* 將部分 Markdown 從 agent-instruction style 改成較適合課程報告閱讀的 project notes。
* 清理 fenced code/text blocks 中不會 render 的 LaTeX notation，改在一般 Markdown prose 使用 `$P$`、`$Q$`、`$\Omega$` 等符號。
* 這次仍然只屬於 documentation polish；沒有執行實作、backtest、LLM call 或投資組合實驗。

### Documentation cleanup

* 將 paper-reading notes 與 architecture synthesis 改成較清楚的 Taiwan Traditional Chinese wording，同時保留 English technical terms、formulas、schemas 與 prompt sketches。
* 參考 `references/local/` 底下的 local-only paper source folders，用來確認 metadata 與 architecture details。
* 這次只屬於 documentation cleanup；沒有執行 code、backtest、LLM experiment 或 portfolio result。

### Done

* Created the initial course/research documentation scaffold.
* Added placeholders for paper reading, architecture notes, and progress tracking.

### Stage recorded on 2026-05-22

* Repository 仍在 course/research scaffolding stage。
* Model architecture 尚未 finalized。
* 目前文件主軸已調整為 news-aware LLM views 進入 Black-Litterman；下一步是把設計收斂成可實作的 offline baseline 與 mocked/news-aware view examples。

### Next steps recorded on 2026-05-22

1. 整理 BL baseline 的 data split、return scale、$\pi$、$\Sigma$、$P$、$Q$、$\Omega$ 與 optimizer assumptions。
2. 建立 fixed / mocked views 的 deterministic example。
3. 設計 selected news + rationality 的 offline fixture。
4. 評估 Nexus-style macro/micro synthesis 是否放入實作，或先作為 report/design extension。
