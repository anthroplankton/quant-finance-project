# Architecture Notes

這份文件整理目前的模型設計方向。個別論文摘要放在 `docs/papers/`；這裡主要說明三篇論文如何合成一個可實作、也適合寫進課程報告的專案架構。

## 1. 專案主軸

此專案的主軸是 **news-aware LLM view generation for Black-Litterman portfolio optimization**。

這個專案研究如何把新聞、事件與 LLM reasoning 轉成 Black-Litterman 可使用的 views。Black-Litterman 在這裡扮演 portfolio integration framework，負責把 market prior 與 views 整合成 posterior return；portfolio optimization 再根據 posterior return 產生最終權重。LLM 的角色是輔助 view generation、rationale 與 uncertainty signals，最終權重則由 Black-Litterman posterior 與 optimizer 產生。

因此，較精確的研究方向可以寫成「news/event-informed LLM views -> Black-Litterman」。

## 2. 整體設計想法

目前暫定的資料流如下：

```text
Historical prices / returns
        ↓
Market prior and covariance estimation
        ├── pi
        └── Sigma

News and event data
        ↓
Information Retrieval
        ↓
Candidate news pool
        ↓
Reasoning Agent / news filtering
        ↓
Selected news + rationality
        ↓
Contextualization
        ↓
Macro-Reasoning Agent
        ↓
Micro-Reasoning Agent
        ↓
View Synthesizer
        ├── P
        ├── Q
        └── Omega or named uncertainty signals
        ↓
Black-Litterman posterior return mu_BL
        ↓
Mean-variance optimization
        ↓
Portfolio weights
        ↓
Backtest
```

圖中的 $P$ 是 picking matrix，$Q$ 是 view vector，$\Omega$ 是 view uncertainty matrix。Market prior 由 $\pi$ 表示，資產報酬的 covariance matrix 由 $\Sigma$ 表示，$\tau$ 則用來調整 prior 與 views 的相對信心。Black-Litterman posterior return 記為 $\mu_{BL}$。

這張圖呈現的是完整設計方向。早期可以使用 deterministic fixtures 或 mocked views 來測試資料格式、公式與 backtest 流程；後續再逐步接上 live news 或 live LLM。整體資料流仍以 news-aware view generation 為目標。

## 3. 三篇論文的分工

`LLM-Enhanced Black-Litterman Portfolio Optimization` 解決的是 views 如何進入 Black-Litterman。它示範如何把 repeated LLM forecasts 轉成 $Q$，用 repeated-output variance 建立 diagonal $\Omega$，並讓最終權重仍由 Black-Litterman posterior 與 optimizer 決定。這篇論文很適合作為 BL integration baseline，但它沒有完整處理新聞檢索、新聞篩選或事件推理。

`From News to Forecast` 補上的是 news-processing layer。它的流程是先建立 candidate news pool，再由 Reasoning Agent 篩選 relevant news、記錄 rationality，最後用 Evaluation Agent 根據 prediction error 與 missed news 反思 selection logic。這篇論文對此專案的「新聞 view」主軸特別重要。

`Nexus` 則提供 agentic reasoning architecture。它把 forecasting 拆成 Historical Context Agent、Macro-Reasoning Agent、Micro-Reasoning Agent、Forecast Synthesizer 與 Calibration Agent。Nexus 原文屬於 time-series forecasting framework；在此專案中，它比較適合作為 view-generation layer 的架構參考，後續仍需另外定義 $P$、$Q$ 與 $\Omega$ 的 mapping。

三篇論文可以這樣理解：From News to Forecast 處理「哪些新聞值得用」，Nexus 處理「如何對新聞與數值資料做分層 reasoning」，LLM-Enhanced Black-Litterman 處理「如何把 LLM views 放進 Black-Litterman 並產生 portfolio」。

```text
From News to Forecast
    -> news retrieval, filtering, rationality, reflection

Nexus
    -> context, macro reasoning, micro reasoning, synthesis, calibration

LLM-Enhanced Black-Litterman
    -> P, Q, Omega mapping, BL posterior, portfolio optimization
```

## 4. View Generation 的設計

$Q$ 是 Black-Litterman 的 view vector，也是此專案中 LLM layer 最直接影響 portfolio 的地方。目前可以分成三個層級來思考。

第一層是 baseline $Q$。這一層可以先使用 fixed 或 mocked values，目的是確認 BL posterior、optimizer、constraints 與 backtest 能正常運作。

第二層是 paper-style LLM $Q$，也就是仿照 LLM-Enhanced Black-Litterman，對同一檔資產重複查詢 LLM，然後把 forecasts 平均成 view：

$$
q_i = \frac{1}{N}\sum_{j=1}^{N} r_{i,j}.
$$

其中 $r_{i,j}$ 是第 $i$ 檔資產第 $j$ 次 LLM forecast。

第三層才是最符合此專案主軸的 news-aware $Q$。這一層會把 selected news、rationality、macro reasoning 與 micro reasoning 整合成 expected return view。仍待比較的設計包括：$Q$ 是否應直接由 LLM 輸出 expected return，或是先建立 time-series baseline forecast，再由 news/event information 產生 adjustment。

## 5. 對 $\Omega$ 的疑慮：穩定輸出不等於正確信心

LLM-Enhanced Black-Litterman 使用 repeated-output variance 建立 $\Omega$。這個方法可以作為 baseline，但它衡量的是 LLM output self-consistency，不一定代表 factual reliability。

如果 LLM 對某個錯誤 view 很穩定，repeated forecasts 的 variance 會很小，$\Omega$ 也會變小。這種情況下，$\Omega$ 反映的是輸出穩定度；view 的真實可靠性還取決於新聞選擇是否完整、事件解讀是否合理，以及下列因素：

- 新聞是否 relevant；
- 是否有重要 missed news；
- event direction 是否判斷正確；
- macro reasoning 與 micro reasoning 是否一致；
- 過去類似事件的 forecast error 是否偏大。

因此，$\Omega$ 的來源應分開命名與討論，例如 `repeated_output_variance`、`historical_calibration_error`、`news_selection_quality_signal`、`event_uncertainty_signal` 或 `omega_hybrid_experimental`。在尚未驗證前，這些訊號比較適合被視為不同的 uncertainty sources，而不是被直接混成單一正式公式。

## 6. $P$ 的可能設計

第一版可以使用 $P = I$，也就是每檔股票各有一個 asset-level absolute view。這和 LLM-Enhanced Black-Litterman 的做法一致，也最容易檢查 BL posterior 與 optimizer 是否正確。

引入新聞後，$P$ 可能會變得更複雜。例如 asset-level news 仍可使用 one-hot row；sector-level news 可能需要一個 sector basket；macro news 可能同時影響多個 sector；relative view 則可能表達成「Technology sector outperform Energy sector」這類形式。

後續若使用 non-identity $P$，需要清楚記錄 view 是 absolute 還是 relative、對應哪些 assets、row weight 如何設定、$Q$ 的單位與 forecast horizon，以及它是否和 $\pi$、$\Sigma$ 的 scale 一致。

## 7. 實作階段

實作可以保守推進，但研究主軸仍然是 news-aware view generation。

第一階段是建立 BL baseline。這一階段使用 fixed 或 mocked $P$、$Q$、$\Omega$，確認 posterior return、MVO、constraints、rebalancing 與 backtest 設定都能正常運作。

第二階段是加入 paper-style LLM views。這一階段仿照 LLM-Enhanced Black-Litterman，用 repeated forecasts 建立 $Q$ 與 $\Omega$，先不加入新聞，以便確認 LLM-to-BL mapping。

第三階段是建立 deterministic news-view examples。這一階段使用手動整理或 mocked news examples，建立 candidate news、selected news、rationality 與 view output schema。

第四階段是加入 news filtering 與 reflection。這一階段借用 From News to Forecast 的設計，把 selected news 轉成 asset-level 或 sector-level views，並用 prediction error 或 missed news 反思 news-selection logic。

第五階段視時間加入 Nexus-style macro/micro synthesis。這一階段可比較直接 LLM $Q$ 與 agentic $Q$ 的差異，也可討論 calibration 是否能作為 $\Omega$ 的輔助訊號。

Live news 與 live LLM workflows 適合作為後續延伸，前提是資料、prompt、成本與 reproducibility 都能被清楚控制。

## 8. 報告撰寫角度

報告撰寫時，應避免把主軸描述成「先做 BL baseline，之後有空再加新聞」。較合理的說法是：新聞 view 是研究主軸，而 baseline 是為了讓後續 news-aware view 有可測試的 Black-Litterman 框架。

目前可採用的表述是：此專案先以 Black-Litterman 作為可解釋的 portfolio integration framework，並研究如何將 LLM 從新聞與事件中形成的 views 轉成 $P$、$Q$、$\Omega$。初期會先建立 BL baseline 與 mocked views，確保 posterior return 與 optimizer 正確；接著才加入 news filtering、event rationale、macro/micro reasoning 與 calibration。

## 9. 目前仍待釐清的問題

1. 如何從 selected news 和 rationality 生成 asset-level 或 sector-level $Q$？
2. $Q$ 應該是直接 expected return，還是 time-series forecast 加上 news adjustment？
3. sector-level 或 macro-level news 是否需要 non-identity $P$？
4. $\Omega$ 應如何同時反映 repeated-output uncertainty、news-selection quality 與 historical calibration error？
5. From News to Forecast 的 reflection 應只更新 news-selection logic，還是也能影響 uncertainty？
6. Nexus-style macro/micro synthesis 是否值得在課程專案中實作，還是先作為 report/design extension？
7. 如何避免 look-ahead bias，特別是 publication time、event time、rebalance date 的關係？
8. 如何在報告中區分 paper method、project adaptation、future experiment？
