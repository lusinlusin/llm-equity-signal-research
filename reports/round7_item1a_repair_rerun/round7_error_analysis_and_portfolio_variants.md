# Round 7 Error Analysis and Portfolio Variants

Inputs:

- Signal: `reports/round7_item1a_repair_rerun/round7_item1a_repair_deepseek_diff_surprise_sector_size_neutral.csv`
- Features: `data/processed/llm_diff_surprise_features_deepseek_item1a_repair.csv`
- DeepSeek was not rerun; this analysis uses existing post-repair Round 7 features.
- Baseline check: 0.0000002579 max absolute monthly-return difference vs saved Round 7 baseline

## Portfolio Variant Results

|                              | annualized_return   |   sharpe_ratio | max_drawdown   | mean_ic   | mean_rank_ic   | final_cumulative_return   | long_short_positive_rate   |   avg_effective_n_long |   avg_effective_n_short |
|:-----------------------------|:--------------------|---------------:|:---------------|:----------|:---------------|:--------------------------|:---------------------------|-----------------------:|------------------------:|
| tail_20pct                   | 0.15%               |           0.07 | -17.83%        | 1.89%     | 2.88%          | 0.88%                     | 52.86%                     |                   7.18 |                    7.18 |
| tail_30pct                   | 2.61%               |           0.28 | -14.10%        | 1.89%     | 2.88%          | 16.23%                    | 51.43%                     |                  10.77 |                   10.77 |
| rank_weighted                | 3.50%               |           0.39 | -12.19%        | 1.89%     | 2.88%          | 22.19%                    | 55.71%                     |                  13.47 |                   13.47 |
| sector_neutral_rank_weighted | 5.69%               |           0.57 | -14.82%        | 1.89%     | 2.88%          | 38.10%                    | 55.71%                     |                  12.69 |                   12.69 |

## Random Baseline Percentiles

| variant                      | metric                  | strategy_value   | random_mean   | random_p50   | random_p95   | strategy_percentile   |
|:-----------------------------|:------------------------|:-----------------|:--------------|:-------------|:-------------|:----------------------|
| tail_20pct                   | annualized_return       | 0.15%            | -0.62%        | -0.61%       | 8.66%        | 58.00%                |
| tail_20pct                   | sharpe_ratio            | 0.07             | 0.01          | 0.02         | 0.70         | 57.00%                |
| tail_20pct                   | final_cumulative_return | 0.88%            | 1.13%         | -3.53%       | 62.30%       | 58.00%                |
| tail_30pct                   | annualized_return       | 2.61%            | -0.35%        | -0.42%       | 7.62%        | 74.60%                |
| tail_30pct                   | sharpe_ratio            | 0.28             | 0.02          | 0.01         | 0.71         | 74.40%                |
| tail_30pct                   | final_cumulative_return | 16.23%           | 1.19%         | -2.43%       | 53.45%       | 74.60%                |
| rank_weighted                | annualized_return       | 3.50%            | -0.30%        | -0.18%       | 6.52%        | 80.80%                |
| rank_weighted                | sharpe_ratio            | 0.39             | 0.01          | 0.03         | 0.70         | 80.80%                |
| rank_weighted                | final_cumulative_return | 22.19%           | 0.79%         | -1.06%       | 44.53%       | 80.80%                |
| sector_neutral_rank_weighted | annualized_return       | 5.69%            | -0.32%        | -0.23%       | 6.69%        | 91.20%                |
| sector_neutral_rank_weighted | sharpe_ratio            | 0.57             | 0.02          | 0.03         | 0.69         | 91.80%                |
| sector_neutral_rank_weighted | final_cumulative_return | 38.10%           | 0.82%         | -1.31%       | 45.89%       | 91.20%                |

## Baseline 20% Error Analysis

- Months evaluated: 70
- Worst month: 2020-10-31 (-9.06%)
- Best month: 2024-12-31 (7.02%)
- Months with positive rank IC but negative portfolio return: 10
- Correlation between monthly long-short return and rank IC: 0.78

Worst baseline months:

| date                | long_short_return   | rank_ic   | ic      | worst_contributor_ticker   | worst_contributor_side   | worst_contributor_return_contribution   | worst_contributor_rationale                                                                                                                                         |
|:--------------------|:--------------------|:----------|:--------|:---------------------------|:-------------------------|:----------------------------------------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 2020-10-31 00:00:00 | -9.06%              | -16.64%   | -28.58% | RTX                        | short                    | -5.89%                                  | Turkey sanctions and Raytheon merger conditions add downside risk; removal of government investigations is mildly positive.                                         |
| 2024-04-30 00:00:00 | -7.57%              | -18.07%   | -39.79% | NVDA                       | short                    | -3.28%                                  | New export controls on key products and high customer concentration in China imply significant revenue risk, partially offset by removal of China transition costs. |
| 2025-01-31 00:00:00 | -7.18%              | -37.78%   | -39.52% | GOOGL                      | long                     | -1.97%                                  | Changes are primarily boilerplate regulatory updates and generic risk language; no company-specific new information.                                                |
| 2025-11-30 00:00:00 | -6.11%              | -38.63%   | -33.03% | NFLX                       | long                     | -1.53%                                  | No company-specific change reaches materiality 6; content liability reduction is modest positive.                                                                   |
| 2023-11-30 00:00:00 | -5.60%              | -10.54%   | -20.16% | AMD                        | short                    | -2.85%                                  | New specific export restriction on MI250/MI250X to China/Russia; completion of Xilinx/Pensando acquisitions removes uncertainty; ERP upgrade adds operational risk. |
| 2025-10-31 00:00:00 | -5.26%              | -16.72%   | -17.63% | MRK                        | short                    | -2.61%                                  | Negative driven by quantified Gardasil China sales decline; Keytruda exclusivity loss adds weight.                                                                  |
| 2021-10-31 00:00:00 | -5.17%              | -3.68%    | -24.80% | QCOM                       | short                    | -5.25%                                  | Apple's modem self-development and China trade tensions add concrete negative company-specific risks.                                                               |
| 2021-09-30 00:00:00 | -5.06%              | -18.35%   | -15.31% | NVDA                       | short                    | -3.44%                                  | New specific risks: crypto demand volatility, COVID demand correction, tax audits, supply chain breach; outweigh removal of generic piracy risk.                    |

Best baseline months:

| date                | long_short_return   | rank_ic   | ic     |
|:--------------------|:--------------------|:----------|:-------|
| 2024-12-31 00:00:00 | 7.02%               | 44.74%    | 49.75% |
| 2021-06-30 00:00:00 | 6.98%               | 39.28%    | 34.21% |
| 2022-09-30 00:00:00 | 6.60%               | 24.20%    | 28.15% |
| 2020-09-30 00:00:00 | 5.91%               | 22.74%    | 32.71% |
| 2024-06-30 00:00:00 | 5.40%               | 20.54%    | 27.27% |

Average sector exposure/contribution, worst sectors first:

| sector                 | avg_long_weight   | avg_short_weight   | avg_net_weight   | avg_return_contribution   |   active_months |
|:-----------------------|:------------------|:-------------------|:-----------------|:--------------------------|----------------:|
| Communication Services | 12.08%            | 11.54%             | 0.54%            | -0.47%                    |              23 |
| Technology             | 28.92%            | 30.65%             | -1.72%           | -0.39%                    |              70 |
| Financial Services     | 10.03%            | 15.03%             | -5.00%           | -0.06%                    |              66 |
| Consumer Cyclical      | 11.90%            | 12.57%             | -0.67%           | -0.01%                    |              46 |
| Healthcare             | 19.81%            | 23.91%             | -4.10%           | 0.16%                     |              70 |
| Industrials            | 14.45%            | 13.82%             | 0.64%            | 0.29%                     |              61 |
| Consumer Defensive     | 19.99%            | 8.24%              | 11.75%           | 0.32%                     |              61 |

Largest negative holding-level contributions inside the worst months:

| date                | ticker   | sector                 | side   | weight   |   signal | forward_return   | return_contribution   |   raw_llm_diff_surprise_signal |   diff_similarity | diff_rationale                                                                                                                                                      |
|:--------------------|:---------|:-----------------------|:-------|:---------|---------:|:-----------------|:----------------------|-------------------------------:|------------------:|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 2020-10-31 00:00:00 | RTX      | Industrials            | short  | 17.86%   |    -2.98 | 32.99%           | -5.89%                |                          -3.25 |              0.85 | Turkey sanctions and Raytheon merger conditions add downside risk; removal of government investigations is mildly positive.                                         |
| 2021-10-31 00:00:00 | QCOM     | Technology             | short  | 14.71%   |    -4.4  | 35.72%           | -5.25%                |                          -6.5  |              0.57 | Apple's modem self-development and China trade tensions add concrete negative company-specific risks.                                                               |
| 2020-10-31 00:00:00 | AMD      | Technology             | short  | 17.86%   |    -5.09 | 23.07%           | -4.12%                |                          -6.5  |              0.84 | Addition of Entity List and GF funding dependence are significant negative company-specific risks.                                                                  |
| 2021-10-31 00:00:00 | NVDA     | Technology             | short  | 14.71%   |    -2.17 | 27.81%           | -4.09%                |                          -4.25 |              0.63 | New specific risks: crypto demand volatility, COVID demand correction, tax audits, supply chain breach; outweigh removal of generic piracy risk.                    |
| 2020-10-31 00:00:00 | ABBV     | Healthcare             | short  | 17.86%   |    -2.23 | 22.89%           | -4.09%                |                          -4    |              0.89 | Added acquisition risks for Allergan deal and patent expiration risks specific to AbbVie's product portfolio.                                                       |
| 2021-09-30 00:00:00 | NVDA     | Technology             | short  | 14.71%   |    -2.9  | 23.42%           | -3.44%                |                          -4.25 |              0.63 | New specific risks: crypto demand volatility, COVID demand correction, tax audits, supply chain breach; outweigh removal of generic piracy risk.                    |
| 2024-04-30 00:00:00 | NVDA     | Technology             | short  | 12.20%   |    -3.94 | 26.89%           | -3.28%                |                          -5.25 |              0.61 | New export controls on key products and high customer concentration in China imply significant revenue risk, partially offset by removal of China transition costs. |
| 2024-04-30 00:00:00 | QCOM     | Technology             | short  | 12.20%   |    -4.9  | 23.54%           | -2.87%                |                          -5.5  |              0.86 | New disclosures on Huawei licensing loss and China payment risks are concrete negative company-specific changes.                                                    |
| 2023-11-30 00:00:00 | AMD      | Technology             | short  | 13.16%   |    -2.74 | 21.67%           | -2.85%                |                          -4.5  |              0.77 | New specific export restriction on MI250/MI250X to China/Russia; completion of Xilinx/Pensando acquisitions removes uncertainty; ERP upgrade adds operational risk. |
| 2025-10-31 00:00:00 | MRK      | Healthcare             | short  | 11.90%   |    -2.99 | 21.92%           | -2.61%                |                          -3.75 |              0.83 | Negative driven by quantified Gardasil China sales decline; Keytruda exclusivity loss adds weight.                                                                  |
| 2021-09-30 00:00:00 | MSFT     | Technology             | short  | 14.71%   |    -2.29 | 17.63%           | -2.59%                |                          -3.75 |              0.86 | Addition of Nobelium/Solorigate attack details and supply chain risks; generic pandemic and macroeconomic boilerplate.                                              |
| 2021-09-30 00:00:00 | MRK      | Healthcare             | short  | 14.71%   |    -3.19 | 17.23%           | -2.53%                |                          -3.5  |              0.73 | Added disclosure of Zerbaxa product recall in manufacturing risk, company-specific negative.                                                                        |
| 2021-09-30 00:00:00 | UPS      | Industrials            | short  | 11.76%   |    -1.56 | 17.23%           | -2.03%                |                          -3.25 |              0.71 | Impairment charge from divestiture is company-specific and negative; other changes are boilerplate or sector-wide.                                                  |
| 2024-04-30 00:00:00 | NFLX     | Communication Services | short  | 12.20%   |    -2.16 | 16.52%           | -2.01%                |                          -3.75 |              0.86 | Labor strike disclosure is company-specific and significant; ad risk expansion less material; high boilerplate.                                                     |
| 2025-01-31 00:00:00 | GOOGL    | Communication Services | long   | 11.90%   |     1.88 | -16.54%          | -1.97%                |                           0    |              0.79 | Changes are primarily boilerplate regulatory updates and generic risk language; no company-specific new information.                                                |
| 2020-10-31 00:00:00 | MA       | Financial Services     | short  | 10.71%   |    -1.32 | 16.58%           | -1.78%                |                          -3.25 |              0.89 | Primarily boilerplate updates; company-specific additions of government contract and indemnification risks, but limited quantitative impact.                        |
| 2021-09-30 00:00:00 | SPGI     | Financial Services     | short  | 14.71%   |    -2.54 | 11.60%           | -1.71%                |                          -3.75 |              0.68 | Addition of explicit risks related to the IHS Markit merger integration and failure to close, which is company-specific and negative.                               |
| 2025-10-31 00:00:00 | GOOGL    | Communication Services | short  | 11.90%   |    -2.87 | 13.87%           | -1.65%                |                          -6.25 |              0.79 | Two major antitrust rulings increase regulatory and financial risk for Google's core businesses.                                                                    |
| 2023-11-30 00:00:00 | QCOM     | Technology             | short  | 13.16%   |    -4.25 | 12.07%           | -1.59%                |                          -5.5  |              0.86 | New disclosures on Huawei licensing loss and China payment risks are concrete negative company-specific changes.                                                    |
| 2024-04-30 00:00:00 | AAPL     | Technology             | short  | 12.20%   |    -2.72 | 13.02%           | -1.59%                |                          -4    |              0.85 | App Store antitrust investigations in Europe represent a new, concrete regulatory risk; removal of retail and COVID risks provides minor offset.                    |

## Interpretation

- If a wider 30% tail improves return, the original 20% portfolio was likely too sensitive to noisy extremes.
- If rank-weighting improves return, the signal contains broad ordering information but weak tail separation.
- If sector-neutral rank weighting improves return, part of the baseline loss likely came from sector concentration rather than stock selection.
- If all variants stay weak versus random, the main issue is signal design/extraction quality rather than portfolio construction.

Generated CSVs:

- `round7_portfolio_variant_metrics.csv`
- `round7_portfolio_variant_significance.csv`
- `round7_portfolio_variant_random_trials.csv`
- `round7_monthly_error_analysis.csv`
- `round7_worst_month_holdings.csv`
- `round7_sector_exposure_summary.csv`
- `round7_portfolio_variant_cumulative_returns.csv`
- `round7_portfolio_variant_cumulative_returns.png`
