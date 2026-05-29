# Taiwan Hype Index Design

## Project Motivation

本專案第一階段將以台灣市場為對象，replicate 並 adapt **The Hype Index: an NLP-driven Measure of Market News Attention**。目標是先建立一個透明、可重現的 market news attention measure。

這個方向適合作為課程專案，因為它同時包含文獻方法、台灣市場資料整理、明確公式與可視化實證分析。核心問題是：在台灣大型權值股中，哪些公司或產業得到的新聞關注度高於其市場規模？這些關注度變化是否能描述重大事件與 realized volatility 的變化？

目前階段不主張 trading performance、predictive power、backtest result 或 portfolio result。第一個 deliverable 是 index-construction design、資料需求與 empirical analysis plan。

## Reference Paper

主要參考文獻是 Zheng Cao、Wanchaloem Wunkaew 與 Helyette Geman 的 **The Hype Index: an NLP-driven Measure of Market News Attention** (arXiv:2506.06329)。

這篇論文的核心想法是用 financial news counts 量化 media attention。它先計算每檔股票或每個產業在新聞中的占比，再用 market capitalization weight 調整，藉此觀察新聞曝光是否相對於經濟規模過高或過低。

本專案第一階段將這個想法從美國大型股情境轉到台灣大型股。這個 adaptation 有研究價值，因為台灣市場具有高權值股集中度、半導體供應鏈特色、中文公司名稱比對問題，以及容易引發市場注意力變化的本地事件。

## Proposed Universe

初始 universe 採用 **Taiwan 50 constituents**。這個範圍足夠聚焦，也符合參考論文以 large-cap equities 建立 attention index 的精神。

Universe table 應包含：

- stock identifier、ticker，以及必要時的 exchange suffix；
- official Chinese company name；
- official English company name；
- common short names、ticker aliases、brand names 或 group names；
- industry 或 sector classification；
- constituent selection date 與來源。

重要設計問題是使用 current Taiwan 50 constituents，還是使用 historical constituents。Current constituents 較適合第一版 descriptive replication；historical constituents 較能降低 survivorship bias，適合後續 predictive tests。

## Proposed Data Inputs

計畫中的 data inputs 包含：

- Taiwan 50 constituents 的 stock identifiers 與 company names；
- industry 或 sector classification；
- 每日或每週的 stock-level news counts；
- market capitalization，或 close price 加 shares outstanding 以重建 market capitalization。

News counts 應綁定 publication date，並記錄 news source。同一篇文章若提到多家公司，必須先定義 counting rule。可選做法包括每個 matched company 各記一次、按公司分攤 fractional count，或只記主要公司。

Market capitalization 需要和 news data 對齊到相同頻率。若使用 close price 乘以 shares outstanding，報告中應記錄 adjusted-price assumptions、corporate action handling 與 missing shares data 的處理方式。

## Core Formulas

令 $U_t$ 為時間 $t$ 的 Taiwan 50 universe，$N_{i,t}$ 為股票 $i$ 在時間 $t$ 的 matched news count。時間單位可以是 daily 或 weekly，但同一組分析內必須一致。

Stock-level news-count Hype Index 定義為：

$$
H_{i,t} = \frac{N_{i,t}}{\sum_{j \in U_t} N_{j,t}}.
$$

這個指標衡量股票 $i$ 在 Taiwan 50 universe 中占有的新聞關注度比例。

對 sector $g$，sector-level Hype Index 定義為：

$$
H_{g,t} = \frac{\sum_{i \in g} N_{i,t}}{\sum_{j \in U_t} N_{j,t}}.
$$

這個指標衡量 sector $g$ 在整體 universe 中占有的新聞關注度比例。

令 $MC_{i,t}$ 為股票 $i$ 的 market capitalization。Stock-level market-cap weight 定義為：

$$
w_{i,t} = \frac{MC_{i,t}}{\sum_{j \in U_t} MC_{j,t}}.
$$

Sector-level market-cap weight 定義為：

$$
w_{g,t} = \frac{\sum_{i \in g} MC_{i,t}}{\sum_{j \in U_t} MC_{j,t}}.
$$

Capitalization-adjusted Hype Index 定義為：

$$
A_{i,t} = \frac{H_{i,t}}{w_{i,t}}.
$$

Sector-level capitalization-adjusted Hype Index 定義為：

$$
A_{g,t} = \frac{H_{g,t}}{w_{g,t}}.
$$

當 $A_{i,t}$ 或 $A_{g,t}$ 大於 1，代表該股票或產業的新聞占比高於其 market-cap weight；小於 1 則代表新聞占比低於其 market-cap weight。這些指標描述的是 attention imbalance，本身不是 trading signal。

後續分析可加入 rolling 或 standardized versions。例如 raw stock-level index 的 rolling z-score 可寫成：

$$
Z^{(k)}_{i,t} = \frac{H_{i,t} - \mu^{(k)}_{i,t}}{\sigma^{(k)}_{i,t}},
$$

其中 $\mu^{(k)}_{i,t}$ 與 $\sigma^{(k)}_{i,t}$ 是長度 $k$ 的 rolling mean 與 rolling standard deviation。同樣的形式也可套用到 $A_{i,t}$、$H_{g,t}$ 與 $A_{g,t}$。

如果 news-share formula 的 denominator 為 0，必須先定義 missing-value rule，再產生結果。

## Planned Empirical Analyses

第一組分析是 raw news attention by stock and sector。它用來觀察 Taiwan 50 中哪些公司或產業最常出現在新聞中，以及 attention 是否集中在少數大型權值股。

第二組分析是 cap-adjusted attention by stock and sector。它比較 news share 與 market-cap weight 的落差，呈現哪些股票或產業相對於其經濟規模得到較高或較低關注。

第三組分析是 event-study plots。針對台股重大事件、產業事件或公司事件，可以畫出事件前後的 raw Hype Index、capitalization-adjusted Hype Index、price movement 與 realized volatility。

第四組分析是 relation with realized volatility。第一版可先做 descriptive contemporaneous plots，等 timing assumptions 清楚後再設計 lagged tests。

第五組分析是 possible later relation with returns。Returns relation 需要更嚴格的 look-ahead control、multiple-testing control 與 validation assumptions，因此應放在 index replication 和 volatility analysis 之後。

## Open Questions and Data Risks

Chinese company-name matching 是主要風險。公司可能以正式名稱、簡稱、品牌名、供應鏈描述或集團名稱出現在新聞中。

Ticker aliases 也需要清楚處理。台灣 ticker 可能有 exchange suffix、無 suffix、或混在中英文新聞文字中。

Duplicate news 會扭曲 counts。轉載、快訊更新、同源新聞與重複標題應有明確去重規則。

Source bias 會影響 attention index。不同新聞來源可能偏向電子業、大型權值股、金融股或政治性事件。

Survivorship bias 會影響 Taiwan 50 constituents。Current constituents 可以用於第一版 descriptive replication；historical constituents 較適合 predictive tests。

使用 current Taiwan 50 constituents 或 historical constituents 的選擇，應在任何 empirical result 之前先寫清楚。

## Project Phases

Phase 1 是 Taiwan Hype Index replication。目標是建立 universe table、news-count process、raw Hype Index、capitalization-adjusted Hype Index 與第一版 descriptive plots。

Phase 2 可在另行確認 scope 後加入 sentiment scores。Sentiment 應和 attention counts 分開儲存與分析，讓 intensity 和 tone 可以被清楚區分。

Phase 3 可在資料品質與時間切分設計穩定後測試 predictive power。這一階段可先檢查 realized volatility，再視需要討論 returns。

目前 active scope 到 Phase 1 為止；Phase 2 和 Phase 3 是後續可能方向，不是本階段的 current reference 或 implementation target。
