# Paper Reading Log

這份文件是目前第一階段的文獻閱讀索引。現階段 active first-phase direction 只基於 **The Hype Index: an NLP-driven Measure of Market News Attention**，目標是將該 paper 的 news-attention index 方法 replication / adaptation 到 Taiwan 50 universe。

## Current Reading Map

| Source | Status | Role in this project | What to borrow | Notes |
|---|---|---|---|---|
| `The Hype Index: an NLP-driven Measure of Market News Attention` (Cao, Wunkaew, Geman; arXiv:2506.06329) | active primary reference; local source inspected | 第一階段唯一 current reference。 | News Count-Based Hype Index、Capitalization Adjusted Hype Index、stock/sector aggregation、event and volatility analysis framing。 | 台灣版本改用 Taiwan 50 constituents，並重新處理中文 company-name matching、ticker aliases、news-source bias 與 constituent history。 |

## Primary Reference: Hype Index

Hype Index paper 的核心想法是把新聞關注度轉成可量化的 market-attention measure。它先用新聞提及次數建立 stock-level 與 sector-level news share，再用 market capitalization weight 調整，觀察新聞曝光是否相對於經濟規模過高或過低。

本專案複製的是指標邏輯，並將市場範圍改為台灣大型股：

```text
financial news
    -> company / sector matching
    -> news counts
    -> raw news attention share
    -> market-cap-adjusted attention
    -> event, volatility, and later prediction analysis
```

台灣市場版本的第一步是把 S&P 100 universe 改成 Taiwan 50 constituents。這個改動有明確研究價值：Taiwan 50 提供大型權值股範圍，台灣新聞有中文 entity matching 與產業集中度問題，且台股事件與電子業供應鏈新聞常有高度市場關注。

## Archived Prior Direction

Repository 中既有的 Black-Litterman、LLM view generation、news forecasting 與 Nexus-style notes 屬於 archived prior direction。它們保留作為過去閱讀紀錄與專案轉向前的設計脈絡，不是目前第一階段的 current reference material。

目前第一階段不採用 Self-Driving Portfolio paper、copied X thread、LLM-BL 架構或 multi-agent workflow 作為設計基礎。若未來要重新引入這些材料，應另開 scope，並在報告中明確說明它們與 Hype Index replication 的關係。

## Current Questions

1. Taiwan 50 universe 要使用 current constituents，還是建立 historical constituent table？
2. 中文新聞中的公司名、簡稱、品牌名、集團名和 ticker aliases 如何建立 matching rules？
3. 同一篇新聞提到多家公司時，news count 要重複計入還是分攤？
4. Hype Index 與 capitalization-adjusted Hype Index 應先用 daily 還是 weekly frequency？
5. Realized volatility relation 應使用 contemporaneous comparison，還是先設計 lagged predictive tests？
6. Sentiment scores 若在後續階段加入，應如何與目前的 pure attention index 分開記錄？
