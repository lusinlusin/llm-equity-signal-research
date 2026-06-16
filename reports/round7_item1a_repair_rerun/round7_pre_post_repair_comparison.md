# Round 7 Pre/Post Item 1A Repair Comparison

Old Round 6 used pre-repair SEC Item 1A text. Round 7 uses regenerated raw text and a full 211-row DeepSeek diff-surprise rerun.

## Data Repair Scope

- Raw rows changed: 122 / 293.
- Pairs with similarity change > 0.01: 91 / 211.
- Old similarity range/median: 0.008 / 0.718.
- New similarity range/median: 0.257 / 0.792.
- Common old/new keys: 210; old-only keys: 1; new-only keys: 1. The key change is the ORCL 2020 prior pairing repair.
- Common final LLM signal changed: 104 / 210.

## Strategy Metrics

| signal                                     | old_round6_ann_return   | new_round7_ann_return   | delta_ann_return   |   old_round6_sharpe |   new_round7_sharpe |   delta_sharpe | old_round6_mean_ic   | new_round7_mean_ic   | delta_mean_ic   | old_round6_final_cum   | new_round7_final_cum   | delta_final_cum   |
|:-------------------------------------------|:------------------------|:------------------------|:-------------------|--------------------:|--------------------:|---------------:|:---------------------|:---------------------|:----------------|:-----------------------|:-----------------------|:------------------|
| before_text_signal                         | 2.89%                   | 1.79%                   | -1.11%             |                0.28 |                0.19 |          -0.1  | 2.48%                | 0.23%                | -2.25%          | 18.10%                 | 10.88%                 | -7.22%            |
| enhanced_text_signal                       | 2.90%                   | 4.76%                   | 1.86%              |                0.3  |                0.32 |           0.02 | 2.67%                | 1.59%                | -1.08%          | 18.17%                 | 31.18%                 | 13.02%            |
| enhanced_sector_size_neutral               | 5.32%                   | -4.55%                  | -9.87%             |                0.48 |               -0.33 |          -0.81 | 2.00%                | -1.16%               | -3.16%          | 35.30%                 | -23.81%                | -59.11%           |
| deepseek_diff_surprise_signal              | -1.91%                  | -1.00%                  | 0.91%              |               -0.14 |               -0.01 |           0.13 | -0.92%               | 1.35%                | 2.27%           | -10.64%                | -5.68%                 | 4.96%             |
| deepseek_diff_surprise_sector_size_neutral | 4.46%                   | 0.15%                   | -4.31%             |                0.43 |                0.07 |          -0.36 | 0.59%                | 1.89%                | 1.31%           | 28.98%                 | 0.88%                  | -28.11%           |
| random_no_text_persistent_neutralized      | -2.37%                  | -9.83%                  | -7.45%             |               -0.1  |               -0.57 |          -0.47 | -0.86%               | -1.67%               | -0.81%          | -13.07%                | -45.30%                | -32.23%           |

## Neutralized Diff-Surprise vs Random Baseline

| metric                  | old_strategy_value   | new_strategy_value   | old_percentile   | new_percentile   | old_empirical_p_value   | new_empirical_p_value   |
|:------------------------|:---------------------|:---------------------|:-----------------|:-----------------|:------------------------|:------------------------|
| annualized_return       | 4.46%                | 0.15%                | 82.20%           | 56.40%           | 17.80%                  | 43.60%                  |
| sharpe_ratio            | 0.43                 | 0.07                 | 84.60%           | 56.40%           | 15.40%                  | 43.60%                  |
| mean_ic                 | 0.59%                | 1.89%                | 62.00%           | 83.60%           | 38.00%                  | 16.40%                  |
| mean_rank_ic            | 1.74%                | 2.88%                | 77.60%           | 91.20%           | 22.40%                  | 8.80%                   |
| final_cumulative_return | 28.98%               | 0.88%                | 82.20%           | 56.40%           | 17.80%                  | 43.60%                  |

## Interpretation

- The pre-repair Round 6 LLM result does not survive the Item 1A repair.
- The neutralized diff-surprise signal fell from 4.46% annualized return / 0.43 Sharpe / 28.98% final cumulative return to 0.15% / 0.07 / 0.88%.
- The deterministic sector/size-neutral baseline also changed materially and became negative, so pre-repair deterministic results are not reliable current evidence either.
- Post-repair IC and rank IC remain positive, but portfolio return significance is near random; this suggests the signal may rank some monthly cross-sections but is not yet strong enough as a tradable long-short rule.
