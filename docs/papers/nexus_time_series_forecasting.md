# 論文筆記：Nexus: An Agentic Framework for Time Series Forecasting

## 0. Reference

- Paper: `Nexus: An Agentic Framework for Time Series Forecasting`
- Authors: Sarkar Snigdha Sarathi Das, Palash Goyal, Mihir Parmar, Nanyun Peng, Vishy Tirumalashetty, Chun-Liang Li, Rui Zhang, Jinsung Yoon, Tomas Pfister
- Venue / arXiv: arXiv:2605.14389v1
- Code / data if mentioned by the paper: `needs verification`; local source inspected here did not show a clear public code/data URL
- Local source files inspected: `references/local/arXiv-2605.14389v1/nexus.tex`, `references/local/arXiv-2605.14389v1/files/abstract.tex`, `files/problem_formulation.tex`, `files/methodology.tex`, `files/experiments.tex`, `files/limitations.tex`, and prompt examples in `files/appendix.tex`
- Note status: first-pass reading note revised with local source check; exact public release status and full data-access workflow still `needs verification`

## 1. 核心摘要與 pipeline

Nexus 是一個 LLM multi-agent time-series forecasting framework。它不讓單一 LLM 直接吃完整的「歷史數值 + 新聞文字」後一次輸出 forecast，而是把預測拆成：

```text
raw numerical history + textual context
        ↓
Historical Context Agent
        ↓
structured causal timeline
        ↓
Macro-Reasoning Agent + Micro-Reasoning Agent
        ↓
macro outlook + micro outlook
        ↓
Forecast Synthesizer Agent
        ↓
final numerical forecast + reasoning
        ↓
Calibration Agent
        ↓
guidelines for future synthesis
```

核心概念：

```text
Nexus = contextualization + macro reasoning + micro reasoning + synthesis + calibration
```

它的主要貢獻是重新組織 LLM forecasting 的 reasoning workflow，而不是提出新的 Transformer time-series model。

---

## 2. 這篇論文在此專案中的角色

這篇論文對此專案的價值不在於 Black-Litterman 公式，而在於它提供一個更合理的 agentic view synthesis 架構。它特別適合放在 news 已經被 From News to Forecast-style filtering 整理之後，用來做 macro/micro reasoning 與 synthesis。

對 LLM + Black-Litterman 專案而言，Nexus 可以啟發：

```text
Historical prices + textual events
        ↓
Historical Context Agent
        ↓
Macro Market/Sector View Agent
        ↓
Micro Asset-Level View Agent
        ↓
View Synthesizer
        ↓
P, Q, Omega
        ↓
Black-Litterman posterior
        ↓
Portfolio optimization
```

Nexus 原文輸出的是 future time series forecast $X_{\tau+1:\tau+T}$ 與 reasoning $R$；Black-Litterman 專案需要的是 $P$、$Q$、$\Omega$。因此，在此專案中使用 Nexus-style agents 時，重點是借用它的 view-generation 架構，再另外定義 $P$、$Q$、$\Omega$ 的 mapping。

這裡要清楚分成三件事：

1. 論文實際做法：把 multimodal time-series forecasting 拆成 contextualization、macro reasoning、micro reasoning、forecast synthesis、calibration。
2. 此專案可借用之處：把它當成 view-generation layer 的架構參考，尤其是 macro/micro decomposition。macro reasoning 可支援 market/sector views，micro reasoning 可支援 asset-level views。
3. 此專案仍需自行處理的問題：如何把 Nexus-style forecast 映射成 Black-Litterman 的 $P$、$Q$、$\Omega$，以及如何避免 agent reasoning 直接變成 portfolio weights。

---

## 3. Problem formulation

Nexus 將 multimodal time-series forecasting 定義為：

```text
Input:
    X_{1:τ}: historical numerical time series
    E_{1:τ}: associated textual context/events

Output:
    X_{τ+1:τ+T}: future numerical forecast
    R: natural-language reasoning trace
```

形式化 mapping：

$$
F(X_{1:\tau}, E_{1:\tau})
\to
(X_{\tau+1:\tau+T}, R).
$$

其中：

$$
X_{1:\tau} = (x_1, x_2, \ldots, x_\tau)
$$

是歷史數值序列。

$$
E_{1:\tau} = (e_1, e_2, \ldots, e_\tau)
$$

是每個 timestep 附近的文字脈絡，例如：

```text
news
financial reports
macroeconomic summaries
corporate events
market commentary
```

預測目標是：

$$
X_{\tau+1:\tau+T}
=
(x_{\tau+1}, x_{\tau+2}, \ldots, x_{\tau+T}).
$$

同時輸出 reasoning：

$$
R_{\tau+1:\tau+T}
=
(r_{\tau+1}, r_{\tau+2}, \ldots, r_{\tau+T}).
$$

也就是每一期 forecast 不只要有數值，也要有解釋。

---

## 4. Full architecture

```text
Input
│
├── Historical Numerical Data
│   X_{1:τ} = (x_1, x_2, ..., x_τ)
│
├── Textual Context / Events
│   E_{1:τ} = (e_1, e_2, ..., e_τ)
│   examples:
│   - news
│   - financial reports
│   - macroeconomic summaries
│   - corporate events
│
└── Basic Time-Series Features
    examples:
    - trend
    - seasonality
    - volatility
    - momentum
    - local fluctuations

        ↓

Stage 1: Contextualization
────────────────────────────────────────
Historical Context Agent A_ctx
│
│  Input:
│      X_{1:τ}, E_{1:τ}, basic time-series features
│
│  Operation:
│      clean, filter, summarize, and align numerical values
│      with relevant textual drivers
│
│  Output:
│      H_{1:τ}: structured historical context
│
│  形式化 mapping：
│      A_ctx(X_{1:τ}, E_{1:τ}) → H_{1:τ}

        ↓

Stage 2: Dual-Resolution Forecast Outlook Generation
────────────────────────────────────────
Macro-Reasoning Agent A_macro
│
│  Input:
│      H_{1:τ}
│
│  Operation:
│      infer broad trend, regime, long-horizon trajectory
│
│  Output:
│      X^macro_{τ+1:τ+T}, R^macro
│
│  形式化 mapping：
│      A_macro(H_{1:τ})
│      → (X^macro_{τ+1:τ+T}, R^macro)

Micro-Reasoning Agent A_micro
│
│  Input:
│      H_{1:τ}
│
│  Operation:
│      forecast step-by-step short-term movement,
│      local volatility, and immediate catalysts
│
│  Output:
│      X^micro_{τ+1:τ+T}, R^micro_{τ+1:τ+T}
│
│  形式化 mapping：
│      A_micro(H_{1:τ})
│      → (X^micro_{τ+1:τ+T}, R^micro_{τ+1:τ+T})

        ↓

Stage 3: Forecast Synthesis and Calibration
────────────────────────────────────────
Forecast Synthesizer Agent A_syn
│
│  Input:
│      H_{1:τ}
│      X^macro, R^macro
│      X^micro, R^micro
│      calibration guidelines G
│
│  Operation:
│      synthesize macro and micro outlooks,
│      resolve conflicts,
│      calibrate numerical magnitude
│
│  Output:
│      final forecast X_{τ+1:τ+T}
│      final reasoning R
│
│  形式化 mapping：
│      A_syn(
│          H_{1:τ},
│          X^macro,
│          R^macro,
│          X^micro,
│          R^micro,
│          G
│      )
│      → (X_{τ+1:τ+T}, R)

Calibration Agent A_calib
│
│  Input:
│      previous predictions
│      ground truth
│      prediction errors
│      reasoning traces
│
│  Operation:
│      analyze past errors and generate robust guidelines
│
│  Output:
│      G: calibration guidelines
```

---

## 5. Data layer

### 5.1 Input data types

Nexus 主要考慮兩種 input streams。

### Numerical stream

```json
{
  "entity": "AAPL",
  "frequency": "weekly",
  "context_length": "1 year",
  "historical_values": [
    {"date": "2025-02-07", "value": 227.63},
    {"date": "2025-02-14", "value": 244.60},
    {"date": "2025-02-21", "value": 245.55}
  ]
}
```

### Textual stream

```json
{
  "entity": "AAPL",
  "events": [
    {
      "date": "2025-02-10",
      "text": "Apple supplier concerns increased after weaker iPhone demand commentary."
    },
    {
      "date": "2025-02-13",
      "text": "Broader technology sector rallied after easing rate expectations."
    }
  ]
}
```

### Combined multimodal context

$$
C_{1:\tau} = (X_{1:\tau}, E_{1:\tau}).
$$

範例：

```json
{
  "target_entity": "AAPL",
  "frequency": "weekly",
  "forecast_horizon": 6,
  "numerical_history": [
    {"t": "2025-W01", "value": 243.85},
    {"t": "2025-W02", "value": 236.85},
    {"t": "2025-W03", "value": 229.98}
  ],
  "textual_context": [
    {
      "t": "2025-W01",
      "event": "Technology sector weakened after higher bond yields."
    },
    {
      "t": "2025-W02",
      "event": "Apple faced concerns about demand in China."
    },
    {
      "t": "2025-W03",
      "event": "Market sentiment stabilized after inflation data."
    }
  ]
}
```

---

## 6. Stage 1: Historical Context Agent

### 6.1 Purpose

Historical Context Agent 會在正式 forecasting 前使用。

它的工作是把 messy multimodal context 轉成 structured causal timeline，讓後續 agent 可以在較清楚的脈絡上推理。

它要處理的問題是：

```text
Raw numerical sequence + raw text is too long and noisy.
A single LLM may lose track of important causal signals.
Therefore, Nexus first compresses and organizes the past.
```

形式化 mapping：

$$
A_{\text{ctx}}(X_{1:\tau}, E_{1:\tau}) \to H_{1:\tau}.
$$

### 6.2 Input

```json
{
  "entity": "AAPL",
  "historical_values": [
    {"timestamp": "2025-W01", "value": 243.85},
    {"timestamp": "2025-W02", "value": 236.85},
    {"timestamp": "2025-W03", "value": 229.98}
  ],
  "events": [
    {
      "timestamp": "2025-W01",
      "text": "Technology stocks declined as Treasury yields rose."
    },
    {
      "timestamp": "2025-W02",
      "text": "Reports suggested weaker iPhone demand in China."
    },
    {
      "timestamp": "2025-W03",
      "text": "Market sentiment stabilized after inflation data."
    }
  ],
  "basic_features": {
    "recent_trend": "downward",
    "volatility": "moderate",
    "momentum": "negative"
  }
}
```

### 6.3 Output

$$
H_{1:\tau}
=
(h_1, h_2, \ldots, h_\tau).
$$

每個 $h_t$ 都是一筆 structured record。

範例：

```json
{
  "structured_history": [
    {
      "timestamp": "2025-W01",
      "value": 243.85,
      "value_change": null,
      "event_summary": "Technology stocks weakened as Treasury yields rose.",
      "key_drivers": [
        "higher discount-rate pressure",
        "broad risk-off sentiment in growth stocks"
      ]
    },
    {
      "timestamp": "2025-W02",
      "value": 236.85,
      "value_change": -7.00,
      "event_summary": "Apple-specific demand concerns emerged.",
      "key_drivers": [
        "weaker iPhone demand commentary",
        "company-specific negative sentiment"
      ]
    },
    {
      "timestamp": "2025-W03",
      "value": 229.98,
      "value_change": -6.87,
      "event_summary": "Market stabilized but Apple remained under pressure.",
      "key_drivers": [
        "stabilized macro sentiment",
        "persistent company-level uncertainty"
      ]
    }
  ]
}
```

### 6.4 Prompt sketch

這是 project-level prompt sketch，不一定是原論文的 exact prompt。

```text
You are a historical context analyst for time-series forecasting.

Given:
1. A chronological sequence of numerical values.
2. A chronological sequence of textual events.
3. Basic time-series features.

Construct a structured historical context timeline.

For each timestep, output:
- timestamp
- observed value
- value change from previous timestep
- concise event summary
- key drivers of the observed movement
- whether the movement appears driven by trend, seasonality, volatility, macro event, or entity-specific event

Do not forecast future values.
Return valid JSON only.
```

---

## 7. Stage 2A: Macro-Reasoning Agent

### 7.1 Purpose

Macro-Reasoning Agent 負責掌握 broad direction。

它回答的是：

```text
Over the whole forecast horizon, what is the likely regime or trajectory?
```

它應該聚焦在：

```text
long-term trend
macro regime
sector-level direction
market-wide sentiment
persistent fundamentals
seasonality
```

形式化 mapping：

$$
A_{\text{macro}}(H_{1:\tau})
\to
(X^{\text{macro}}_{\tau+1:\tau+T}, R^{\text{macro}}).
$$

### 7.2 Input

```json
{
  "entity": "AAPL",
  "forecast_horizon": 6,
  "structured_history": [
    {
      "timestamp": "2025-W01",
      "value": 243.85,
      "key_drivers": ["higher yields", "growth stock weakness"]
    },
    {
      "timestamp": "2025-W02",
      "value": 236.85,
      "key_drivers": ["China demand concern"]
    },
    {
      "timestamp": "2025-W03",
      "value": 229.98,
      "key_drivers": ["persistent Apple-specific uncertainty"]
    }
  ]
}
```

### 7.3 Output

```json
{
  "macro_forecast_values": [231.0, 233.0, 235.5, 237.0, 238.0, 239.0],
  "macro_reasoning": {
    "overall_direction": "gradual recovery",
    "regime": "stabilization after prior selloff",
    "main_drivers": [
      "broader technology sector stabilization",
      "possible mean reversion after recent decline",
      "remaining company-specific demand risk limits upside"
    ]
  }
}
```

### 7.4 Prompt sketch

```text
You are a macro-level time-series forecasting agent.

Input:
- structured historical context H
- forecast horizon T

Task:
Generate a broad forecast trajectory for the entire horizon.
Focus on:
- overall trend
- regime
- seasonality
- broad macro or sector context
- persistent fundamental drivers

Do not overreact to one-period noise.
Output:
1. macro_forecast_values: list of T numerical values
2. macro_reasoning: concise explanation of the broad trajectory
Return valid JSON only.
```

---

## 8. Stage 2B: Micro-Reasoning Agent

### 8.1 Purpose

Micro-Reasoning Agent 負責捕捉 local、step-by-step changes。

它回答的是：

```text
For each future timestep, what immediate catalyst or short-term fluctuation may affect the value?
```

它應該聚焦在：

```text
short-term events
local volatility
recent momentum
earnings or announcements
near-term catalysts
event-driven shocks
```

形式化 mapping：

$$
A_{\text{micro}}(H_{1:\tau})
\to
(X^{\text{micro}}_{\tau+1:\tau+T}, R^{\text{micro}}_{\tau+1:\tau+T}).
$$

### 8.2 Input

使用同一份 structured history：

```json
{
  "entity": "AAPL",
  "forecast_horizon": 6,
  "structured_history": [
    {
      "timestamp": "2025-W01",
      "value": 243.85,
      "key_drivers": ["higher yields", "growth stock weakness"]
    },
    {
      "timestamp": "2025-W02",
      "value": 236.85,
      "key_drivers": ["China demand concern"]
    },
    {
      "timestamp": "2025-W03",
      "value": 229.98,
      "key_drivers": ["persistent Apple-specific uncertainty"]
    }
  ]
}
```

### 8.3 Output

```json
{
  "micro_forecast": [
    {
      "step": 1,
      "forecast_value": 230.5,
      "reasoning": "Recent negative momentum may continue but selling pressure is slowing."
    },
    {
      "step": 2,
      "forecast_value": 232.0,
      "reasoning": "Short-term stabilization likely if sector sentiment remains supportive."
    },
    {
      "step": 3,
      "forecast_value": 231.0,
      "reasoning": "Company-specific uncertainty may create renewed volatility."
    }
  ]
}
```

### 8.4 Prompt sketch

```text
You are a micro-level time-series forecasting agent.

Input:
- structured historical context H
- forecast horizon T

Task:
Generate a step-by-step forecast.
For each future timestep:
- identify likely immediate catalysts
- estimate local movement
- explain short-term volatility or momentum
- output a numerical value

Output:
A list of T records, each containing:
- step
- forecast_value
- reasoning
- expected local driver
Return valid JSON only.
```

---

## 9. Stage 3: Forecast Synthesizer Agent

### 9.1 Purpose

Forecast Synthesizer Agent 會整合 macro 與 micro forecasts。

它會根據下列資訊決定如何加權 macro 與 micro outputs：

```text
structured history
macro reasoning
micro reasoning
calibration guidelines
domain characteristics
conflicts between broad trend and short-term events
```

形式化 mapping：

$$
A_{\text{syn}}
(
H_{1:\tau},
X^{\text{macro}},
R^{\text{macro}},
X^{\text{micro}},
R^{\text{micro}},
G
)
\to
(X_{\tau+1:\tau+T}, R).
$$

### 9.2 Input

```json
{
  "structured_history": "...",
  "macro_outlook": {
    "values": [231.0, 233.0, 235.5, 237.0, 238.0, 239.0],
    "reasoning": "Gradual recovery after selloff."
  },
  "micro_outlook": {
    "values": [230.5, 232.0, 231.0, 234.0, 236.0, 237.5],
    "reasoning_by_step": [
      "Negative momentum slows.",
      "Sector stabilization.",
      "Company-specific uncertainty may reappear."
    ]
  },
  "calibration_guidelines": [
    "Do not overreact to single negative corporate news if broad sector sentiment improves.",
    "When macro and micro conflict, use recent volatility to moderate the forecast magnitude."
  ]
}
```

### 9.3 Output

```json
{
  "final_forecast_values": [230.7, 232.2, 232.8, 234.8, 236.5, 238.0],
  "final_reasoning": [
    {
      "step": 1,
      "reasoning": "Micro signal dominates because recent negative momentum is still active."
    },
    {
      "step": 2,
      "reasoning": "Macro stabilization and micro recovery both support a small rebound."
    },
    {
      "step": 3",
      "reasoning": "Forecast is moderated because macro recovery conflicts with company-specific uncertainty."
    }
  ]
}
```

### 9.4 Prompt sketch

```text
You are a forecast synthesis agent.

Input:
1. Structured historical context H.
2. Macro forecast values and macro reasoning.
3. Micro forecast values and step-level reasoning.
4. Calibration guidelines G.

Task:
Produce the final numerical forecast for T future timesteps.

Instructions:
- Do not mechanically average macro and micro forecasts.
- Explain how macro and micro signals are weighted.
- If macro and micro disagree, explicitly resolve the conflict.
- Use calibration guidelines to avoid known past errors.
- Keep the final forecast numerically consistent with the reasoning.

Output valid JSON:
{
  "final_forecast_values": [...],
  "final_reasoning": [...]
}
```

---

## 10. Calibration Agent

### 10.1 Purpose

Calibration Agent 會從 historical forecasting errors 中學習。

它不直接 forecast 未來數值，而是產生之後用來引導 Forecast Synthesizer 的 guidelines $G$。

這篇論文使用 forward-simulation backtesting：

```text
historical data
        ↓
split into sequential folds
        ↓
run Nexus on previous folds
        ↓
compare predictions with ground truth
        ↓
Calibration Agent analyzes errors
        ↓
produce guidelines G_i
        ↓
combine robust guidelines
        ↓
validate on hidden validation fold
        ↓
use guidelines only if they improve performance
```

### 10.2 Sequential split

```text
Historical data
├── Split 1: training fold
├── Split 2: training fold
├── ...
├── Split n-1: training fold
└── Split n: hidden validation fold
```

對每個 training fold $i$：

```text
Nexus forecast → compare with ground truth → error analysis → guideline G_i
```

這篇論文使用：

```text
number of backtest splits n = 6
minimum validation improvement threshold k = 5%
```

### 10.3 Guideline construction

對每個 fold：

$$
A_{\text{calib}}
(
\text{prediction}_i,
\text{ground truth}_i,
\text{reasoning}_i,
\text{error}_i
)
\to
G_i.
$$

接著合併：

$$
G = \bigcap_{i=1}^{n-1} G_i.
$$

解讀：

```text
Only robust guidelines common across multiple folds are retained.
This reduces overfitting to one historical anomaly.
```

### 10.4 Hidden validation check

synthesized guidelines $G$ 會被套用到 hidden validation。

```text
If validation improvement >= k%:
    use G in final test forecast
else:
    discard G
```

這點很重要，因為從過去錯誤產生的 guidelines 可能 overfit。

### 10.5 Example calibration guidelines

```json
{
  "guidelines": [
    {
      "rule": "Do not over-amplify a single event when the numerical trend is stable.",
      "reason": "Past forecasts overreacted to isolated news events."
    },
    {
      "rule": "When macro and micro forecasts conflict, reduce the forecast magnitude unless recent momentum confirms the micro view.",
      "reason": "Past errors were largest when short-term catalysts were trusted without numerical confirmation."
    },
    {
      "rule": "For high-volatility equities, preserve wider movement range and avoid excessive smoothing.",
      "reason": "Past forecasts underestimated sudden weekly swings."
    }
  ]
}
```

### 10.6 Prompt sketch

```text
You are a calibration agent for time-series forecasting.

Input:
- historical forecast values
- ground truth values
- macro reasoning
- micro reasoning
- final reasoning
- error metrics
- relevant events during forecast horizon

Task:
Identify systematic forecasting mistakes.

Output:
A list of calibration guidelines that can improve future forecasts.

Each guideline should include:
- rule
- evidence from past error
- when to apply
- when not to apply
Return valid JSON only.
```

---

## 11. Agent input/output summary

| Agent | Input | Output | 主要功能 |
|---|---|---|---|
| Historical Context Agent $A_{ctx}$ | $X_{1:\tau}$, $E_{1:\tau}$, basic TS features | $H_{1:\tau}$ | 將 raw numerical/textual context 轉成 structured causal timeline |
| Macro-Reasoning Agent $A_{macro}$ | $H_{1:\tau}$ | $X^{macro}_{\tau+1:\tau+T}$, $R^{macro}$ | 預測 broad trend 與 regime |
| Micro-Reasoning Agent $A_{micro}$ | $H_{1:\tau}$ | $X^{micro}_{\tau+1:\tau+T}$, $R^{micro}_{\tau+1:\tau+T}$ | 預測 local step-level changes 與 immediate catalysts |
| Forecast Synthesizer $A_{syn}$ | $H$, macro outlook, micro outlook, $G$ | $X_{\tau+1:\tau+T}$, $R$ | 合併 macro/micro forecasts 並產生 final forecast |
| Calibration Agent $A_{calib}$ | predictions, ground truth, errors, reasoning | $G_i$, then robust $G$ | 從 past forecast errors 學習 correction guidelines |

---

## 12. Experiment setup in the paper

這篇論文在 knowledge cutoff 之後的資料上評估 Nexus，以降低 data leakage 風險。

### 12.1 Datasets

```text
Dataset 1: Zillow Real Estate Metrics
Entity type:
    15 major US metropolitan areas
Frequency:
    weekly
Context length:
    3 years
Forecast horizons:
    4, 8, 13 weeks
Evaluation period:
    February 2025 to October 2025

Dataset 2: Stock Market Equities
Tickers:
    AAPL, GOOGL, JNJ, MSFT, NFLX, NVDA, RKLB
Frequency:
    weekly
Context length:
    1 year
Forecast horizons:
    6, 13, 26 weeks
Evaluation period:
    February 2025 to December 2025
```

### 12.2 Models

```text
Gemini-3.1-Pro
Claude-4.5-Sonnet
```

論文回報的 implementation details：

```text
access:
    Vertex AI

temperature:
    0.1

purpose:
    deterministic and reproducible outputs
```

### 12.3 Baselines

```text
TimesFM-2.5
    Time Series Foundation Model baseline

CoT Baseline
    raw historical numerical sequence + textual context
    directly fed into LLM with step-by-step reasoning prompt
```

### 12.4 Evaluation metrics

```text
MAPE
RMSE
```

### 12.5 Evaluation settings

```text
Setting 1:
    numerical context only

Setting 2:
    multimodal context
    numerical history + chronological relevant text
```

### 12.6 Limitations noted by the paper

local source `files/limitations.tex` 提到幾個對此專案重要的限制：

- 評估只涵蓋 Zillow 與 stock datasets，因為同時具備 timestamped numerical data 與 textual context 的公開資料不容易取得。
- 這篇論文刻意使用 selected LLMs 的 January 2025 knowledge cutoff 之後的資料，以降低 leakage risk。
- 論文回報的 multi-agent results 是 single-run evaluations，原因是重複呼叫大型模型成本太高。

對此專案的提醒是：若未來用 Nexus-style agent layer，不應在沒有 repeated runs、成本估計、資料可取得性檢查之前，把它當成穩定可重現的 baseline。

---

## 13. Important findings

### 13.1 Decomposition matters

這篇論文認為 one-shot LLM forecasting 較弱，因為同一個 LLM 必須同時處理：

```text
parse long numerical history
parse textual events
identify trend
identify local volatility
reason about future values
produce numerical outputs
```

Nexus 把這些責任拆給不同 agents 處理。

### 13.2 Macro and micro agents are both useful

component analysis 會分別拿掉：

```text
Nexus without Micro Reasoning
Nexus without Macro Reasoning
Nexus without Calibration
Full Nexus
```

在論文回報的 short-horizon multimodal setting 中，完整 pipeline 表現最好。

解讀：

```text
Macro reasoning helps preserve broad trend and regime.
Micro reasoning helps capture local volatility and event-driven movement.
Calibration helps correct systematic overreaction or underreaction.
```

### 13.3 Reasoning quality is evaluated separately

這篇論文不只評估 numerical forecast accuracy，也用 pairwise LLM judging 評估 reasoning quality。

評估標準包括：

```text
Domain relevance
Event relevance and plausibility
Logic-to-number consistency
Analytical depth
Overall preference
```

這點對此專案有用，因為 LLM-generated views 不只要看數值結果，也應該可以被 audit。

---

## 14. Difference from From News to Forecast

Nexus 和 From News to Forecast 都使用 LLM 與 textual events，但兩者結構不同。

| Aspect | From News to Forecast | Nexus |
|---|---|---|
| Main idea | Filter news, build prompt data, fine-tune LLM | Decompose forecasting into multiple LLM agents |
| News handling | Reasoning Agent filters relevant news | Context Agent structures numerical/textual context |
| Forecasting model | Fine-tuned LLaMA-style model with LoRA | Zero-shot / prompt-based multi-agent LLM framework |
| Reflection/calibration | Evaluation Agent updates news selection logic | Calibration Agent produces synthesis guidelines |
| Output | future time series | future time series + reasoning |
| Key risk addressed | irrelevant news hurts forecasting | monolithic LLM prompt fails to handle numerical + textual complexity |

對此專案而言，From News to Forecast 比較適合處理 news filtering，Nexus 比較適合處理 view-generation architecture 與 macro/micro decomposition，LLM-Enhanced Black-Litterman 則比較適合處理 forecasts/views 如何轉成 $P$、$Q$、$\Omega$ 並進入 portfolio optimization。

---

## 15. 和 LLM-Black-Litterman 專案的關係

Nexus 的原始輸出是 future forecast values $X_{\tau+1:\tau+T}$ 與 reasoning trace $R$。Black-Litterman 需要的是 picking matrix $P$、view vector $Q$ 與 view uncertainty/confidence matrix $\Omega$。

因此，此專案的 adaptation 可以長這樣。這是 project adaptation；$P$、$Q$、$\Omega$ 的定義仍由此專案另行設計：

```text
Historical prices + filtered/structured news
        ↓
Historical Context Agent
        ↓
Macro Agent
    market-level / sector-level direction
        ↓
Micro Agent
    asset-level catalysts
        ↓
View Synthesizer
    produces project-level view signals:
    - expected return view candidates
    - uncertainty / calibration signals
    - possible absolute or relative view structure
        ↓
Black-Litterman posterior
        ↓
Mean-variance optimization
```

Macro Agent 可以支援 market-level 或 sector-level views；Micro Agent 則比較適合支援 individual asset-level views。真正的 $P$、$Q$、$\Omega$ mapping 仍需要在此專案中另外定義。

### 15.1 Possible mapping to $Q$

對 asset $i$，Nexus-like output 可能產生：

```json
{
  "ticker": "AAPL",
  "forecast_horizon": "2 weeks",
  "macro_direction": "positive",
  "micro_direction": "neutral",
  "final_expected_return": 0.012,
  "reasoning": "Macro sector support is positive, but company-specific demand concerns limit upside."
}
```

接著：

$$
Q_i = 0.012.
$$

### 15.2 Possible mapping to $\Omega$

Nexus 沒有直接定義 Black-Litterman $\Omega$。

可能的專案選項需要分開記錄，包括 repeated-query variance、根據過去 forecast errors 估計的 calibration-error variance、reasoning-based confidence score，或結合 repeated-query variance 與 calibration error 的 hybrid method。後兩者比較像 heuristic 或 experimental method，報告中需要清楚標示。

比較保守的做法是讓 Nexus 先用在 structured $Q$ generation；$\Omega$ 則先使用 repeated-query variance 或 calibration-error variance。若要提出新的 $\Omega$ 公式，應明確標成 heuristic。

### 15.3 Possible mapping to $P$

如果每個 asset 都有一個 expected return view：

$$
P = I_n.
$$

如果 Nexus 產生 sector-level 或 relative views：

```text
Technology sector will outperform Energy sector by 1%.
```

那 $P$ 就不再是 identity matrix，而需要編碼 relative exposure。

範例：

```text
Assets:
    AAPL, MSFT, XOM

View:
    Tech basket 比 XOM 多 1% expected return

P row:
    [0.5, 0.5, -1.0]
```

---

## 16. 此專案的實作位置

Nexus-style reasoning 比較適合在 BL mapping baseline 之後加入。較合理的順序是先 reproduce LLM-Enhanced Black-Litterman 的 BL mapping baseline，例如 $P = I$、$Q$ from LLM return forecast、$\Omega$ from repeated-query variance；接著用 filtered 或 mocked news 建立 Nexus-style structured reasoning fixture，例如 sample historical context JSON、mock macro output、mock micro output 與 mock synthesizer output。

等資料結構穩定後，可以再把 synthesizer output 轉成每個 asset 的 expected return view，並保持 $\Omega$ construction 獨立，例如 repeated-query variance 或 calibration-error variance。Real news retrieval 與 live LLM calls 比較適合放到後期，因為完整 Nexus system 需要 careful prompt design、aligned textual events 與 historical backtest folds for calibration，對初期課程專案來說範圍較大。

Nexus 是此專案 agentic view synthesis 的主要架構參考；第一版可以先用 mocked / deterministic context 驗證資料結構，再逐步接上完整 agent workflow。

---

## 17. Minimal project schemas

### 17.1 Historical context input

```json
{
  "rebalance_date": "2025-03-03",
  "ticker": "AAPL",
  "frequency": "daily",
  "lookback_window": "2 weeks",
  "historical_returns": [-0.0117, -0.0092, -0.0231],
  "market_returns": [0.0009, -0.0039, -0.0161],
  "sector_returns": [-0.0014, -0.0038, -0.0188],
  "events": [
    {
      "date": "2025-02-25",
      "scope": "asset",
      "summary": "Apple faced renewed concerns about iPhone demand.",
      "source_type": "news"
    },
    {
      "date": "2025-02-26",
      "scope": "market",
      "summary": "Technology stocks declined after higher yield expectations.",
      "source_type": "macro"
    }
  ]
}
```

### 17.2 Context Agent output

```json
{
  "ticker": "AAPL",
  "structured_history": [
    {
      "date": "2025-02-25",
      "return": -0.0117,
      "drivers": [
        "negative asset-specific demand news",
        "weak technology sector sentiment"
      ],
      "movement_type": "event-driven decline"
    }
  ]
}
```

### 17.3 Macro Agent output

```json
{
  "ticker": "AAPL",
  "macro_direction": "slightly positive",
  "macro_expected_return": 0.004,
  "reasoning": "Technology sector sentiment is stabilizing, but upside remains limited by rate pressure."
}
```

### 17.4 Micro Agent output

```json
{
  "ticker": "AAPL",
  "micro_direction": "neutral to negative",
  "micro_expected_return": -0.002,
  "step_reasoning": [
    {
      "period": "week_1",
      "expected_return": -0.001,
      "reason": "Recent demand concern may continue to weigh on sentiment."
    },
    {
      "period": "week_2",
      "expected_return": -0.001,
      "reason": "No clear short-term positive catalyst."
    }
  ]
}
```

### 17.5 View Synthesizer output for BL

```json
{
  "ticker": "AAPL",
  "forecast_horizon": "2 weeks",
  "final_expected_return": 0.001,
  "confidence": "medium",
  "uncertainty_reason": "Macro and micro signals conflict; final view is moderated.",
  "view_type": "absolute",
  "black_litterman_mapping": {
    "Q_i": 0.001,
    "P_i": "one-hot row for AAPL",
    "Omega_source": "to be computed separately"
  }
}
```

---

## 18. 實作與報告注意事項

### 18.1 Nexus 不應直接決定 portfolio weights

對此專案而言，LLM 比較適合產生 views、uncertainty signals、reasoning 與 event summaries。Portfolio weights 仍應由 Black-Litterman posterior 搭配 portfolio optimization 產生。

### 18.2 $\Omega$ methods 應分開命名

Nexus-style reasoning 可以提供 uncertainty signal，但 Black-Litterman 需要的是 numerical matrix。

每一種 $\Omega$ method 都應分開命名，例如 `omega_repeated_query_variance`、`omega_calibration_error`、`omega_reasoning_confidence_heuristic`、`omega_hybrid_experimental`。這樣比較容易在報告中區分 baseline、heuristic 與 future experiment。

### 18.3 保持 numerical scale 一致

如果 Nexus-like agents 輸出的是 two-week expected return，那 Black-Litterman $Q$、$\pi$、$\Sigma$ 與 portfolio optimization 都應使用相容的 horizon 和 scale。實作與報告中需要記錄 return 是 daily 或 two-week、decimal 或 percent、arithmetic return 或 log return，以及 annualized 或 non-annualized。

### 18.4 分清楚原論文與 project adaptation

寫 report 時需要分清楚原論文與此專案 adaptation。Nexus 原文的 claim 是 forecasting future time-series values and reasoning；此專案的 adaptation 是使用 Nexus-style agents 協助建構 Black-Litterman views。因此，不應把 Nexus 描述成 Black-Litterman paper。

---

## 19. 簡短結論

Nexus 對 LLM-based forecasting 的價值在於它把責任拆開：Context Agent 整理 historical numerical and textual context，Macro Agent 捕捉 broad trend and regime，Micro Agent 處理 short-term catalysts and local volatility，Synthesizer 合併 macro/micro forecasts，Calibration Agent 則從 past errors 建立 correction guidelines。

對此專案最有用的是它的 design principle：先整理 context，再分成 macro / micro reasoning，接著 synthesis，最後 calibration。這比要求單一 LLM prompt 一次處理所有資訊更適合複雜的 news-aware view generation。

這可以作為放在 Black-Litterman 前面的 agentic view-generation layer：

```text
Nexus-style agents
        ↓
news-aware Q candidates and uncertainty signals
        ↓
Black-Litterman
        ↓
portfolio optimization
```
