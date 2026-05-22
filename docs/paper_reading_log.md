# Paper Reading Log

這份文件是此專案主要論文的閱讀索引與整合筆記。此專案的暫定主題是 **news-aware LLM view generation for Black-Litterman portfolio optimization**。

核心想法是將新聞、事件與 LLM reasoning 轉成 Black-Litterman 可使用的 views。Black-Litterman 負責整合 market prior 與 views，portfolio optimization 負責產生最終權重；LLM 的角色則是協助產生、解釋與校準 views。

因此，較精確的方向可以寫成「news/event-informed LLM views -> Black-Litterman」。

## 閱讀定位

| Paper | 閱讀狀態 | 在此專案中的角色 | 主要可借用內容 | 詳細筆記 | 目前疑問 |
|---|---|---|---|---|---|
| `LLM-Enhanced Black-Litterman Portfolio Optimization` | first-pass note revised; replication details still need verification | 最接近 Black-Litterman integration 的 baseline。它說明如何把 LLM return forecasts 轉成 $P$、$Q$、$\Omega$，再交給 BL posterior 與 optimizer。 | $P = I$ 的 absolute views、用 repeated forecasts 平均建立 $Q$、用 repeated-output variance 建立 diagonal $\Omega$、two-week rebalancing backtest。 | `docs/papers/llm_enhanced_black_litterman.md` | repeated-output variance 只衡量 self-consistency。若 LLM 穩定但錯誤，$\Omega$ 可能被低估。 |
| `From News to Forecast` | first-pass note revised; exact data/prompt implementation still needs verification | 此專案最重要的 news-processing 參考。它處理 raw news 如何被檢索、篩選、附上 rationality，並用 prediction error 與 missed news 做 reflection。 | news retrieval、candidate news pool、Reasoning Agent、selected news rationality、Evaluation Agent、reflection loop。 | `docs/papers/from_news_to_forecast.md` | selected news 如何轉成 asset-level 或 sector-level views？reflection 應只更新 news-selection logic，還是也可用於 $\Omega$ calibration？ |
| `Nexus` | first-pass note revised; public code/data release still needs verification | agentic view-generation architecture 的參考。它把 forecasting 拆成 contextualization、macro reasoning、micro reasoning、synthesis、calibration。 | Historical Context Agent、Macro/Micro-Reasoning Agents、Forecast Synthesizer、Calibration Agent。 | `docs/papers/nexus_time_series_forecasting.md` | macro/micro outputs 如何映射成 $Q$？是否適合產生 relative views？calibration 是否可作為 $\Omega$ 的輔助訊號？ |

## 三篇論文的分工

`LLM-Enhanced Black-Litterman` 說明 views 如何進入 Black-Litterman，重點是 $P$、$Q$、$\Omega$、$\pi$、$\Sigma$、$\tau$、posterior return 與 optimizer。

`From News to Forecast` 說明 raw news 進入 view generation 前應如何處理，重點是 retrieval、filtering、selected news rationality 與 reflection。

`Nexus` 說明 LLM reasoning layer 可以如何拆成多個 agent，重點是 context、macro reasoning、micro reasoning、synthesis 與 calibration。

簡單來說，From News to Forecast 處理「哪些新聞值得用」，Nexus 處理「如何對新聞與數值資料做分層 reasoning」，LLM-Enhanced Black-Litterman 處理「如何把 LLM views 放進 BL 並產生 portfolio」。

```text
From News to Forecast
    -> news filtering and reflection

Nexus
    -> macro/micro reasoning and synthesis

LLM-Enhanced Black-Litterman
    -> P, Q, Omega and portfolio optimization
```

## 目前的專案主線

```text
Historical prices + market data
        ↓
News/event retrieval and filtering
        ↓
Event rationale and reflection
        ↓
Macro/micro LLM reasoning
        ↓
View Synthesizer
        ↓
P, Q, Omega
        ↓
Black-Litterman posterior return
        ↓
Portfolio optimization
        ↓
Backtest
```

其中 $P$ 是 picking matrix，$Q$ 是 view vector，$\Omega$ 是 view uncertainty matrix。第一階段仍可以先做 fixed 或 mocked views，用來確認 BL 公式、資料切分、optimizer 與 backtest 都正確；後續再把 news-aware view generation 接進同一個框架。

## 實作順序和研究主軸的差別

保守的實作順序可以從 BL math and optimization baseline 開始，再加入 fixed / mocked views、paper-style repeated LLM forecasts、deterministic news-aware examples、filtered news + event rationale，以及 Nexus-style macro/micro synthesis。Live news 或 live LLM workflows 則適合放在資料管線穩定之後。

這個順序是為了降低工程風險。真正的研究問題仍然是新聞與事件如何形成可用的 Black-Litterman views。

## 目前仍待釐清的問題

1. $Q$ 應該直接由 LLM 預測 expected return，還是由 time-series baseline 加上 news adjustment？
2. 新聞 view 應該是 asset-level absolute view、sector-level view，還是 relative view？
3. $\Omega$ 是否只用 repeated-output variance？如果加入 reflection error 或 calibration error，應如何清楚命名？
4. From News to Forecast 的 reflection 應該只更新 news-selection logic，還是也可以影響 confidence？
5. Nexus-style macro/micro reasoning 產生的是 forecast，還是應該轉成 view explanation？
6. 如果課程時間有限，哪些部分需要實作，哪些部分只放在 report/design note？
