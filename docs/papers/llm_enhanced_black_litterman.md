# 論文筆記：LLM-Enhanced Black-Litterman Portfolio Optimization

## 0. Reference

- Paper: `LLM-Enhanced Black-Litterman Portfolio Optimization`
- Authors: Youngbin Lee, Yejin Kim, Juhyeong Kim, Suin Kim, Yongjae Lee
- Venue / arXiv: arXiv:2504.14345v2; local source also lists `CIKM'25 Workshop on FinAI` / `Advances in Financial AI`
- Code / data if mentioned by the paper: `https://github.com/youngandbin/LLM-BLM`
- Local source files inspected: `references/local/arXiv-2504.14345v2/_main.tex`, `references/local/arXiv-2504.14345v2/figure/prompt_system.tex`, `references/local/arXiv-2504.14345v2/figure/prompt_user.tex`, result-table `.tex` files under `references/local/arXiv-2504.14345v2/figure/`
- Note status: first-pass reading note revised with local source check; exact replication details such as downloaded price data, code behavior, and full universe list still `needs verification`

## 1. 核心摘要與 pipeline

這篇論文的核心是讓 LLM 產生 Black-Litterman 所需的 view vector $Q$ 與 view uncertainty matrix $\Omega$，再由 Black-Litterman posterior return 與 mean-variance optimization 決定最終權重。

```text
Historical prices + company metadata
        ↓
Structured prompt
        ↓
Repeated LLM return forecasts
        ↓
Q = mean forecasts
Omega = forecast variance
P = identity matrix
        ↓
Black-Litterman posterior return mu_BL
        ↓
Mean-variance portfolio optimization
        ↓
Portfolio weights
        ↓
Hold for two weeks and rebalance
```

---

## 2. 這篇論文在此專案中的角色

這篇論文適合作為此專案的 Black-Litterman integration baseline，但不等於完整專案方向。它直接處理：

- 如何把 LLM output 轉成 Black-Litterman views。
- 如何把 LLM prediction uncertainty 轉成 $\Omega$。
- 如何避免讓 LLM 直接輸出 portfolio allocation。
- 如何設計 two-week rebalance backtest。
- 如何比較 LLM-BL 與 EW、MVO、market benchmark。

但它也有明顯限制：

- 它沒有使用 news retrieval 或 event reasoning agent。
- 它的重點在 LLM-to-BL mapping，而非完整的 LLM time-series forecasting framework。
- 它主要使用 past stock/sector/market returns + company metadata。
- $\Omega$ 只由 repeated LLM outputs 的 variance 得到。
- 它使用 absolute views，沒有使用 relative views。
- 它沒有處理多層新聞篩選、事件因果推理、macro/micro agent synthesis。

這裡要清楚分成三件事：

1. 論文實際做法：用 repeated LLM forecasts 產生 $Q$ 與 diagonal $\Omega$，再做 Black-Litterman 與 optimizer。
2. 此專案可借用之處：先把它當作 baseline mapping，不讓 LLM 直接決定 portfolio weights。
3. 此專案仍需自行處理的問題：news-aware view generation、news/event filtering、$\Omega$ calibration、資料可重現性與 backtest assumptions。

因此，這篇論文回答的是「LLM forecast 如何進入 Black-Litterman」，但此專案真正要往前推的是「news/event-informed LLM views 如何進入 Black-Litterman」。

---

## 3. 模型 / pipeline 架構總覽

```text
[Asset universe]
    - Top 50 S&P 500 constituents by market cap
    - Selection date: 2025-03-26
    - Price source: Yahoo Finance

        ↓

[Historical price data]
    - Total period: 2024-06 to 2025-06
    - Validation period: 2024-06 to 2024-08
    - Test period: 2024-09 to 2025-06
    - Rebalancing frequency: every 2 weeks

        ↓

[Lookback window at each rebalancing date t]
    For each stock i:
    - past 2 weeks stock daily returns
    - past 2 weeks sector daily returns
    - past 2 weeks S&P 500 daily returns
    - ticker
    - company name
    - GICS sector
    - GICS sub-industry

        ↓

[Structured LLM prompt]
    System prompt:
    - role: financial analyst
    - task: predict average daily return over next 2 weeks
    - constraints: output one float only

    User prompt:
    - stock returns
    - sector returns
    - market returns
    - company metadata

        ↓

[Repeated LLM querying]
    For each stock i:
    - query LLM N = 100 times
    - collect predictions r_{i,1}, ..., r_{i,N}

        ↓

[View construction]
    q_i = mean repeated prediction for stock i
    Omega_ii = variance of repeated predictions for stock i
    P = I_n

        ↓

[Black-Litterman]
    輸入：
    - pi: market equilibrium prior return
    - Sigma: covariance matrix
    - q: LLM-generated view vector
    - P: picking matrix
    - Omega: view uncertainty matrix
    - tau: prior-view confidence scaling parameter

    輸出：
    - mu: posterior expected return

        ↓

[Mean-variance optimization]
    輸入：
    - mu
    - Sigma
    - lambda = 0.1
    - constraints: sum weights = 1, no shorting

    輸出：
    - optimal portfolio weights w*

        ↓

[Backtest]
    - hold portfolio for next 2 weeks
    - subtract transaction costs
    - repeat at next rebalancing date
```

---

## 4. Data layer

### 4.1 Asset universe

論文設定：

```text
Universe:
    largest 50 S&P 500 constituents by market capitalization
Selection date:
    2025-03-26
Data source:
    Yahoo Finance
Data period:
    2024-06 to 2025-06
```

此專案實作備註：

```text
If exact market-cap constituents as of 2025-03-26 cannot be reproduced,
record the deviation explicitly.

Example deviation:
- used current S&P 500 top 50 instead of historical top 50
- used available Yahoo Finance adjusted close data
- excluded tickers with missing data
```

local source 檢查：`_main.tex` 明確寫到使用 2025-03-26 市值最大的 50 檔 S&P 500 constituents、Yahoo Finance，以及 2024-06 到 2025-06 的資料。詳細 ticker list 與 adjusted-price handling 仍需要從 code/data 驗證，不能只靠論文原始碼，因此標成 `needs verification`。

### 4.2 Time split

```text
Validation:
    2024-06 to 2024-08
    Used only for tau tuning.

Test:
    2024-09 to 2025-06
    Used for final performance evaluation.
```

### 4.3 Rebalancing setup

在每個 rebalancing date `t`：

```text
Lookback period:
    past 2 weeks

Forecast target:
    average daily return over next 2 weeks

Holding period:
    next 2 weeks

Rebalance:
    every 2 weeks
```

重要的是，LLM 只能接收 rebalancing date 當下已經可得的資訊。

---

## 5. Raw input schema

對每檔股票 `i` 和 rebalancing date `t`，LLM input 可以表示成：

```json
{
  "date": "2024-09-02",
  "ticker": "AAPL",
  "company_name": "Apple Inc.",
  "gics_sector": "Information Technology",
  "gics_sub_industry": "Technology Hardware, Storage & Peripherals",
  "stock_daily_returns": [-1.17, -0.92, -2.31, -0.36, -3.02, 2.53, 0.10, -0.23, 0.45],
  "sector_daily_returns": [-0.14, -0.38, -1.88, 0.03, -1.10, 2.38, -0.41, 0.17, -0.31],
  "market_daily_returns": [0.09, -0.39, -1.61, -0.04, -0.67, 2.05, -0.56, 0.40, -0.01],
  "forecast_horizon": "next two weeks",
  "target": "average daily return"
}
```

這篇論文會先把 daily returns 乘以 100，再傳給 LLM。

範例：

```text
Raw return:
    -0.0036

Prompt value:
    -0.36
```

原因是 raw decimal form 的 daily returns 數值很小，轉成 percentage-scale value 後，LLM 可能比較容易辨識數值差異。

---

## 6. Prompting layer

### 6.1 System prompt structure

這篇論文使用 structured system prompt，目的是把 LLM 約束在 quantitative forecasting task。

概念型 template：

```text
You are providing analysis on {DATE}.

Predict the average daily return for the next two weeks based on the information provided about a stock's past performance.

You will receive:
- Daily Returns: stock's daily returns from the past two weeks.
- Company Sector: GICS sector classification.
- Sector Returns: sector daily returns from the past two weeks.
- Market Returns: S&P 500 daily returns from the past two weeks.
- Company Information:
  - Ticker
  - Company Name
  - GICS Sector
  - GICS Sub-Industry

Steps:
1. Analyze the time-series data.
2. Consider sector performance.
3. Incorporate company information.
4. Predict future returns.

Output format:
Return a single float value representing the predicted average daily return for the stock over the next two weeks.
Do not include commentary or explanation.
```

### 6.2 User prompt example

```text
Daily Returns: [-1.17, -0.92, -2.31, -0.36, -3.02, 2.53, 0.1, -0.23, 0.45]

Company Sector: Information Technology

Sector Returns: [-0.14, -0.38, -1.88, 0.03, -1.1, 2.38, -0.41, 0.17, -0.31]

Market Returns: [0.09, -0.39, -1.61, -0.04, -0.67, 2.05, -0.56, 0.4, -0.01]

Company Information:
Ticker: AAPL
Company Name: Apple Inc.
GICS sector: Information Technology
GICS sub-industry: Technology Hardware, Storage & Peripherals
```

### 6.3 LLM output format

預期輸出：

```text
0.12
```

或：

```text
-0.08
```

不輸出解釋、不輸出 JSON、不做排名，也不直接輸出 allocation。

這個輸出會被解讀為：

```text
predicted average daily return over the next two weeks
```

因為 input 已經乘以 100，實作時必須決定並記錄 LLM output 是被當成 percentage points，還是會再轉回 decimal return。

建議的專案慣例：

```python
llm_output_percent = 0.12
q_i = llm_output_percent / 100
```

---

## 7. LLM view generation layer

對每檔股票 `i`，LLM 會被重複查詢：

```text
N = 100
```

令：

```text
r_{i,j} = j-th LLM prediction for stock i
```

其中：

```text
i = 1, ..., n
j = 1, ..., N
```

AAPL 的 raw repeated outputs 範例：

```text
r_AAPL = [0.12, 0.08, 0.15, 0.10, ..., 0.09]
```

如果輸出是 percentage points，在進入 BL 前要先轉成 decimal：

```text
[0.0012, 0.0008, 0.0015, 0.0010, ..., 0.0009]
```

---

## 8. View vector `q`

對每檔股票：

$$
q_i = \frac{1}{N}\sum_{j=1}^{N} r_{i,j}.
$$

對所有股票：

$$
q =
\begin{bmatrix}
q_1 \\
q_2 \\
\vdots \\
q_n
\end{bmatrix}.
$$

形狀：

```text
q shape: (n,)
```

在這篇論文中：

```text
n = 50
k = 50
```

因為這篇論文為每檔股票建立一個 view。

範例：

```json
{
  "tickers": ["AAPL", "MSFT", "NVDA"],
  "q": [0.0011, 0.0007, 0.0018]
}
```

這代表 AAPL、MSFT、NVDA 的 expected average daily return 分別為 0.11%、0.07%、0.18%。

---

## 9. Picking matrix `P`

這篇論文使用 absolute views。

它沒有使用「AAPL will outperform MSFT by 0.2%」這類 relative views，而是使用「AAPL expected return = q_AAPL」、「MSFT expected return = q_MSFT」這類 absolute views。

因此：

$$
P = I_n.
$$

$P$ 的 shape 是 $(k,n)=(n,n)$。

三個資產的例子：

$$
P =
\begin{bmatrix}
1 & 0 & 0 \\
0 & 1 & 0 \\
0 & 0 & 1
\end{bmatrix}.
$$

這個例子中，View 1 對應 AAPL，View 2 對應 MSFT，View 3 對應 NVDA。

---

## 10. Confidence matrix $\Omega$

這篇論文用 repeated LLM predictions 估計 uncertainty。

對每檔股票：

$$
\Omega_{ii}
=
\frac{1}{N-1}
\sum_{j=1}^{N}
(r_{i,j} - q_i)^2.
$$

接著：

$$
\Omega =
\operatorname{diag}(\Omega_{11}, \Omega_{22}, \ldots, \Omega_{nn}).
$$

$\Omega$ 的 shape 是 $(k,k)=(n,n)$。

直覺上，若 repeated LLM predictions 的 variance 較高，表示該 view 的 uncertainty 較高，$\Omega$ 對角線元素也會較大，Black-Litterman posterior 會較少相信這個 view。反過來，如果 repeated predictions 很穩定，$\Omega$ 會較小，posterior 會更靠近該 view。

範例：

```json
{
  "tickers": ["AAPL", "MSFT", "NVDA"],
  "q": [0.0011, 0.0007, 0.0018],
  "Omega_diag": [0.000004, 0.000009, 0.000016]
}
```

在這個例子中，NVDA 的 LLM view uncertainty 最高。

---

## 11. Market prior and covariance layer

Black-Litterman 需要 market equilibrium return vector $\pi$，以及 asset return covariance matrix $\Sigma$。

這篇論文把 $\pi$ 描述為由 market capitalization weights 推得的 equilibrium returns，$\Sigma$ 則是 stock returns 的 covariance matrix。

$\pi$ 的 shape 是 $(n,)$，$\Sigma$ 的 shape 是 $(n,n)$。重現時需要記錄 return frequency、covariance estimation 的 lookback window、returns 是否 daily 或 annualized，以及 $\pi$、$q$、$\Sigma$、$\Omega$ 是否使用相容的 scale。

例如 $q$ 若代表 average daily return，$\pi$ 也應該在 daily return scale；$\Sigma$ 與 $\Omega$ 則應對應 daily return variance scale。

---

## 12. Black-Litterman layer

這篇論文把 BL posterior estimation 表示為：

$$
y = X\mu + \epsilon,
\quad
\epsilon \sim N(0,V),
$$

其中：

$$
y =
\begin{bmatrix}
\pi \\
q
\end{bmatrix},
\quad
X =
\begin{bmatrix}
I \\
P
\end{bmatrix},
\quad
V =
\begin{bmatrix}
\tau \Sigma & 0 \\
0 & \Omega
\end{bmatrix}.
$$

輸入包含 prior equilibrium returns $\pi$、return covariance matrix $\Sigma$、LLM view vector $q$、picking matrix $P$、view uncertainty matrix $\Omega$，以及控制 prior 和 views 相對信心的 $\tau$。輸出是 posterior expected return vector $\mu$，shape 為 $(n,)$。

直覺上，$\mu$ 是 market prior 與 LLM views 的加權融合。若 $\Omega$ 較大，表示 LLM views 較不確定，posterior 會更靠近 $\pi$；若 $\Omega$ 較小，posterior 會更靠近 $q$。$\tau$ 則控制 prior 的相對 uncertainty：$\tau$ 越大，prior 被視為越不確定，views 的影響也會更大。

---

## 13. $\tau$ tuning

這篇論文用 validation period 來 tune $\tau$。

### 13.1 Initial heuristic

$$
\tau_{\text{init}}
=
\frac{1}{|T_{\text{val}}|}
\sum_{t \in T_{\text{val}}}
\frac{\operatorname{mean}(\Omega_t)}
{\operatorname{mean}(\Sigma_t)}.
$$

解讀：

```text
tau_init is based on the relative scale of:
- LLM view uncertainty Omega
- market return covariance Sigma
```

### 13.2 Grid search

$$
T =
\{
0.5\tau_{\text{init}},
0.75\tau_{\text{init}},
\tau_{\text{init}},
1.25\tau_{\text{init}},
1.5\tau_{\text{init}}
\}.
$$

對每個 candidate $\tau$：

```text
1. Run validation-period backtest.
2. Compute Sharpe ratio.
3. Choose tau with highest validation Sharpe.
```

最後：

```text
tau_star = argmax validation Sharpe
```

接著使用：

```text
tau = tau_star
```

套用到 test period。

---

## 14. Portfolio optimization layer

取得 posterior return $\mu$ 之後，這篇論文使用 mean-variance optimization。

目標式：

$$
\min_w
\left(
w^T \Sigma w
-
\lambda w^T r
\right).
$$

對 LLM-BL：

$$
r = \mu.
$$

限制式：

$$
\sum_i w_i = 1,
$$

$$
w_i \ge 0.
$$

所以：

```text
No short selling.
Fully invested portfolio.
```

這篇論文設定：

```text
lambda = 0.1
```

輸出：

```text
w* = optimal portfolio weights
```

output schema 範例：

```json
{
  "date": "2024-09-02",
  "weights": {
    "AAPL": 0.052,
    "MSFT": 0.041,
    "NVDA": 0.088
  }
}
```

---

## 15. Backtest loop

在每個 rebalancing date：

```text
1. 選定當期 asset universe。
2. 載入過去兩週的 stock、sector、market returns。
3. 對每檔股票建立一個 LLM prompt。
4. 每檔股票重複 query LLM，N = 100。
5. 計算 q。
6. 用 repeated-query variance 計算 Omega。
7. 設定 P = identity matrix。
8. 估計 pi 與 Sigma。
9. 計算 BL posterior return mu。
10. 解 mean-variance optimization。
11. 持有 portfolio 到下一個兩週區間。
12. 套用 transaction costs。
13. 移到下一個 rebalancing date。
```

這篇論文納入 transaction costs：

```text
transaction cost = 0.1% of portfolio weight changes at each rebalance
```

實作公式：

$$
\text{cost}_t
=
0.001 \sum_i |w_{t,i} - w_{t^-,i}|.
$$

重現時需要確認論文實作是否使用這個精確公式，或是等價的 turnover-based implementation。

---

## 16. Baselines

這篇論文將 LLM-BL portfolios 與下列 baseline 比較：

```text
1. S&P 500 Index
   Market-cap-weighted market benchmark.

2. Equally Weighted portfolio
   Equal allocation to all assets.

3. Mean-Variance Optimization
   Uses historical returns and covariance only.
   No LLM views.
```

對 MVO：

$$
\min_w
\left(
w^T \Sigma w
-
\lambda w^T r
\right),
$$

其中 `r` 是 historical expected return estimate，而不是 BL posterior return。

---

## 17. Model variants

這篇論文評估多個 LLM-driven BL variants：

```text
BLM-Gemma
BLM-Qwen
BLM-Llama
BLM-GPT
```

使用的 LLM：

```text
Gemma-7B
Qwen-2-7B
LLaMA-3.1-8B
GPT-4o-mini
```

重要解讀：

```text
這篇論文對 LLM 選擇的解讀不只看 forecasting accuracy，也觀察不同 LLM 透過 view distribution 形成的 investment styles。
```

對此專案而言，這表示我們應該記錄：

```text
- mean of generated q
- dispersion of q
- sign bias: optimistic / pessimistic
- sector concentration
- turnover caused by each LLM
- performance by market regime
```

---

## 18. What each layer consumes and produces

| Layer | Input | Operation | Output |
|---|---|---|---|
| Data universe | S&P 500 constituents, market cap date | 選出 top 50 | asset list |
| Price data | Yahoo Finance prices | 計算 daily returns | stock return matrix |
| Sector/market context | sector index/sector aggregate, S&P 500 | 計算 daily returns | sector returns, market returns |
| Prompt builder | returns + metadata | 建立 system/user prompt | prompt text |
| LLM querying | prompt text | 重複 sample/query N = 100 次 | repeated forecasts |
| View vector | repeated forecasts | 對每檔股票取平均 | `q` |
| Confidence matrix | repeated forecasts | 對每檔股票取 variance | diagonal `Omega` |
| Picking matrix | one absolute view per stock | identity mapping | `P = I_n` |
| Market prior | market cap weights + covariance | 估計 equilibrium return | `pi` |
| BL posterior | `pi`, `Sigma`, `P`, `q`, `Omega`, `tau` | Bayesian blending | `mu` |
| Optimizer | `mu`, `Sigma`, constraints | MVO | `w*` |
| Backtest | `w*`, realized returns | hold and rebalance | performance metrics |

---

## 19. Minimal implementation schema

### 19.1 Prompt input record

```json
{
  "rebalance_date": "2024-09-02",
  "ticker": "AAPL",
  "company_name": "Apple Inc.",
  "gics_sector": "Information Technology",
  "gics_sub_industry": "Technology Hardware, Storage & Peripherals",
  "stock_daily_returns_pct": [-1.17, -0.92, -2.31],
  "sector_daily_returns_pct": [-0.14, -0.38, -1.88],
  "market_daily_returns_pct": [0.09, -0.39, -1.61],
  "target": "average daily return over next two weeks"
}
```

### 19.2 LLM response record

```json
{
  "rebalance_date": "2024-09-02",
  "ticker": "AAPL",
  "model": "qwen-2-7b",
  "run_id": 17,
  "prediction_pct": 0.12,
  "prediction_decimal": 0.0012
}
```

### 19.3 View record

```json
{
  "rebalance_date": "2024-09-02",
  "ticker": "AAPL",
  "model": "qwen-2-7b",
  "num_queries": 100,
  "q": 0.0011,
  "omega": 0.000004
}
```

### 19.4 BL input record

```json
{
  "rebalance_date": "2024-09-02",
  "tickers": ["AAPL", "MSFT", "NVDA"],
  "pi": [0.0005, 0.0004, 0.0008],
  "q": [0.0011, 0.0007, 0.0018],
  "P": "identity",
  "Omega_diag": [0.000004, 0.000009, 0.000016],
  "tau": 0.03,
  "Sigma_frequency": "daily",
  "return_unit": "decimal_daily_return"
}
```

### 19.5 Portfolio output record

```json
{
  "rebalance_date": "2024-09-02",
  "model": "qwen-2-7b",
  "weights": {
    "AAPL": 0.052,
    "MSFT": 0.041,
    "NVDA": 0.088
  },
  "constraints": {
    "sum_to_one": true,
    "long_only": true
  }
}
```

---

## 20. 實作與報告檢查重點

### 20.1 Unit consistency

重現這篇論文或改成此專案 baseline 時，最容易出錯的是單位不一致。需要確認 returns 是 percent 還是 decimal，$q$ 和 $\pi$ 是否在同一個 scale，$\Sigma$ 和 $\Omega$ 是否對應同一種 variance scale，以及 optimizer 使用的是 daily 還是 annualized quantities。

比較清楚的專案慣例是：內部計算使用 decimal daily returns；prompt inputs 可以用 percentage points 方便 LLM 閱讀；LLM outputs 則在進入 BL 前轉回 decimal daily returns。

### 20.2 No look-ahead bias

在 rebalancing date $t$，prompt 只能包含 $t$ 當天或以前可取得的資料。目標期間 $t$ 到 $t+2$ weeks 的 realized returns 不能出現在 prompt input 裡。$\tau$ 也應只用 validation period 調整，不能使用 test period 搜尋。

### 20.3 LLM reproducibility

LLM 實驗若要能被報告或比較，需要記錄 model name、model version、temperature、`top_p`、random seed（如果可用）、repeated queries 次數、prompt template version 與 inference date。

### 20.4 $\Omega$ construction

這篇論文只使用 repeated LLM predictions 的 diagonal variance 作為 $\Omega$。這個方法應和 canonical BL $\Omega$、Idzorek confidence mapping、residual variance、shrinkage $\Omega$ 等其他方法分開討論。若未來要加入其他 $\Omega$ construction method，報告中應明確標成 project extension。

### 20.4.1 對 $\Omega$ 的疑慮：variance 不等於 factual confidence

這篇論文的 $\Omega$ 來自 repeated LLM outputs 的 variance。這是合理的 baseline，因為它讓不穩定的 LLM forecasts 在 Black-Litterman posterior 裡被降低權重。

但我目前的疑慮是：repeated-query variance 衡量的是 output self-consistency，不一定衡量 view 是否真實可靠。若 LLM 對某個股票或市場 regime 一直有同樣偏誤，輸出可能很穩定，variance 很小，$\Omega$ 也會很小；可是這個 view 仍可能是錯的，或是缺乏新聞/事件根據。

因此，小 $\Omega$ 比較適合解讀成「輸出穩定」，而不是「事實上一定可靠」。比較保守的處理方式是：

- 先把 paper-style repeated-output variance 當成 baseline；
- 把 `repeated_output_variance` 和未來的 `historical_calibration_error`、`news_selection_quality_signal` 分開命名；
- 若要結合多種 uncertainty signal，清楚標成 proposed heuristic 或 future experiment；
- 在沒有額外驗證前，不把 $\Omega$ 直接等同於 factual reliability。

### 20.5 Prompt-output parsing

雖然 prompt 要求只輸出一個 float，實作仍需要處理 invalid outputs：

```text
valid:
    0.12
    -0.08

invalid:
    "The predicted return is 0.12%"
    "AAPL will likely rise."
    "[0.12]"
```

parser 可以採取保守規則：擷取第一個合法 float、遇到多個不相關數字時拒絕該輸出，並保留 raw output 供後續 audit。

---

## 21. 和此專案方向的關係

對目前這個專案來說，這篇論文提供最清楚的 BL integration skeleton：LLM 負責產生 views，BL 負責整合 market prior 和 LLM views，MVO 負責產生 final weights，backtest 則用來和 EW、MVO、market benchmark 比較。

實作順序可以先保守推進：先完成不含 LLM 的 baseline BL，再加入 fixed mocked $Q$ 和 $\Omega$，接著加入 paper-style repeated-query $Q$ 和 $\Omega$，最後再接 deterministic news/event fixtures，以及 From News to Forecast 與 Nexus 啟發的 view-generation layer。

baseline 的作用是讓後續新聞 view 有穩定的 BL framework 可以測。

---

## 22. 如果要延伸這篇論文，還缺什麼

這篇論文沒有回答 raw financial news 如何收集、irrelevant news 如何篩除、event rationale 如何表示、news 應該影響 $Q$ 或 $\Omega$，以及 macro events 和 micro company events 如何分開。這些問題比較適合由 From News to Forecast 的 news filtering / reflection，以及 Nexus 的 contextualization、macro/micro reasoning、synthesis/calibration 補上。

所以對此專案而言，這篇論文適合作為 Black-Litterman integration baseline。最終設計仍需要把 selected news、event rationale、macro/micro reasoning 轉成可進入 BL 的 views。

---

## 23. 重要公式

### View mean

$$
q_i = \frac{1}{N}\sum_{j=1}^{N} r_{i,j}
$$

### View uncertainty

$$
\Omega_{ii}
=
\frac{1}{N-1}
\sum_{j=1}^{N}
(r_{i,j} - q_i)^2
$$

### Picking matrix

$$
P = I_n
$$

### Black-Litterman observation form

$$
y = X\mu + \epsilon,
\quad
\epsilon \sim N(0,V)
$$

$$
y =
\begin{bmatrix}
\pi \\
q
\end{bmatrix},
\quad
X =
\begin{bmatrix}
I \\
P
\end{bmatrix},
\quad
V =
\begin{bmatrix}
\tau \Sigma & 0 \\
0 & \Omega
\end{bmatrix}
$$

### Tau initial value

$$
\tau_{\text{init}}
=
\frac{1}{|T_{\text{val}}|}
\sum_{t \in T_{\text{val}}}
\frac{\operatorname{mean}(\Omega_t)}
{\operatorname{mean}(\Sigma_t)}
$$

### Tau grid

$$
T =
\{
0.5\tau_{\text{init}},
0.75\tau_{\text{init}},
\tau_{\text{init}},
1.25\tau_{\text{init}},
1.5\tau_{\text{init}}
\}
$$

### Portfolio optimization

$$
\min_w
\left(
w^T \Sigma w
-
\lambda w^T r
\right)
$$

對 LLM-BL：

$$
r = \mu
$$

限制式：

$$
\sum_i w_i = 1,
\quad
w_i \ge 0.
$$

---

## 24. 簡短結論

這篇論文提供一個乾淨、可實作的 LLM-BL baseline。它最重要的設計優點是責任分工清楚：LLM 產生 return forecasts 與 uncertainty，Black-Litterman 將它們轉成 posterior expected returns，mean-variance optimization 再把 posterior returns 轉成 portfolio weights。

它對此專案的主要限制是還沒有 structured news/event reasoning。因此比較合理的順序是先把它實作成 BL integration baseline，再把 From News to Forecast 的 news filtering / reflection 與 Nexus 的 macro/micro synthesis 接成 news-aware LLM view-generation layer，最後回到 $P$、$Q$、$\Omega$ 與 portfolio optimization。
