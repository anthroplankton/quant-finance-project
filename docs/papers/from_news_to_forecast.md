# 論文筆記：From News to Forecast: Integrating Event Analysis in LLM-Based Time Series Forecasting with Reflection

## 0. Reference

- Paper: `From News to Forecast: Integrating Event Analysis in LLM-Based Time Series Forecasting with Reflection`
- Authors: Xinlei Wang, Maike Feng, Jing Qiu, Jinjin Gu, Junhua Zhao
- Venue / arXiv: arXiv:2409.17515v3; local source uses a NeurIPS 2024 style file
- Code / data if mentioned by the paper: `https://github.com/ameliawong1996/From_News_to_Forecast`
- Local source files inspected: `references/local/arXiv-2409.17515v3/neurips_2024_arxiv.tex`, `references/local/arXiv-2409.17515v3/ref.bib`
- Note status: first-pass reading note revised with local source check; exact dataset construction scripts, full news database contents, and prompt implementation details still `needs verification`

## 1. 核心摘要與 pipeline

這篇論文提出一個 news-aware LLM time-series forecasting pipeline：

```text
raw time series + raw news + supplementary information
        ↓
Information Retrieval
        ↓
candidate news pool
        ↓
Reasoning Agent filters relevant news
        ↓
selected news + rationality
        ↓
Prompt Integration / Data Construction
        ↓
fine-tuned LLM forecasts future time series
        ↓
Evaluation Agent compares prediction errors with all news
        ↓
missed news + updated reasoning logic
        ↓
next iteration
```

核心流程可以概括為：

```text
news retrieval
+ news filtering
+ rationale construction
+ instruction tuning
+ prediction-error reflection
+ iterative news-selection logic update
```

---

## 2. 這篇論文在此專案中的角色

這篇論文對 LLM + Black-Litterman 專案最有價值的地方，是示範 news 在進入 view generation 前應如何被處理。換成此專案的語言，它是 news-aware view-generation layer 最重要的參考之一。selected news + rationality 很自然可以成為後續 View Synthesizer 的輸入。

它可以補上 LLM-Enhanced Black-Litterman 的缺口：LLM-Enhanced Black-Litterman 說明 LLM forecasts 如何轉成 $Q$ 與 $\Omega$；From News to Forecast 說明 news 如何被 retrieve、filter、reason over，並透過 reflection 修正；Nexus 則說明 forecasting reasoning 如何拆成 contextualization、macro/micro reasoning、synthesis 與 calibration。

對此專案而言，這篇論文可以放在 Black-Litterman view generation 前面，作為 news filtering、event reasoning 與 reflection/update layer。它處理的是「哪些新聞值得進入 view generation」以及「預測錯誤後如何修正 news-selection logic」。

這裡要清楚分成三件事：

1. 論文實際做法：用 retrieval、Reasoning Agent、selected news、fine-tuned LLM forecasting、Evaluation Agent reflection 形成 news-aware time-series forecasting workflow。
2. 此專案可借用之處：把它當成 news filtering / event rationale / reflection 的核心設計參考。
3. 此專案仍需自行處理的問題：如何把 selected news 轉成 Black-Litterman 的 $P$、$Q$、$\Omega$，以及如何避免把 reflection confidence 誤當成正式 $\Omega$。

---

## 3. 模型 / pipeline 架構總覽

```text
[Raw Time Series Data]
    - historical target values
    - frequency
    - region
    - forecasting horizon
    - task domain

        ↓

[Information Retrieval Module]
    Inputs:
        - region
        - time range
        - task domain
        - retrieval keywords
        - forecasting horizon

    Retrieves:
        - raw news
        - supplementary information

        ↓

[Candidate News Pool + Supplementary Context]
    Raw news:
        - title
        - summary
        - full article
        - publication time
        - category
        - source link

    Supplementary information:
        - calendar date
        - holiday
        - geography
        - weather
        - economic indicators

        ↓

[Reasoning Agent]
    Inputs:
        - forecasting task
        - candidate news
        - prediction date
        - region
        - current news-selection logic

    Operations:
        - reason about possible effects
        - filter irrelevant news
        - classify selected news by effect horizon
        - attach rationality

    Outputs:
        - long-term effect news
        - short-term effect news
        - rationality for each news item
        - structured JSON

        ↓

[Prompt Integration / Data Construction]
    Inputs:
        - historical time series
        - selected news
        - rationality
        - supplementary information
        - forecasting requirements

    Operation:
        Convert all information into text input-output pairs.

    Output:
        Instruction-tuning dataset

        ↓

[LLM Forecasting Model]
    Inputs:
        - text-form historical time series
        - selected news and rationality
        - supplementary information

    Operation:
        Fine-tune pretrained LLM with supervised instruction tuning and LoRA.

    Output:
        predicted future numerical sequence

        ↓

[Evaluation Agent]
    Inputs:
        - predicted values
        - actual values
        - prediction errors
        - selected news
        - all news before prediction
        - task background

    Operations:
        - identify missed news
        - explain why missed news matters
        - update news-selection logic

    Outputs:
        - missed news
        - updated reasoning logic
        - final refined selection logic after iterations
```

---

## 4. Data layer

### 4.1 Time-series data

這篇論文評估的是外部社會事件可能影響時間序列的任務，例如：

```text
Traffic:
    traffic volume

Exchange:
    exchange rate

Bitcoin:
    Bitcoin price

Electricity:
    Australian electricity demand
```

資料頻率的例子：

```text
daily
hourly
half-hourly
```

若改成此專案的金融情境，對應設定可以寫成：

```text
Target:
    stock return, ETF return, sector return, volatility, or price movement

Frequency:
    daily or weekly

Forecast horizon:
    next day, next week, next two weeks, or next rebalancing period

Region:
    US market, Taiwan market, global market, or sector-specific region
```

---

## 5. Information Retrieval Module

### 5.1 Purpose

Information Retrieval Module（資訊檢索模組）的作用是先收集可能相關的資料。

它還不判斷新聞是否真的有用，只負責建立 candidate news pool。

### 5.2 Sources

這篇論文使用或提到的資料來源包括：

```text
News:
    GDELT
    Yahoo Finance
    News websites
    media sources

Supplementary information:
    OpenWeatherMap
    calendar dates
    holidays
    economic indicators
    GDP
    inflation
    employment statistics
    interest-rate-related data
```

對此專案而言：

```text
Possible financial news sources:
    Yahoo Finance
    SEC filings
    company press releases
    macroeconomic calendar
    FRED
    earnings calendar
    sector news
```

### 5.3 Input schema

```json
{
  "task_domain": "stock_return_forecasting",
  "target_entity": "AAPL",
  "region": "United States",
  "frequency": "daily",
  "forecast_horizon": "next two weeks",
  "lookback_start": "2025-02-17",
  "lookback_end": "2025-03-03",
  "retrieval_keywords": [
    "Apple",
    "AAPL",
    "iPhone demand",
    "technology sector",
    "Federal Reserve",
    "NASDAQ"
  ]
}
```

### 5.4 Output schema

```json
{
  "candidate_news": [
    {
      "title": "Apple faces renewed demand concerns in China",
      "summary": "Analysts reported weaker-than-expected iPhone demand.",
      "publication_time": "2025-02-24T09:30:00",
      "region": "United States / China",
      "category": "company",
      "source": "Yahoo Finance",
      "url": "..."
    },
    {
      "title": "Technology shares rebound after softer inflation data",
      "summary": "Growth stocks rose as bond yields declined.",
      "publication_time": "2025-02-26T14:00:00",
      "region": "United States",
      "category": "macro_market",
      "source": "market_news",
      "url": "..."
    }
  ],
  "supplementary_information": {
    "calendar": {
      "is_holiday": false,
      "weekday": "Monday"
    },
    "macro": {
      "inflation_release": "upcoming",
      "fomc_event": "none"
    }
  }
}
```

---

## 6. Candidate alignment

在進行 news reasoning 之前，candidate news 需要先和 forecasting task 對齊。

這篇論文強調要依照下列資訊對齊：

```text
time frequency
forecasting horizon
geographical area
task domain
```

此專案版本可以寫成：

```text
Align news by:
    - publication date
    - event date
    - asset ticker
    - company
    - sector
    - market
    - macro region
    - forecast horizon
```

範例：

```json
{
  "news_id": "news_001",
  "publication_time": "2025-02-24T09:30:00",
  "event_time": "2025-02-24",
  "affected_assets": ["AAPL"],
  "affected_sector": "Information Technology",
  "affected_market": "NASDAQ",
  "horizon_type": "short_term",
  "available_before_rebalance": true
}
```

關鍵規則：

```text
Only use news available before the forecast cutoff.
```

---

## 7. Reasoning Agent for news filtering

### 7.1 Purpose

Reasoning Agent（推理代理）會從 candidate news pool 中挑出相關新聞。

它不負責預測最終數值，而是產生：

```text
selected news
effect category
rationality
structured JSON
```

重點是 agent 要判斷 causal relevance，而不是只看 keyword overlap。

### 7.2 Initial reasoning logic setting

這篇論文一開始會請 LLM agent 先整理 forecasting task 的 news-selection logic。

概念型 prompt：

```text
Please summarize the logic of selection of news that will change the {forecasting task} in a specific {output format}.
```

此專案可能的輸出範例：

```json
{
  "positive_factors": [
    {
      "factor": "strong earnings guidance",
      "expected_effect": "increase expected stock return",
      "horizon": "short_to_medium_term"
    },
    {
      "factor": "falling interest-rate expectations",
      "expected_effect": "support growth stocks and risk assets",
      "horizon": "market_level_short_term"
    }
  ],
  "negative_factors": [
    {
      "factor": "weaker product demand",
      "expected_effect": "decrease expected stock return",
      "horizon": "company_short_term"
    },
    {
      "factor": "hawkish central bank surprise",
      "expected_effect": "reduce risk appetite and pressure equity valuations",
      "horizon": "market_short_term"
    }
  ]
}
```

### 7.3 News filtering prompt

依照論文架構整理出的概念型 prompt：

```text
If I give you all news, based on the above positive and negative issues analysis of {news selection logic}:

1. Please choose the news that may have a long-term effect on {forecasting task topic}.
2. Please choose the news that may have a short-term effect on {forecasting task topic}.

Requirements:
- Include the region and time information of these news.
- The prediction date is {prediction date}.
- The news happened before and on the prediction date includes: {all news}.
- Only give JSON output.
```

### 7.4 Output schema

```json
{
  "Long-Term Effect News": [
    {
      "news": "Company announced a multi-year AI infrastructure partnership.",
      "region": "United States",
      "time": "2025-02-20T08:00:00",
      "rationality": "The partnership may improve long-term revenue expectations and investor sentiment."
    }
  ],
  "Short-Term Effect News": [
    {
      "news": "Analysts cut near-term iPhone shipment estimates.",
      "region": "United States / China",
      "time": "2025-02-24T09:30:00",
      "rationality": "Lower shipment expectations may pressure near-term returns before the next rebalancing period."
    }
  ]
}
```

### 7.5 Important output field: rationality

`rationality` 是這個流程裡很重要的欄位。

它記錄為什麼這則新聞重要、可能影響 target 的方向、影響是 short-term 還是 long-term，以及受影響的 region 或 entity。

對此專案而言，這個欄位之後可以協助判斷：

- 這則新聞是否影響 $Q$；
- 是否可能提供 $\Omega$ 的輔助訊號；
- 或者只適合作為 qualitative audit evidence。

---

## 8. Prompt Integration / Data Construction

### 8.1 Purpose

selected news 會被轉成 instruction-tuning data。

forecasting model 不會直接接收 raw database rows，而是接收整合下列資訊的 natural-language prompt：

```text
historical time series
forecasting task
frequency
region
prediction date
supplementary information
selected news
rationality
actual future values as output during training
```

### 8.2 Training record structure

```text
Instruction:
    historical numerical sequence

Input:
    task description
    region
    date
    frequency
    historical coverage
    prediction date
    supplementary information
    selected news + rationality

Output:
    actual future numerical sequence
```

### 8.3 Example training record

```text
Instruction:
The historical stock return data is:
-0.34, 0.12, -1.05, 0.48, -0.26, 0.91, -0.18, 0.37, -0.44, 0.20

Input:
Based on the historical return data, please predict the stock return sequence in the next two weeks.

The target ticker is AAPL.
The region for prediction is United States.
The start date of historical data was 2025-02-17.
The data frequency is daily.
Historical data covers 2 weeks.
The date of prediction is 2025-03-03.

Supplementary information:
The next two weeks include no major US market holidays.
The market is waiting for inflation data next week.

On 2025-02-24 09:30:00,
the news "Analysts cut near-term iPhone shipment estimates" can change the time series fluctuation because weaker product demand may reduce short-term investor sentiment.

On 2025-02-26 14:00:00,
the news "Technology shares rebound after softer inflation data" can change the time series fluctuation because lower yield expectations may support growth stocks.

Output:
0.15, -0.22, 0.31, 0.08, -0.10, 0.27, ...
```

在原論文中，supervised fine-tuning 的輸出是實際未來 time-series values。

若改成 Black-Litterman adaptation，輸出可以改成：

```text
future return sequence
or
average return over forecast horizon
or
event-adjusted expected return view
```

---

## 9. LLM forecasting model

### 9.1 Problem framing

這篇論文把 time-series forecasting 視為 conditional language generation。

數值時間序列會被表示成 text tokens。

範例：

```text
123,456
```

可以被 tokenizer 切成：

```text
"1", "2", "3", ",", "4", "5", "6"
```

因此，預測未來數值就變成 next-token prediction。

### 9.2 Conditional probability view

沒有 news 時：

$$
P(x_{t+1} \mid x_{0:t})
$$

加入 news tokens 時：

$$
P(x_{t+1} \mid x_{0:t}, e_{0:u})
$$

加入 supplementary context 時：

$$
P(x_{\text{future}} \mid x_{\text{history}}, e_{0:u}, c)
$$

其中：

```text
x_history:
    historical time series

x_future:
    future time series

e_{0:u}:
    selected news event tokens

c:
    supplementary information, such as weather, calendar, or macro indicators
```

### 9.3 Training method

這篇論文用下列方式 fine-tune pretrained LLM：

```text
supervised instruction tuning
LoRA
text input-output pairs
```

模型學到的是：

```text
historical time series + selected news + supplementary context
        ↓
future numerical sequence
```

### 9.4 Output format

forecasting output 是一段 numerical sequence。

範例：

```json
{
  "predicted_values": [6592.6, 6467.0, 6312.3, 6208.4]
}
```

若改成 stock-return adaptation：

```json
{
  "predicted_returns": [0.0015, -0.0022, 0.0031, 0.0008]
}
```

若改成 Black-Litterman view generation：

```json
{
  "average_expected_return": 0.0012,
  "forecast_horizon": "next_two_weeks"
}
```

---

## 10. Evaluation Agent / Reflection

### 10.1 Purpose

Evaluation Agent（評估代理）會在看到 prediction errors 之後改善 news filtering。

它是在 forecasting model 訓練並評估後才使用。

它會問：

```text
Were there important news events that should have been selected but were missed?
```

### 10.2 Inputs

```json
{
  "forecasting_task": "AAPL next-two-week return forecasting",
  "prediction_date": "2025-03-03",
  "selected_news": [
    {
      "news": "Technology shares rebound after softer inflation data",
      "rationality": "Lower yield expectations may support growth stocks."
    }
  ],
  "all_news_before_prediction": [
    {
      "news": "Analysts cut near-term iPhone shipment estimates",
      "publication_time": "2025-02-24T09:30:00"
    },
    {
      "news": "Technology shares rebound after softer inflation data",
      "publication_time": "2025-02-26T14:00:00"
    }
  ],
  "predicted_values": [0.002, 0.001, 0.003],
  "actual_values": [-0.004, -0.003, -0.001],
  "prediction_errors": [-0.006, -0.004, -0.004]
}
```

### 10.3 Evaluation prompt structure

這篇論文描述的是三階段 evaluation prompt。

#### Phase 1: assess prediction accuracy

```text
Based on historical data and relevant news, I have predicted the future {forecasting time series domain} in {forecasting period}.

Given predicted values, actual values, and the news references, assess the prediction accuracy and analyze whether any important news has been overlooked.

This is {Background Information}.
```

#### Phase 2: identify missed news

```text
Given:
- selected news
- all news
- actual values
- prediction errors

Determine if any news has been missed.
Output the missed news in the required format.
```

#### Phase 3: update prediction logic

```text
According to the missed news for {forecasting period}, directly conclude several new prediction logic rules of {forecasting time series domain}.
```

### 10.4 Output schema

```json
{
  "missed_news": [
    {
      "news": "Analysts cut near-term iPhone shipment estimates",
      "publication_time": "2025-02-24T09:30:00",
      "reason_missed": "The original selection logic underweighted company-specific demand news.",
      "possible_effect": "Negative short-term pressure on AAPL returns."
    }
  ],
  "updated_logic": [
    {
      "rule": "Company-specific demand revisions should be treated as short-term return-relevant news.",
      "direction": "negative if demand is revised downward",
      "horizon": "short_term"
    }
  ]
}
```

---

## 11. Iterative training and refinement loop

完整 training process 是 iterative 的。

```text
Iteration 1
────────────────────────────────
Initial reasoning logic
        ↓
Reasoning Agent selects news
        ↓
Prompt integration
        ↓
LLM fine-tuning
        ↓
Validation prediction
        ↓
Evaluation Agent identifies missed news
        ↓
Updated reasoning logic


Iteration 2
────────────────────────────────
Updated reasoning logic
        ↓
Reasoning Agent reselects news
        ↓
Prompt integration
        ↓
LLM fine-tuning
        ↓
Validation prediction
        ↓
Evaluation Agent updates logic again


Final iteration
────────────────────────────────
Consolidated final reasoning logic
        ↓
Final news selection
        ↓
Final LLM fine-tuning
        ↓
Test prediction
```

final reasoning logic 會在處理 validation-set feedback 後產生。

---

## 12. Agent input/output summary

| Module | Input | Operation | Output |
|---|---|---|---|
| Information Retrieval | domain, region, dates, horizon, keywords | collect candidate news and context | raw news + supplementary information |
| Candidate Alignment | raw news, time-series metadata | align by date, region, horizon, domain | candidate news pool |
| Initial Reasoning Logic | forecasting task | summarize what news should matter | initial selection logic |
| Reasoning Agent | candidate news + logic | filter and classify news | selected news + rationality |
| Prompt Integration | selected news + time series + context | build instruction-tuning records | text input-output pairs |
| LLM Forecasting Model | instruction data | supervised fine-tuning with LoRA | predicted future time series |
| Evaluation Agent | predictions, actuals, errors, all news | detect missed news and update logic | missed news + updated logic |
| Final Training | refined logic | final data construction and fine-tuning | final forecasting model |

---

## 13. Experiment findings

### 13.1 Filtered news helps

這篇論文比較四種 prompt design：only numeric prompt、textual prompt without news、textual prompt with non-filtered news，以及 textual prompt with filtered news。論文回報的整體模式是 filtered news 在多數 tested domains 表現最好，而 non-filtered news 反而可能傷害 performance。

原因：

unfiltered news 會增加過多 tokens，irrelevant news 也可能引入 noise 或錯誤 causal links。這點對此專案很重要，因為 raw unfiltered news 不適合直接丟給 view-generation LLM。

### 13.2 Evaluation agent improves selection logic

這篇論文指出 iterative reflection 可以改善 filtering process。

Reasoning Agent 只看得到 news content，本身不知道 selected news 是否真的幫助 prediction。Evaluation Agent 則能根據 prediction errors 檢查是否有 missed events。

這暗示此專案可以保留一個有用的機制：

```text
backtest errors
        ↓
find missed events
        ↓
update event-selection rules
        ↓
improve future Q generation or Omega calibration
```

### 13.3 Limitations and notes for reuse

local source 檢查確認，這篇論文評估 electricity、exchange、traffic、Bitcoin 等多個 domain，並指出 filtered news 通常比 non-filtered news 更有幫助。它也提到一個實務限制：traffic forecasting 的改善較小，因為可取得的新聞對 road-level traffic behavior 來說太粗。

對此專案而言，這個限制很重要，因為 financial news 也有類似的 granularity problem。market-wide headline、sector headline、asset-specific headline 不應被視為同一種信號。若 selected news 太粗，可能不適合作為個別 asset-level $Q_i$ 的根據。

仍標記為 `needs verification` 的細節：

- local LaTeX source 之外的 exact raw news source / database construction；
- released code 裡的 exact training scripts 與 LoRA settings；
- 同樣的 reflection loop 是否能改成足夠 deterministic、適合此課程專案使用。

---

## 14. Difference from Nexus

| 比較面向 | From News to Forecast | Nexus |
|---|---|---|
| 主要目標 | 建立 news-aware fine-tuning data，並用 reflection 改善 news filtering | 把 LLM forecasting 拆成 contextualization、macro、micro、synthesis、calibration |
| Forecasting model | Fine-tuned LLM | Prompt-based multi-agent LLM framework |
| News handling | explicit retrieval + filtering + rationality | structured historical context 搭配 macro/micro decomposition |
| Reflection | Evaluation Agent 找 missed news 並更新 selection logic | Calibration Agent 從 past errors 產生 synthesis guidelines |
| Output | future numerical time series | future numerical time series + reasoning |
| 對此專案最有用之處 | news selection 與 event-filtering layer | view synthesis architecture |

簡單來說，From News to Forecast 處理「哪些新聞應該進入模型」，Nexus 處理「如何對結構化的 numerical/textual context 做 reasoning」，LLM-Enhanced Black-Litterman 則處理「如何把 views 接到 BL 並產生 portfolio weights」。

---

## 15. 和 LLM-Black-Litterman 專案的關係

### 15.1 原論文直接輸出

原論文輸出的是 future time-series values，例如 future electricity demand、future exchange rate、future Bitcoin price 或 future traffic volume。

### 15.2 此專案需要的輸出

Black-Litterman 需要 picking matrix $P$、view vector $Q$，以及 view uncertainty/confidence matrix $\Omega$。

因此，這篇論文比較適合被改成 pre-BL news-view layer：

```text
Raw financial news
        ↓
Candidate news retrieval
        ↓
Reasoning Agent selects relevant events
        ↓
Selected news + rationality
        ↓
View generation context
        ↓
Forecast/View construction
        ↓
Q and possibly Omega signals
        ↓
Black-Litterman
```

### 15.3 Mapping to $Q$

對每檔股票 $i$：

```text
selected events + historical returns
        ↓
forecasting/view model
        ↓
expected return over horizon
        ↓
Q_i
```

這裡的重點是：raw news 不應直接進入 $Q$ generation。比較合理的輸入是已經過濾、對齊 forecast horizon、並附上 rationality 的 selected news。

範例：

```json
{
  "ticker": "AAPL",
  "forecast_horizon": "next_two_weeks",
  "selected_news": [
    {
      "news": "Analysts cut near-term iPhone shipment estimates.",
      "rationality": "This may reduce short-term investor sentiment."
    }
  ],
  "expected_return": -0.006,
  "black_litterman_mapping": {
    "Q_i": -0.006
  }
}
```

### 15.4 Mapping to $\Omega$

這篇論文沒有直接定義 Black-Litterman $\Omega$。

可能的 adaptation 包括：沿用 LLM-Enhanced Black-Litterman 的 repeated-query variance、使用 news-aware forecasting model 的 historical validation error、把 reflection-agent confidence 當成 heuristic，或結合 repeated-query variance 與 validation error 作為清楚標記的 experimental method。

比較保守的 baseline 是：From News to Forecast 先用在 news selection 與 rationale，$\Omega$ 則先沿用 LLM-Enhanced Black-Litterman 的 repeated-query variance 方法。

此處要特別保守：Reasoning Agent 的 `rationality`、Evaluation Agent 的 missed-news analysis，最多只能先當作 news-selection quality signal，不能直接宣稱是 Black-Litterman $\Omega$。如果未來要把 reflection error 或 missed-news rate 放進 $\Omega$，需要獨立命名，例如 `reflection_calibration_error`，並標成 proposed heuristic / future experiment。

這篇論文的 reflection 對此專案很重要，因為它可以幫忙發現 biased news view 或 missed news view：如果某次 view 明顯錯誤，Evaluation Agent 的 missed-news analysis 可以回頭修正 retrieval / filtering / rationale logic。

---

## 16. Minimal project schemas

### 16.1 Candidate news schema

```json
{
  "news_id": "news_001",
  "title": "Apple faces renewed demand concerns in China",
  "summary": "Analysts reported weaker-than-expected iPhone demand.",
  "publication_time": "2025-02-24T09:30:00",
  "event_time": "2025-02-24",
  "source": "Yahoo Finance",
  "region": "United States / China",
  "candidate_assets": ["AAPL"],
  "candidate_sector": "Information Technology",
  "retrieval_keywords": ["Apple", "iPhone demand", "AAPL"]
}
```

### 16.2 Selected news schema

```json
{
  "news_id": "news_001",
  "selected": true,
  "effect_horizon": "short_term",
  "expected_direction": "negative",
  "affected_assets": ["AAPL"],
  "affected_sector": "Information Technology",
  "rationality": "Weaker iPhone demand may reduce short-term investor sentiment and pressure expected returns.",
  "affects": {
    "Q": true,
    "Omega": true
  }
}
```

### 16.3 Forecasting prompt record

```json
{
  "rebalance_date": "2025-03-03",
  "ticker": "AAPL",
  "historical_returns": [-0.0034, 0.0012, -0.0105, 0.0048],
  "market_returns": [-0.0011, 0.0025, -0.0042, 0.0030],
  "sector_returns": [-0.0020, 0.0031, -0.0067, 0.0044],
  "selected_news": [
    {
      "publication_time": "2025-02-24T09:30:00",
      "summary": "Analysts cut near-term iPhone shipment estimates.",
      "rationality": "This may negatively affect short-term expected return."
    }
  ],
  "forecast_target": "average daily return over next two weeks"
}
```

### 16.4 Reflection output schema

```json
{
  "rebalance_date": "2025-03-03",
  "ticker": "AAPL",
  "prediction_error_summary": {
    "predicted_return": 0.004,
    "actual_return": -0.009,
    "error": -0.013
  },
  "missed_news": [
    {
      "news_id": "news_003",
      "summary": "Supplier data indicated weaker device orders.",
      "reason": "The selection logic missed supply-chain demand indicators."
    }
  ],
  "updated_selection_logic": [
    {
      "rule": "Supplier and channel-check news should be treated as short-term company-demand signals.",
      "expected_direction": "negative when order estimates decline"
    }
  ]
}
```

---

## 17. 實作與報告注意事項

### 17.1 raw news 不適合直接進入 view generation

這篇論文的實驗顯示，non-filtered news 可能讓 forecasting 變差。

較合適的資料流程是先建立 candidate news pool，再經過 filtering 與 rationale 整理，最後才進入 view generation。這樣可以避免把大量未篩選新聞直接塞進 prompt，造成 noise 或錯誤因果解讀。

這篇論文的重點正是：news selection 本身需要 reasoning，也需要用 prediction error 做 reflection。對此專案而言，news-aware workflow 可以先停在 offline fixtures / mocked examples，等 baseline Black-Litterman pipeline 清楚後再接 live news。

應使用 staged workflow：

```text
raw news
    ↓
alignment
    ↓
filtering
    ↓
rationality
    ↓
view construction
```

### 17.2 event date 與 publication date 要分開

在 financial forecasting 情境中：

publication date 代表模型何時能知道這則新聞，event date 則代表事件實際發生或預期發生的時間。兩者不能混在一起，否則很容易造成 look-ahead bias。

避免 look-ahead bias：

```text
If publication_time > rebalance_date:
    cannot use the news for that rebalance.
```

### 17.3 news rationality 不等於 numerical confidence

`rationality` 是 qualitative explanation。

它不會自動等於有效的 Black-Litterman $\Omega$。

如果要把 rationality 當作 confidence 使用，應清楚標成 heuristic。

### 17.4 reflection 可以先從 offline examples 開始

在使用 live APIs 之前，可以先使用 manually curated 或 mocked news examples，搭配 deterministic JSON fixtures 測試 prompt schemas。等資料格式穩定後，再加入 live news retrieval。

---

## 18. 建議實作順序

建議的順序是先完成 BL integration baseline，使用 $P = I$、mocked $Q$ 與 mocked $\Omega$ 確認 posterior return、optimizer、backtest 正常。接著建立 offline news fixtures，例如 `candidate_news.json`、`selected_news.json`、`reflection_examples.json`，再實作 From News to Forecast-style news filtering schema。Reasoning Agent output 可以先 mock，等 view-construction prototype 穩定後，再加入 reflection 與 live workflows。

這個順序先用 deterministic fixtures 固定 news-aware view generation 的資料結構，再逐步接上更完整的新聞與 LLM workflow。

---

## 19. 簡短結論

這篇論文比較適合理解成 news-aware、reflection-based 的 data-construction 與 forecasting framework，也是此專案設計新聞 view layer 的主要參考。

它對此專案最重要的提醒是：news 不應被當成 raw text 直接塞進 prompt，而應先經過 retrieval、alignment、filtering、explanation，再透過 feedback 修正。

對 Black-Litterman 來說，From News to Forecast-style layer 可以產生 selected events 與 rationality；Nexus-style layer 可以組織 macro/micro reasoning；LLM-Enhanced Black-Litterman layer 則提供把 final expected returns 與 uncertainty 轉成 $P$、$Q$、$\Omega$ 的 baseline mapping。

因此，這篇論文適合作為 news filtering、event rationality、prediction-error reflection 與 event-selection logic update 的主要參考。

它的角色是把 raw news 變成 selected news、rationality 與 reflection signals；portfolio weights 則由 Black-Litterman posterior 與 optimizer 產生。
