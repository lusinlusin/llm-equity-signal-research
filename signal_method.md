# Signal Method Iteration Log

Last updated: 2026-06-11

This note summarizes each major signal iteration run so far: method, universe, change versus the prior round, performance, and what the result implies.

## 1. Iteration Summary

| Round | Main method tested | Universe / coverage | Change versus prior round | Main takeaway |
|---|---|---|---|---|
| 1 | Deterministic dictionary signals: `before_text_signal`, `enhanced_text_signal`, `enhanced_sector_size_neutral` | 211 SEC 10-K Item 1A records, 42 tickers, 2020-2025, 70 backtest periods | Built the real SEC text-signal pipeline and moved beyond a random placeholder. Added enhanced finance dictionaries and sector/size neutralization. | Best result is `enhanced_sector_size_neutral`: 5.92% annualized return, 0.50 Sharpe, 39.89% final cumulative return. |
| 2 | DeepSeek absolute LLM signal: `deepseek_llm_text_signal` | 211 LLM feature rows, 42 tickers, 72 signal months, 70 backtest periods | Added real DeepSeek extraction on each single filing. Prompt scored absolute sentiment/risk severity from one Item 1A section. | Failed as alpha: -9.11% annualized return, -0.51 Sharpe, -42.73% final cumulative return. |
| 3 | DeepSeek YoY relative LLM signal, initial internal-prior version | 169 YoY feature rows, 40 tickers, 60 signal months, 58 backtest periods | Changed prompt from absolute risk to current-vs-prior filing comparison, but only used prior filings already present inside the 211-row current dataset. | Looked promising on the smaller sample: 5.56% annualized return, 0.48 Sharpe, 29.90% final cumulative return. |
| 4 | DeepSeek YoY relative LLM signal, completed prior-context version | 211 YoY feature rows, 42 tickers, YoY signal itself covers 72 signal months / 42 tickers; strict all-signal comparison covers 71 months / 42 tickers; 70 backtest periods | Downloaded 82 prior-context 10-K records from 2018-2024. Ran only the 42 missing YoY LLM rows with `--resume`, then overwrote the prior 169-row output. | Performance dropped: 1.09% annualized return, 0.15 Sharpe, 6.55% final cumulative return. Not significant versus random. |
| 5 | Soundness-fix evaluation: fractional tie handling, persistent random baseline, and LLM sector/size neutralization | Same completed 211-row / 42-ticker YoY universe; strict all-signal comparison covers 71 months / 42 tickers; 70 backtest periods | Fixed ticker-order tie breaking, changed random baseline from iid monthly draws to persistent signal-spell draws, added sector/size-neutral DeepSeek absolute and YoY signals, and removed numeric anchors from future LLM prompts. | Current best signal remains `enhanced_sector_size_neutral`: 5.32% annualized return, 0.48 Sharpe, 35.30% final cumulative return. Neutralized YoY LLM is only 0.51% annualized return, 0.10 Sharpe, and 56th percentile versus persistent neutralized random. |
| 6 | Prompt redesign in two stages: (A) de-anchored YoY prompt pilot, (B) diff-surprise prompt on deterministic YoY diffs | Stage A: 30 pilot pairs. Stage B: 30-pair pilot, then full 211 rows / 42 tickers; strict comparison 71 months / 70 backtest periods | Stage A removed numeric anchors only and failed the pilot gate (8 unique signal values in 30 rows). Stage B changed the task: deterministic Item 1A block diff first, LLM scores only the changed sections for company-specific investable surprise with a zero base rate, integer scales, and anonymized prompts. | Stage B passed the pilot gate and ran in full. Neutralized diff-surprise signal (after the 8.8 formula fix): 4.46% annualized return, 0.43 Sharpe, 28.98% final cumulative return — the best LLM signal so far (old neutralized YoY: 0.10 Sharpe), at the 82-85th percentile versus persistent neutralized random, within 0.05 Sharpe of `enhanced_sector_size_neutral` (0.48) but not significant at 95%. |

## 2. Shared Backtest Setup

All main comparisons use the same broad backtest design:

- Text source: SEC 10-K Item 1A Risk Factors.
- Alignment: use SEC `filing_date`, then forward-fill each ticker's latest available filing signal to month-end dates.
- Return target: 1-month forward equity return.
- Portfolio: long top quintile and short bottom quintile by signal each month. Rounds 1-4 used ticker-order tie breaking; Round 5 uses fractional boundary tie handling so tied scores are not selected by ticker alphabetic order.
- Metrics: annualized return, Sharpe ratio, max drawdown, mean IC, rank IC, final cumulative return.
- Sanity check: compare against random no-text signals on the same coverage.

The current completed current-filing universe is:

- 211 current SEC 10-K Item 1A records.
- 42 tickers.
- Filing date range: 2020-01-21 to 2025-12-18.
- YoY prior context: 82 additional prior 10-K records from 2018-01-22 to 2024-02-02.

## 3. Round 1: Deterministic Dictionary Signals

### 3.1 Method

This round used transparent, deterministic text scoring. No LLM was used.

### `before_text_signal`

This is the original dictionary signal. It counts:

- positive terms
- negative terms
- uncertainty terms
- growth terms
- margin-pressure terms

Intermediate scores:

```text
sentiment_score =
  (positive_hits - negative_hits)
  / (positive_hits + negative_hits + 1)

uncertainty_score =
  uncertainty_hits
  / (uncertainty_hits + positive_hits + negative_hits + 1)

growth_outlook_score =
  growth_hits
  / (growth_hits + negative_hits + 1)

margin_pressure_score =
  margin_hits
  / (margin_hits + positive_hits + 1)
```

Final signal:

```text
text_signal =
  sentiment_score
  + 0.50 * growth_outlook_score
  - 0.50 * uncertainty_score
  - 0.75 * margin_pressure_score
```

### `enhanced_text_signal`

This adds finance-specific dictionaries:

- financial positive terms
- financial negative terms
- risk intensity terms

It also normalizes some counts per 1,000 words.

Intermediate scores:

```text
financial_sentiment_score =
  ((positive_hits + financial_positive_hits)
   - (negative_hits + financial_negative_hits))
  / (positive_hits + financial_positive_hits
     + negative_hits + financial_negative_hits + 1)

uncertainty_rate =
  uncertainty_hits / word_count * 1000

risk_intensity_rate =
  (risk_intensity_hits + financial_negative_hits) / word_count * 1000

growth_rate =
  (growth_hits + financial_positive_hits) / word_count * 1000

margin_pressure_rate =
  margin_hits / word_count * 1000
```

Final signal:

```text
enhanced_text_signal =
  financial_sentiment_score
  + 0.08 * growth_rate
  - 0.10 * uncertainty_rate
  - 0.10 * risk_intensity_rate
  - 0.08 * margin_pressure_rate
```

### `enhanced_sector_size_neutral`

This starts from `enhanced_text_signal`, then neutralizes sector and size exposure cross-sectionally each month:

```text
enhanced_text_signal_i,t =
  intercept_t
  + sector_dummies_i,t
  + standardized_log_market_cap_i,t
  + residual_i,t

enhanced_sector_size_neutral_i,t = residual_i,t
```

If the cross-section is too small for the full regression, the code falls back to sector demeaning. Current sector and market-cap metadata are static, not point-in-time historical metadata.

### 3.2 Change Versus Prior Round

This was the first full real-text robustness round. It moved the project from a placeholder random signal to actual SEC text-derived signals.

### 3.3 Results

| signal | Ann. Return | Sharpe | Max DD | Mean IC | Final Cum |
|---|---:|---:|---:|---:|---:|
| `before_text_signal` | 3.22% | 0.31 | -20.83% | 2.48% | 20.28% |
| `enhanced_text_signal` | 3.10% | 0.31 | -13.92% | 2.67% | 19.50% |
| `enhanced_sector_size_neutral` | 5.92% | 0.50 | -15.35% | 2.00% | 39.89% |

Interpretation:

The best model in this round is `enhanced_sector_size_neutral`. It improves on both raw dictionary variants because it keeps the finance-specific and length-normalized text features while removing simple sector and size exposure. The better drawdown versus `before_text_signal` also suggests that some of the original signal's behavior came from broad cross-sectional tilts rather than pure text information.

Limitations:

- The dictionaries are hand-built and may miss context, negation, and firm-specific meaning.
- Sector and market-cap metadata are current static metadata, not point-in-time historical metadata.
- The signal is still based on annual 10-K risk disclosures, so it is slow-moving.
- The result is better than most random baselines but not strong enough to be treated as a production alpha signal.

Best next step from this round: add a real LLM extraction model to test whether contextual understanding can improve on dictionary counts, while keeping the same point-in-time backtest and random-baseline framework.

## 4. Round 2: DeepSeek Absolute LLM Signal

### 4.1 Method

This round added real DeepSeek extraction on each single SEC Item 1A text independently.

Implementation details:

- LLM provider: DeepSeek, called through the OpenAI-compatible chat completions API.
- Model used in the full run: `deepseek-v4-flash`.
- Base URL: `https://api.deepseek.com`.
- Input text: one current SEC 10-K Item 1A Risk Factors section.
- Input truncation: only the first 12,000 characters of the filing text are sent to the LLM.
- Response mode: `response_format={"type": "json_object"}`.
- Temperature: `0.0`.
- Max output tokens: `800`.
- Retry behavior: up to 3 retries for empty, unparsable, or schema-invalid responses.

Prompt objective:

```text
Extract a point-in-time equity signal from SEC 10-K Item 1A Risk Factors text.
Return JSON only.
```

Requested JSON fields:

```text
sentiment_score          range [-1, 1]
uncertainty_score        range [0, 1]
growth_outlook_score     range [0, 1]
margin_pressure_score    range [0, 1]
risk_severity_score      range [0, 1]
confidence               range [0, 1]
rationale                short text explanation
```

Prompt scoring guide:

- `sentiment_score`: -1 is very negative for expected stock returns, 0 is neutral, 1 is very positive.
- `uncertainty_score`: 0 means little uncertainty, 1 means high uncertainty.
- `growth_outlook_score`: 0 means weak or no growth evidence, 1 means strong growth evidence.
- `margin_pressure_score`: 0 means little margin pressure, 1 means severe margin pressure.
- `risk_severity_score`: 0 means generic/low severity risks, 1 means severe business or financial risk.
- `confidence`: 0 means weak evidence, 1 means strong evidence.

Final signal:

```text
llm_text_signal =
  sentiment_score
  + 0.50 * growth_outlook_score
  - 0.50 * uncertainty_score
  - 0.75 * margin_pressure_score
  - 0.50 * risk_severity_score
```

### 4.2 Change Versus Round 1

The signal moved from transparent dictionary counts to LLM-generated structured scores. The universe stayed at 211 rows / 42 tickers. The prompt still evaluated each filing in isolation, so it mostly measured absolute risk severity.

### 4.3 Results

| signal | Ann. Return | Sharpe | Max DD | Mean IC | Final Cum |
|---|---:|---:|---:|---:|---:|
| `original_text_signal` | 3.22% | 0.31 | -20.83% | 2.48% | 20.28% |
| `deepseek_llm_text_signal` | -9.11% | -0.51 | -53.63% | -2.15% | -42.73% |
| `random_no_text` | -0.34% | 0.05 | -34.71% | -0.81% | -1.96% |

Interpretation:

The new DeepSeek absolute LLM model performed worse than the original deterministic text signal and worse than the random baseline. The most likely reason is prompt design: the model scored absolute risk severity inside a section that is legally designed to describe risks. Companies with more complete or severe risk disclosure were mechanically pushed toward lower signal values, even when that disclosure was boilerplate, already known, or not predictive of next-month returns.

Limitations:

- The prompt evaluates one filing in isolation, with no prior-year comparison.
- It does not separate company-specific risk from sector-wide or market-wide risk.
- It penalizes `risk_severity_score` directly, which may mostly measure disclosure intensity rather than investable bad news.
- It only reads the first 12,000 characters, so it may miss later risk sections or context.

Potential solutions:

- Replace absolute risk scoring with current-vs-prior filing comparison.
- Ask the model for incremental stock-price relevance rather than legal risk severity.
- Add peer-relative context so structurally risky sectors are not mechanically penalized.
- Keep the old deterministic signal as a baseline because it is currently more robust.

Best next step from this round: redesign the LLM prompt around year-over-year disclosure changes and rerun on the same SEC universe where possible.

## 5. Round 3: DeepSeek YoY Relative LLM Signal, Initial 169-Row Version

### 5.1 Method

This round changed the LLM task from absolute risk scoring to current-vs-prior filing comparison.

Implementation details:

- LLM provider: DeepSeek, called through the OpenAI-compatible chat completions API.
- Model used in the run: `deepseek-v4-flash`.
- Base URL: `https://api.deepseek.com`.
- Input text: one current SEC 10-K Item 1A Risk Factors section plus one prior filing Item 1A section for the same ticker.
- Input truncation: the current filing is clipped to the first 12,000 characters, and the prior filing is also clipped to the first 12,000 characters.
- Metadata included in the prompt: ticker, company name, sector, current filing date, prior filing date.
- Response mode: `response_format={"type": "json_object"}`.
- Temperature: `0.0`.
- Max output tokens: `800`.
- Retry behavior: at least 6 attempts for empty, unparsable, or schema-invalid responses in the YoY client.

Prompt objective:

```text
Evaluate whether the latest SEC 10-K Item 1A Risk Factors update contains
incrementally positive or negative information for the company's stock price.
Do not score absolute risk level. Focus on incremental changes versus the prior filing.
```

Requested JSON fields:

```text
risk_change_score          range [-1, 1]
new_material_risk_score    range [0, 1]
risk_mitigation_score      range [0, 1]
peer_relative_risk_score   range [-1, 1]
direction_score            range [-1, 1]
impact_label               positive / negative / neutral / uncertain
confidence                 range [0, 1]
rationale                  short text explanation
```

Prompt scoring guide:

- `risk_change_score`: -1 means risks clearly worsened, 0 means little change, 1 means risks clearly improved.
- `new_material_risk_score`: 0 means no important new risk, 1 means severe new or intensified material risks.
- `risk_mitigation_score`: 0 means no risk mitigation evidence, 1 means clear mitigation or reduced risk language.
- `peer_relative_risk_score`: -1 means unusually worse than a typical company in this sector, 0 means typical, 1 means unusually better.
- `direction_score`: 1 means incrementally positive for expected stock returns over the next 1-3 months, 0 means neutral or uncertain, -1 means incrementally negative.
- `confidence`: 0 means weak evidence, 1 means strong evidence.

Final signal:

```text
llm_yoy_relative_signal =
  direction_score
  + 0.50 * risk_change_score
  + 0.50 * risk_mitigation_score
  + 0.50 * peer_relative_risk_score
  - 0.75 * new_material_risk_score
```

### 5.2 Change Versus Round 2

The model no longer scored one filing in isolation. It compared current Item 1A text against the prior Item 1A text for the same company. This was meant to reduce the absolute-risk bias.

However, this first version only used prior filings already available inside `data/raw/sec_10k_risk_factors.csv`. As a result, each ticker's first current filing had no prior and was dropped. The universe shrank from 211 rows / 42 tickers to 169 rows / 40 tickers.

### 5.3 Results

This intermediate report was later overwritten by the completed 211-row run. The table below records the 169-row run used for diagnosis.

| signal | Ann. Return | Sharpe | Max DD | Mean IC | Final Cum |
|---|---:|---:|---:|---:|---:|
| `before_text_signal` | 3.07% | 0.30 | -11.64% | 2.26% | 15.71% |
| `enhanced_text_signal` | -1.41% | -0.07 | -13.43% | 1.50% | -6.63% |
| `enhanced_sector_size_neutral` | 0.69% | 0.12 | -13.41% | -0.48% | 3.38% |
| `deepseek_absolute_llm_text_signal` | -10.64% | -0.68 | -52.71% | -2.50% | -41.94% |
| `deepseek_yoy_relative_signal` | 5.56% | 0.48 | -29.08% | -1.00% | 29.90% |
| `random_no_text` | 4.74% | 0.38 | -35.14% | 1.83% | 25.07% |

Interpretation:

The new YoY LLM model looked better than the absolute DeepSeek model in this round. It also beat the deterministic signals on final cumulative return within this smaller window. The likely reason is that current-vs-prior comparison reduced the absolute-risk bias from Round 2: the model no longer punished every company simply because Item 1A is risk-heavy.

However, this result had important limitations:

- The universe was incomplete: 169 rows / 40 tickers instead of 211 rows / 42 tickers.
- Each ticker's first current filing was dropped because there was no prior filing inside the original dataset.
- The random single path was also strong in this window, so the result could be sample-window luck.
- Mean IC was still negative at -1.00%, so the cross-sectional ranking quality was not clearly reliable.

Best next step from this round: restore the original 211-row / 42-ticker universe by downloading prior filings from before the first current filing, then rerun only the missing YoY LLM rows and retest on the full intended coverage.

## 6. Round 4: DeepSeek YoY Relative LLM Signal, Completed 211-Row Version

### 6.1 Method

The YoY LLM prompt and formula stayed the same as Round 3.

The data construction changed:

- Downloaded prior 10-K Item 1A context for each ticker's first current filing.
- Saved prior context to `data/raw/sec_10k_risk_factors_prior_context.csv`.
- Prior context rows: 82.
- Prior context tickers: 42.
- Prior context filing range: 2018-01-22 to 2024-02-02.
- Used these prior filings only as comparison context, not as additional current signal records.
- Used `--resume` to run only the missing 42 YoY DeepSeek rows.
- Overwrote `data/processed/llm_yoy_relative_features_deepseek.csv` from 169 rows to 211 rows.

One caveat: `ORCL 2020` uses 2018 as prior instead of 2019 because the 2019 ORCL Item 1A section could not be reliably extracted.

### 6.2 Change Versus Round 3

The universe was restored to the old 211-row / 42-ticker current filing universe. The apparent small-sample outperformance from Round 3 was retested on the full intended coverage.

### 6.3 Results

| signal | Ann. Return | Sharpe | Max DD | Mean IC | Final Cum |
|---|---:|---:|---:|---:|---:|
| `before_text_signal` | 3.22% | 0.31 | -20.83% | 2.48% | 20.28% |
| `enhanced_text_signal` | 3.10% | 0.31 | -13.92% | 2.67% | 19.50% |
| `enhanced_sector_size_neutral` | 5.92% | 0.50 | -15.35% | 2.00% | 39.89% |
| `deepseek_absolute_llm_text_signal` | -9.11% | -0.51 | -53.63% | -2.15% | -42.73% |
| `deepseek_yoy_relative_signal` | 1.09% | 0.15 | -25.96% | -2.20% | 6.55% |
| `random_no_text` | -8.42% | -0.52 | -48.41% | -0.49% | -40.13% |

YoY signal versus 500 random trials:

| metric | YoY value | Random mean | Random p50 | Random p95 | YoY percentile |
|---|---:|---:|---:|---:|---:|
| Annualized return | 1.09% | -0.95% | -1.11% | 9.23% | 66.20% |
| Sharpe ratio | 0.15 | 0.00 | -0.01 | 0.68 | 66.40% |
| Mean IC | -2.20% | -0.06% | -0.04% | 3.35% | 15.00% |
| Final cumulative return | 6.55% | -0.59% | -6.30% | 67.33% | 66.20% |

Interpretation:

The completed YoY LLM signal is better than the absolute DeepSeek signal, but it is not strong enough to treat as a useful alpha signal. It has positive final cumulative return, but it is weaker than all deterministic text signals and only reaches about the 66th percentile versus random on annualized return and Sharpe.

Why the result worsened versus Round 3:

- Round 3 was partly a sample-selection artifact. The initial YoY run dropped each ticker's first current filing. After prior context was added, 42 first-current rows entered the sample.
- Many of those newly added rows are from 2020/2021, when companies added COVID, supply-chain, macro, and operational disruption disclosures.
- The LLM often scored those new disclosures as strongly negative, but those risks were broad market information and not necessarily negative alpha.
- The prompt still rewards legal-disclosure interpretation more than investable interpretation. Even though it says not to score absolute risk, it still asks whether risks worsened and penalizes `new_material_risk_score` directly.
- Economy-wide risks are not separated from company-specific risks. COVID, inflation, supply-chain issues, rates, and regulation can appear across many companies at once and may already be priced.
- Ranking quality is weak: mean IC is -2.20% and mean rank IC is -0.99%.
- SEC parser quality still matters. The parser was improved, but `ORCL 2020` still uses 2018 prior rather than 2019 prior because 2019 Item 1A could not be reliably extracted.

Potential solutions:

- Do a YoY LLM error-analysis report before another prompt run: inspect 2020 and 2023, worst months, long/short holdings, and top/bottom rationales.
- Redesign prompt v2 around investable surprise rather than risk expansion.
- Add fields that separate company-specific risk from market-wide boilerplate, sector-wide risk, already-priced risk, and disclosure-quality change.
- Change the formula so market-wide and sector-wide risks are diagnostic fields, not direct alpha penalties.
- Add a sector/size-neutral version of the YoY LLM signal to test whether the raw LLM signal is mostly sector or size exposure.
- Keep future prompt tests on the same 211-row / 42-ticker universe to avoid repeating the Round 3 sample-selection issue.

## 7. Round 5: Soundness-Fix Evaluation

### 7.1 Method

Round 5 did not rerun DeepSeek extraction. It reused the existing processed LLM feature files:

- `data/processed/llm_text_features_deepseek.csv`
- `data/processed/llm_yoy_relative_features_deepseek.csv`

The goal was to test whether several evaluation-design issues were distorting the Round 4 conclusion before spending API cost on a new prompt run.

Changes implemented:

- Portfolio tie handling changed from `rank(method="first")` to fractional boundary inclusion.
- If multiple tickers tie at the top/bottom quintile boundary, the full tied group is included with fractional weights instead of selecting by ticker order.
- Random baseline changed from independent monthly random draws to persistent random draws that follow the target signal's non-missing spells and updates.
- Random baseline used for the main Round 5 significance test is also sector/size neutralized.
- Added `deepseek_absolute_sector_size_neutral`.
- Added `deepseek_yoy_relative_sector_size_neutral`.
- Updated future LLM prompts to remove numeric example anchors and omit ticker/company/date identifiers from the prompt text.

Important caveat:

The prompt change affects future LLM extraction only. The Round 5 metrics below still use the old DeepSeek output files, because no new DeepSeek API run was executed.

Output folder:

```text
reports/round5/
```

Key files:

- `round5_soundness_metrics.csv`
- `round5_soundness_cumulative_returns.csv`
- `round5_soundness_cumulative_returns.png`
- `round5_yoy_neutralized_random_significance.csv`
- `round5_persistent_neutralized_random_baseline_trials.csv`
- `round5_soundness_comparison.md`

### 7.2 Change Versus Round 4

Round 4 asked whether the completed YoY LLM signal worked on the full 211-row universe. Round 5 asks a different question:

```text
After fixing evaluation issues, does the existing LLM signal still look useful?
```

The main evaluation changes were:

- no ticker-order tie breaking;
- no iid monthly random baseline for an annual filing signal;
- LLM signals tested both raw and sector/size neutralized;
- random benchmark matched to the persistence and neutralization of the target signal.

### 7.3 Results

| signal | Ann. Return | Sharpe | Max DD | Mean IC | Final Cum |
|---|---:|---:|---:|---:|---:|
| `before_text_signal` | 2.89% | 0.28 | -17.54% | 2.48% | 18.10% |
| `enhanced_text_signal` | 2.90% | 0.30 | -10.84% | 2.67% | 18.17% |
| `enhanced_sector_size_neutral` | 5.32% | 0.48 | -16.55% | 2.00% | 35.30% |
| `deepseek_absolute_llm_text_signal` | -8.45% | -0.47 | -53.72% | -2.15% | -40.25% |
| `deepseek_absolute_sector_size_neutral` | -3.53% | -0.20 | -41.53% | 0.95% | -18.94% |
| `deepseek_yoy_relative_signal` | 0.67% | 0.11 | -26.72% | -2.20% | 3.95% |
| `deepseek_yoy_relative_sector_size_neutral` | 0.51% | 0.10 | -28.21% | 1.32% | 3.02% |
| `random_no_text_persistent_neutralized` | -4.97% | -0.29 | -39.35% | -0.61% | -25.72% |

Neutralized YoY signal versus 500 persistent neutralized random trials:

| metric | YoY neutralized value | Random mean | Random p50 | Random p95 | YoY percentile |
|---|---:|---:|---:|---:|---:|
| Annualized return | 0.51% | -0.44% | -0.42% | 9.46% | 56.20% |
| Sharpe ratio | 0.10 | 0.03 | 0.04 | 0.69 | 55.80% |
| Mean IC | 1.32% | 0.19% | 0.14% | 3.24% | 72.80% |
| Mean rank IC | 1.91% | 0.18% | 0.16% | 3.20% | 82.80% |
| Final cumulative return | 3.02% | 1.96% | -2.40% | 69.47% | 56.20% |

Interpretation:

Round 5 makes the evaluation more defensible, but it does not rescue the current LLM signal.

The deterministic `enhanced_sector_size_neutral` signal remains the best strategy. Its Sharpe drops slightly from Round 4 because the portfolio construction no longer breaks ties by ticker order, but it still has the strongest return profile among the tested signals.

The absolute DeepSeek signal improves after sector/size neutralization. Raw absolute DeepSeek is still strongly negative, but neutralization moves final cumulative return from -40.25% to -18.94% and mean IC from -2.15% to 0.95%. This suggests part of the absolute LLM failure was sector/size exposure rather than pure stock-level information. However, the strategy remains negative and is not useful as alpha.

The YoY DeepSeek signal also improves in ranking quality after neutralization: mean IC changes from -2.20% raw to 1.32% neutralized, and mean rank IC becomes 1.91%. But the portfolio return is still economically weak: only 0.51% annualized return, 0.10 Sharpe, and 3.02% final cumulative return.

The random comparison is now stricter than Round 4 because random scores persist like filing-based signals and are sector/size neutralized. Under this benchmark, neutralized YoY DeepSeek is only around the 56th percentile on annualized return and Sharpe. Its IC percentiles are better, but that does not translate into a strong long-short return.

Main conclusion:

```text
The existing LLM outputs contain some weak rank information after neutralization,
but not enough to justify treating them as a robust tradable signal.
```

## 8. Round 6: Prompt Redesign — De-Anchored Pilot and Diff-Surprise Full Run

Round 6 has two stages. Stage A tested whether removing numeric example anchors alone would fix the YoY prompt; it failed its pilot gate and no full run was spent on it. Stage B changed the task itself — deterministic text diffs plus an investable-surprise prompt — passed its pilot gate, and ran in full with a backtest comparison.

### 8.1 Stage A Method: Remove Numeric Anchors Only

Round 6 tested whether removing numeric examples from the YoY prompt would produce less anchored and more cross-sectionally informative LLM scores.

The pilot used 30 current/prior filing pairs sampled from the completed 211-row YoY universe:

- years covered: 2020-2025;
- sample design: each year sampled across old YoY signal quantiles;
- sample key file: `reports/round6/round6_pilot_sample_keys.csv`;
- new pilot output: `data/processed/llm_yoy_relative_features_deanchored_pilot.csv`;
- old-prompt comparison subset: `reports/round6/round6_old_prompt_pilot_sample_features.csv`.

The extraction used the updated YoY prompt in `src/llm/yoy_relative_prompts.py`:

- removed concrete numeric examples such as `-0.40`, `0.60`, `0.70`;
- removed ticker, company name, current filing date, and prior filing date from the prompt body;
- kept sector as context;
- kept the same output schema and same signal formula so the pilot isolated prompt anchoring/dispersion rather than changing the full research design.

The workflow was:

```text
run 30-row pilot
    -> diagnose old-anchor concentration and signal dispersion
    -> only if diagnostic passes, run full 211-row extraction
```

Round 6 was run through:

```bash
python3 scripts/run_round6_deanchored_workflow.py
```

### 8.2 Stage A Change Versus Round 5

Round 5 fixed evaluation issues but reused old LLM outputs. Round 6 tested a new prompt output distribution directly.

Round 6 did not proceed to full backtesting because the pilot failed the diagnostic gate.

### 8.3 Stage A Pilot Diagnostic Results

Old-prompt pilot sample:

| field | Unique values | Top value share | Old anchor share |
|---|---:|---:|---:|
| `yoy_risk_change_score` | 15 | 26.67% | 26.67% at `-0.40` |
| `yoy_new_material_risk_score` | 9 | 23.33% | 23.33% at `0.60` |
| `yoy_risk_mitigation_score` | 8 | 46.67% | 16.67% at `0.20` |
| `yoy_peer_relative_risk_score` | 10 | 33.33% | 23.33% at `-0.30` |
| `yoy_direction_score` | 4 | 60.00% | 60.00% at `-1.00` |
| `yoy_confidence` | 8 | 46.67% | 46.67% at `0.70` |
| `llm_yoy_relative_signal` | 22 | 16.67% | n/a |

New de-anchored prompt pilot sample:

| field | Unique values | Top value share | Old anchor share |
|---|---:|---:|---:|
| `yoy_risk_change_score` | 4 | 53.33% | 0.00% at `-0.40` |
| `yoy_new_material_risk_score` | 4 | 50.00% | 0.00% at `0.60` |
| `yoy_risk_mitigation_score` | 2 | 90.00% | 0.00% at `0.20` |
| `yoy_peer_relative_risk_score` | 2 | 76.67% | 0.00% at `-0.30` |
| `yoy_direction_score` | 4 | 53.33% | 53.33% at `-1.00` |
| `yoy_confidence` | 8 | 33.33% | 33.33% at `0.70` |
| `llm_yoy_relative_signal` | 8 | 33.33% | n/a |

Diagnostic decision:

```text
do_not_full_run_yet
```

Reasons:

- Top-value concentration stayed high for `yoy_risk_change_score`, `yoy_new_material_risk_score`, `yoy_risk_mitigation_score`, and `yoy_peer_relative_risk_score`.
- `llm_yoy_relative_signal` had only 8 unique values out of 30 pilot rows.

Interpretation:

The de-anchored prompt succeeded at removing the old numeric anchors. For example, old-anchor shares at `-0.40`, `0.60`, `0.20`, and `-0.30` went to 0% for the corresponding component fields.

However, removing numeric examples did not improve usable cross-sectional information. The model shifted from copying example-like decimal scores to using a coarser rubric: mostly `-1`, `0`, and `1` component values. The resulting signal became less granular than the old prompt on the same pilot sample: 8 unique signal values versus 22 under the old prompt.

The full 211-row extraction was therefore not run. This avoided spending API cost on a prompt variant that already failed the pilot gate.

Conclusion of Stage A: do not simply remove numeric examples again — change the task, not just the formatting. This was implemented as Stage B below.

### 8.4 Stage B Method: Diff-Surprise Prompt on Deterministic YoY Diffs

Stage B implements the prompt v2 plan: feed actual text diffs, ask for company-specific investable surprise, separate market-wide boilerplate from company-specific changes, and gate the full run on a 30-row pilot.

Step 1 — deterministic diff (no LLM):

- SEC-extracted Item 1A text has no paragraph markers, so each filing is split into sentence groups of roughly 700 characters (`src/features/risk_section_diff.py`).
- Current-year blocks are greedily matched to prior-year blocks by word-set Jaccard similarity.
- No match above 0.50 means the block is `added`; a match below 0.85 is `modified`; unmatched prior blocks are `removed`.
- A whole-document word-shingle Jaccard similarity is also computed (Lazy Prices style) and stored as `diff_similarity`.
- Only the changed sections (up to 12,000 characters, longest changes first) are sent to the LLM. Unchanged boilerplate never reaches the model.

Step 2 — LLM scoring (`src/llm/diff_surprise_prompts.py`):

- Evidence first: the model must list up to 5 material changes, each with `scope` (company_specific / sector_wide / market_wide), `direction`, and integer `materiality` 0-10, before producing any aggregate score.
- Base-rate calibration is explicit: risk sections grow through lawyer-driven boilerplate updating, growth in length or risk count is not a signal, and for the majority of filings the correct `net_signal` is 0.
- Market-wide and sector-wide changes are classified but may not move `net_signal`.
- Materiality gate: `net_signal` must be 0 unless at least one company-specific change has materiality 6 or higher. Violations are recorded in `diff_gate_violation`, not silently corrected.
- Integer scales throughout, no numeric example values anywhere in the prompt, and no ticker, company name, or filing dates (sector is the only identity context). This addresses the Round 2-4 anchoring and training-data contamination concerns.

Final signal:

```text
llm_diff_surprise_signal =
  0                                                       if net_signal == 0
  net_signal
  + 0.25 * (company_specific_positive - company_specific_negative)
                                                          otherwise
```

`net_signal` (integer -5..5) is the primary judgment; the intensity spread adds within-bucket granularity so committed scores can still be ranked under fractional tie handling. Rows with `net_signal = 0` stay exactly 0: the materiality rule says no position without a high-materiality company-specific change, so sub-threshold intensity must not leak a direction into the neutral bucket. (The first run leaked it on 49 of 211 rows; this was fixed in post-run review, see 8.8.)

Implementation details:

- Model: `deepseek-v4-flash`, temperature 0.0, JSON mode, max output tokens 1,600.
- Extraction CLI with `--mock`, `--resume`, `--sample-keys`: `src/llm/extract_diff_surprise_signals.py`.
- Distribution gate: `src/analysis/diagnose_diff_surprise_distribution.py`.
- Workflow: `scripts/run_round6_diff_surprise_workflow.py` (pilot -> gate -> full run -> comparison).
- New dependencies recorded in `requirements.txt`: `tabulate`, `scipy`.

### 8.5 Stage B Pilot Gate (30 Pairs)

The pilot reused the same 30 sample keys as Stage A. Decision: `pass_for_full_run`.

- `net_signal` distribution: 21 zeros (70%), 6 negative, 3 positive — the base-rate rule was followed and both directions were used, versus 60% at -1 under the old prompt.
- Materiality gate violations: 0.
- Signal std 1.78; 11 unique signal values overall, 6 unique among the 9 nonzero rows.
- Spot-checked evidence was concrete and verifiable: MRK cited the disclosed Lagevrio sales decline from $5.7B to ~$1.0B; QCOM scored positive for the removal of Huawei export-restriction language; KO 2020 weighed the CCBA held-for-sale reversal against the CCBJHI impairment.

One gate criterion was revised after observing the pilot, and this is a documented post-hoc change: the original whole-signal uniqueness threshold (>= 12 unique values in 30 rows) contradicts the intended zero base rate, because a correct sparse signal concentrates at 0 by design. The check now applies only to committed (nonzero) scores, with sparsity bounded separately by zero-share limits (20%-90%).

### 8.6 Stage B Full-Run Output Distribution (211 Rows)

- Zero share 64% (136/211), within the calibration bounds.
- Nonzero rows: 75, of which 56 negative / 19 positive (75% negative). The negativity tilt is reduced but not eliminated; under the old prompt 66% of all rows were scored -1.
- Materiality gate violations: 0 out of 211.
- Signal mean by filing year ranges from -0.34 (2022) to -1.53 (2023); no year collapses to a constant.
- The strict pilot gate, reapplied to the full output, flags low uniqueness among committed scores (29 unique values across 75 nonzero rows). Committed scores cluster into coarse buckets such as -1.7 and -2.0 equivalents on the new scale; this is recorded in `round6_diff_surprise_full_distribution_diagnostic.md`.
- Diff quality caveat: median pair similarity is 0.72, but 12 of 211 pairs have similarity below 0.20 (for example BKNG 2020, QCOM 2021, XOM 2025), which usually indicates prior-year extraction problems rather than true full-document rewrites. For those pairs the "diff" approaches the whole filing.

### 8.7 Stage B Backtest Results

Same evaluation framework as Round 5: strict common coverage (71 signal months, 42 tickers, 70 backtest periods), fractional boundary ties, persistent sector/size-neutralized random baseline, 500 Monte Carlo trials.

| signal | Ann. Return | Sharpe | Max DD | Mean IC | Final Cum |
|---|---:|---:|---:|---:|---:|
| `before_text_signal` | 2.89% | 0.28 | -17.54% | 2.48% | 18.10% |
| `enhanced_text_signal` | 2.90% | 0.30 | -10.84% | 2.67% | 18.17% |
| `enhanced_sector_size_neutral` | 5.32% | 0.48 | -16.55% | 2.00% | 35.30% |
| `deepseek_absolute_llm_text_signal` | -8.45% | -0.47 | -53.72% | -2.15% | -40.25% |
| `deepseek_absolute_sector_size_neutral` | -3.53% | -0.20 | -41.53% | 0.95% | -18.94% |
| `deepseek_diff_surprise_signal` | -1.91% | -0.14 | -13.76% | -0.92% | -10.64% |
| `deepseek_diff_surprise_sector_size_neutral` | 4.46% | 0.43 | -21.73% | 0.59% | 28.98% |
| `random_no_text_persistent_neutralized` | -2.37% | -0.10 | -22.58% | -0.86% | -13.07% |

Neutralized diff-surprise signal versus 500 persistent neutralized random trials:

| metric | strategy value | random mean | random p50 | random p95 | percentile |
|---|---:|---:|---:|---:|---:|
| Annualized return | 4.46% | -0.81% | -1.24% | 9.11% | 82.2% |
| Sharpe ratio | 0.43 | 0.00 | -0.02 | 0.75 | 84.6% |
| Mean IC | 0.59% | 0.04% | -0.09% | 3.49% | 62.0% |
| Mean rank IC | 1.74% | -0.01% | -0.21% | 3.56% | 77.6% |
| Final cumulative return | 28.98% | 0.11% | -7.00% | 66.34% | 82.2% |

Annual stability of the neutralized diff-surprise signal: positive long-short years are 2021 (+1.10% per month), 2023 (+1.52% per month), and 2024 (+0.64% per month); 2020 is clearly negative (-1.12% per month); 2022 and 2025 are roughly flat.

Supplementary deterministic check: a similarity-only signal (long high `diff_similarity`, short low, i.e. the Lazy Prices direction) is negative on this coverage: -4.52% annualized return, -0.27 Sharpe, mean IC -1.79%, final cumulative return -23.92%. The canonical change-volume signal carries no positive information in this 42-mega-cap 2020-2025 universe, which both contextualizes the modest LLM result and reinforces that the binding constraint is the sample, not only the prompt.

Interpretation:

- The diff-surprise redesign fixed the distributional pathologies it targeted: no anchor copying, a real zero base rate, both directions used, zero materiality-gate violations, and evidence grounded in verifiable filing changes.
- It produced the best LLM-based signal so far. After sector/size neutralization it reaches 0.43 Sharpe versus 0.10 for the old neutralized YoY signal, at the 82-85th percentile versus the persistent neutralized random benchmark on return and Sharpe, and within 0.05 Sharpe of the deterministic `enhanced_sector_size_neutral` benchmark (0.48).
- It is still not a tradable result: it does not clear the 95% significance threshold (empirical p around 0.15-0.18), and its mean IC percentile is modest (62nd; rank IC 78th), so the long-short performance leans on the tails rather than a uniformly strong ranking.
- The raw, un-neutralized version is slightly negative, so raw LLM output still carries sector/size tilts; the usable information only appears in the residual.
- Remaining bottlenecks, in order: statistical power of the 42-ticker universe (the similarity baseline failing here is direct evidence), coarse bucketing of committed scores, and prior-year extraction quality for the low-similarity pairs.

Best next step:

- Expand the universe and history (S&P 500-scale, point-in-time membership) before further prompt iteration; at the current sample size even a good signal cannot clear the significance bar.
- Test a listwise sector/year ranking prompt as the next variant, which directly produces the cross-sectional ordering the backtest consumes and removes the residual negativity tilt by construction.
- Fix prior-year Item 1A extraction for the 12 low-similarity pairs.
- Audit the stored `diff_rationale` and `diff_material_changes` fields for 2020 (the worst year) before changing the formula.

### 8.8 Post-Run Review Fixes

A code review after the first Stage B run found four issues. All are fixed; the third and fourth were documentation/labeling problems, the first two affected report content.

1. **Coverage mislabeled the API rerun.** `llm_api_rerun` was hardcoded to `no` in the shared comparison module, which was correct for Round 5 but wrong for Round 6. It is now a parameter; the Round 6 coverage table reads `yes (diff-surprise DeepSeek extraction)`.
2. **The composite signal leaked direction into gated rows.** The prompt requires `net_signal = 0` without a high-materiality company-specific change, but the intensity spread `0.25 * (positive - negative)` was applied unconditionally, so 49 of 211 rows had `net_signal = 0` and a nonzero final signal. The formula now keeps gated rows at exactly 0 (equivalent to strict materiality gating here, since the run has zero gate violations). All Stage B artifacts and the tables above were regenerated under the fixed formula. The fix improved the neutralized result from 3.44% annualized / 0.33 Sharpe / 21.79% cumulative (79-81st percentile) to 4.46% / 0.43 / 28.98% (82-85th percentile) — the sub-threshold direction leak had been adding noise, not information. Pilot-stage artifacts are kept as the historical record of the gate decision and still reflect the pre-fix formula.
3. **Misleading diagnostic labels.** The full-output diagnostic reused the pilot report title and the `do_not_full_run_yet` decision string, which could read as invalidating a run that had already completed. The full-output report is now titled as a full-output quality warning, and the comparison report states explicitly that the flag concerns coarse committed-score buckets, not run validity.
4. **`requirements.txt` was missing `scipy`.** The docs claimed it was recorded but only `tabulate` had been added. `scipy` is a genuine runtime dependency — pandas imports `scipy.stats` inside `corr(method="spearman")` for rank IC, which is exactly where the first comparison run crashed — so it is now in `requirements.txt` despite never being imported directly by project code.

## 9. Future Improvement Directions

Status note: the prompt-v2 ideas in 9.2 and 9.3 (investable surprise, company-specific versus market-wide separation, market-wide risks as diagnostics rather than penalties) were implemented in Round 6 Stage B. The remaining open directions are the error-analysis report (9.1), the neutralization diagnostics (9.4), running variants on a larger universe (9.5 — Round 6 evidence suggests universe size is now the binding constraint), and higher-frequency text sources (9.6).

### 9.1 Build an error-analysis report first

Before another prompt run, inspect where YoY LLM failed.

Recommended output:

- `reports/yoy_llm_error_analysis.md`
- annual long/short holdings
- worst months by long-short return
- top/bottom YoY signal names and rationales
- separation of company-specific risk versus economy-wide boilerplate

Priority years:

- 2020: strongly negative YoY performance after COVID disclosure rows were added.
- 2023: poor YoY IC and long-short performance.

### 9.2 Redesign prompt v2 around investable surprise

The next prompt should not primarily ask "did risk increase?" It should ask:

```text
Do the disclosure changes contain company-specific, not-yet-priced information
that is likely to affect 1-3 month excess returns versus peers?
```

New fields should separate:

- company-specific negative surprise
- company-specific positive surprise
- market-wide boilerplate risk
- sector-wide risk
- already-priced risk
- disclosure-quality change
- relative resilience versus peers
- mitigation credibility

### 9.3 Change the signal formula

The current formula penalizes new material risk too directly. A better formula should focus on investable surprise:

```text
investable_yoy_signal =
  company_specific_positive_change
  - company_specific_negative_change
  + mitigation_quality
  + relative_resilience
  - unpriced_negative_surprise
  - weak_disclosure_quality
```

Market-wide and sector-wide risks should be diagnostic fields, not direct alpha penalties.

### 9.4 Extend sector/size-neutral LLM diagnostics

Round 5 added sector/size-neutral versions of the existing DeepSeek signals. The next step is to diagnose what neutralization removed and whether the remaining residual signal has stable information:

- `deepseek_yoy_relative_signal`
- `deepseek_yoy_relative_sector_size_neutral`
- `deepseek_absolute_llm_text_signal`
- `deepseek_absolute_sector_size_neutral`

Useful follow-up checks:

- sector-level average signal before and after neutralization;
- size correlation before and after neutralization;
- long/short holdings by sector;
- factor regression of long-short returns against market, size, value, momentum, and quality factors.

### 9.5 Run prompt variants on the same 211-row universe

Future prompt comparisons should avoid changing the universe. Use the completed 211-row / 42-ticker setup for all variants.

Candidate variants:

- `absolute_risk_v1`
- `yoy_relative_v1`
- `investable_yoy_v2`
- `company_specific_yoy_v2`
- `sector_adjusted_yoy_v2`

Each variant should be evaluated with:

- same universe
- same backtest
- same random Monte Carlo framework
- same annual stability output
- same long/short rationale audit

### 9.6 Consider higher-information text sources

If 10-K Item 1A remains weak, shift to text sources with more timely information:

- earnings-call transcripts
- Q&A sections
- 8-K event filings
- guidance updates
- point-in-time news
- analyst call summaries

The current evidence suggests that annual 10-K risk-factor LLM scoring alone may be too slow-moving and too legalistic for short-horizon monthly alpha.
