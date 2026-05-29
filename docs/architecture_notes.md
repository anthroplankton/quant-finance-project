# Architecture Notes

這份文件整理目前第一階段的專案架構。現階段只基於 **The Hype Index: an NLP-driven Measure of Market News Attention**，主軸是把該 paper 的 news-attention index 方法 replication / adaptation 到 Taiwan 50 universe。

## 1. Active First-Phase Architecture

目前的 active first implementation 是：

```text
news/headlines
    -> entity matching
    -> news counts
    -> raw Hype Index
    -> market-cap-adjusted Hype Index
    -> empirical analysis
```

這個流程的核心是把非結構化新聞轉成可檢查的 attention time series。第一階段的架構只涵蓋 Hype Index replication：新聞來源、公司名稱比對、ticker alias、產業分類、market cap 權重與時間對齊方式都需要能被重現。

## 2. Research Question

新的第一階段問題可以表述為：

> 台灣大型權值股的新聞曝光是否和其經濟規模成比例？若不成比例，這種 raw attention 與 market-cap-adjusted attention 是否能描述事件、產業關注度與 realized volatility 的變化？

這個問題適合課程專案，因為它同時包含文獻 replication、在地市場 adaptation、資料清理、可解釋公式與後續 empirical testing。Taiwan 50 constituents 可作為初始 large-cap universe，讓新聞比對與 market cap 權重先在一個範圍清楚的資產池內完成。

## 3. Data Flow

第一階段資料流分成四個層次。

第一層是 universe table。每一檔股票需要 ticker、中文公司名、英文公司名、常見別名與產業分類。Taiwan 50 constituents 是初始範圍；後續必須決定使用 current constituents 還是 historical constituents。

第二層是 news matching。新聞標題或內文需要和公司名稱、ticker、別名、集團名稱或常見縮寫對齊。中文新聞會遇到公司簡稱、品牌名、同名詞、半導體供應鏈描述與市場整體新聞等問題，因此 entity matching 的規則應先以可解釋方式記錄。

第三層是 attention indices。對每個日期或週期，先計算 stock-level news counts，再聚合到 sector-level news counts。接著計算 raw Hype Index 與 market-cap-adjusted Hype Index。

第四層是 empirical analysis。先做描述統計與圖形，再檢查事件期間、realized volatility，以及後續可能的 returns relation。第一階段不設計 portfolio application。

## 4. Index Construction

令 $U_t$ 為時間 $t$ 的 Taiwan 50 universe，$N_{i,t}$ 為股票 $i$ 在時間 $t$ 的新聞數，$MC_{i,t}$ 為市場價值。若 market cap 無法直接取得，可在資料來源允許時用 adjusted close price 乘以 shares outstanding 建立近似值，並在報告中記錄來源與限制。

Stock-level raw Hype Index:

$$
H_{i,t} = \frac{N_{i,t}}{\sum_{j \in U_t} N_{j,t}}.
$$

Sector-level raw Hype Index:

$$
H_{g,t} = \frac{\sum_{i \in g} N_{i,t}}{\sum_{j \in U_t} N_{j,t}} = \sum_{i \in g} H_{i,t}.
$$

Market-cap weight:

$$
w_{i,t} = \frac{MC_{i,t}}{\sum_{j \in U_t} MC_{j,t}}.
$$

Sector market-cap weight:

$$
w_{g,t} = \frac{\sum_{i \in g} MC_{i,t}}{\sum_{j \in U_t} MC_{j,t}}.
$$

Capitalization-adjusted Hype Index:

$$
A_{i,t} = \frac{H_{i,t}}{w_{i,t}}, \qquad
A_{g,t} = \frac{H_{g,t}}{w_{g,t}}.
$$

當 $A_{i,t}$ 或 $A_{g,t}$ 大於 1 時，代表該股票或產業的新聞占比高於其 market-cap weight；小於 1 時，代表新聞占比低於其 economic weight。這是 attention imbalance 的描述性指標，不應直接解讀為投資建議或已驗證的預測訊號。

後續可加入 rolling mean、rolling change、percentage change 或 z-score：

$$
Z^{(k)}_{i,t} = \frac{H_{i,t} - \mu^{(k)}_{i,t}}{\sigma^{(k)}_{i,t}},
$$

其中 $\mu^{(k)}_{i,t}$ 與 $\sigma^{(k)}_{i,t}$ 分別是長度 $k$ 的 rolling mean 與 rolling standard deviation。相同形式也可套用在 $A_{i,t}$、$H_{g,t}$ 與 $A_{g,t}$。

## 5. Empirical Analysis Plan

第一組分析是 raw news attention。它比較不同股票與產業的新聞占比，回答哪些公司或產業最常出現在新聞中，以及 attention 是否集中在少數大型權值股。

第二組分析是 cap-adjusted attention。它比較新聞占比與 market-cap weight 的落差，回答哪些股票或產業相對於其經濟規模被過度關注或低度關注。

第三組分析是 event-study plots。針對台股重大事件、產業事件或公司事件，畫出事件前後的 raw Hype Index、cap-adjusted Hype Index、價格與 realized volatility。這一階段只描述事件對 attention 指標的對應關係，不宣稱因果。

第四組分析是 realized volatility relation。可用 5-day、10-day 或 weekly realized volatility 與 Hype Index 變化做 contemporaneous 與 lagged comparison。這是 Phase 1 後段或 Phase 3 的銜接點。

第五組分析才是 possible returns relation。returns relation 需要更嚴格的時間切分、transaction assumptions 與 multiple-testing control，因此應放在後續階段。

## 6. Current Phase Boundary

目前第一階段只做 Hype Index replication。Sentiment scores、forecasting tests、Black-Litterman、LLM-assisted views、agentic portfolio systems 與 multi-agent workflows 都在 current phase 之外。

後續若加入 sentiment 或 prediction，應另行定義資料來源、時間切分、target variable 與 validation design。這些後續工作不改變本文件目前的 active architecture。

## 7. Open Questions

1. Taiwan 50 應使用 current constituents，還是應取得 historical constituents 以降低 survivorship bias？
2. 中文公司名、英文名、簡稱、品牌名與 ticker aliases 如何建立可重現的 matching table？
3. 同一篇新聞提到多家公司時，應每家公司各記一次，還是按文章權重分攤？
4. 重複新聞、轉載新聞、快訊更新與同源新聞應如何去重？
5. 新聞來源是否偏向特定產業、大型公司或熱門題材？
6. 產業分類應使用交易所分類、GICS 類似分類，還是手動建立的研究分類？
7. market cap 資料若缺少 shares outstanding 或調整因子，應如何記錄近似方法？
8. 實證圖表應先用 daily frequency 還是 weekly frequency？
9. 後續若加入 sentiment 或 returns prediction，如何避免把未來新聞或事後事件標籤放入特徵？
