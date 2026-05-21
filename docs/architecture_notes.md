# Architecture Notes

This file records architecture alternatives, design decisions, and open questions for the project.

## Current project stage

The model architecture is not finalized yet.

Current priority:

1. finish course assignments;
2. read and summarize relevant papers;
3. compare possible architectures;
4. decide the first reproducible baseline.

## Baseline architecture candidate

```text
Historical prices
    -> return calculation
    -> market prior pi and covariance Sigma
    -> fixed or mocked views P, Q, Omega
    -> Black-Litterman posterior returns
    -> portfolio optimization
    -> backtest
````

## Open questions

1. Should the first reproducible baseline use fixed synthetic views or paper-style LLM views?
2. Should the project replicate the exact top 50 S&P 500 universe or use an approximate available universe?
3. Should `Omega` initially be repeated-query variance only?
4. How should news events modify `Q`, `Omega`, or both?
5. Should macro/micro decomposition be implemented or only discussed in the report?
