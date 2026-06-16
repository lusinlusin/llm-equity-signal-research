# Code Map

这个文件的目的：帮你快速判断这个项目里每个目录和关键文件是干什么的。先看这里，不要直接从 `src/` 里一个个文件猜。

## One-Line Summary

这个项目做的是：

```text
SEC 10-K Item 1A risk factor text
        -> text / LLM signal
        -> monthly cross-sectional long-short backtest
        -> metrics, IC, cumulative return, random baseline comparison
        -> reports/
```

## 最重要的分层

```text
scripts/
    你手动运行的命令入口。
    它们负责 parse CLI arguments，然后调用 src/ 里的函数。

src/
    真正的项目功能代码。
    包括下载数据、构造 signal、回测、分析、画图、LLM prompt/client。

data/
    本地数据文件。
    raw/ 是原始或近似原始数据，processed/ 是 LLM extraction 或 pipeline 生成的数据。

reports/
    实验结果。
    每个 round 的 metrics, IC, cumulative return, plots, comparison report 都在这里。
```

简单记：

```text
scripts = 运行入口
src     = 功能实现
data    = 输入和中间数据
reports = 输出结果
```

## 你通常会直接运行的文件

| 任务 | 入口 |
| --- | --- |
| 下载当前 SEC 10-K Item 1A 文本 | `scripts/download_sec_10k_risk_factors.py --mode current` |
| 下载 prior 10-K context | `scripts/download_sec_10k_risk_factors.py --mode prior` |
| 当前 + prior 一起下载 | `scripts/download_sec_10k_risk_factors.py --mode both` |
| 下载 ticker sector / market cap metadata | `scripts/download_ticker_metadata.py` |
| 跑 Round 1 deterministic robustness | `scripts/run_research_upgrade.py` |
| 跑 DeepSeek absolute extraction | `scripts/extract_llm_text_signals.py` 或 `python3 -m src.llm.extract_text_signals` |
| 跑 DeepSeek YoY relative extraction | `python3 -m src.llm.extract_yoy_relative_signals` |
| 跑 Round 2 DeepSeek absolute comparison | `python3 -m src.analysis.compare_llm_results` |
| 跑 Round 4 YoY relative all-signal comparison | `python3 -m src.analysis.compare_yoy_relative_all_signals` |
| 跑 Round 5 soundness-fix comparison | `python3 -m src.analysis.compare_round5_soundness` |
| 跑 Round 6 de-anchored prompt pilot/full workflow | `python3 scripts/run_round6_deanchored_workflow.py` |
| 跑 Round 6 diff-surprise prompt pilot/full workflow | `python3 scripts/run_round6_diff_surprise_workflow.py` |
| 跑 Round 7 Item 1A repair rerun comparison | `python3 scripts/run_round7_item1a_repair_comparison.py` |
| 跑 Round 7 error analysis + portfolio variants | `python3 scripts/analyze_round7_error_and_portfolio_variants.py` |
| 单独重画 legacy cumulative return 图 | `scripts/plot_cumulative_returns.py` |

## 推荐阅读顺序

如果你只是想理解项目，不要从底层代码开始。按这个顺序看：

1. `progress.md`
2. `signal_method.md`
3. `code_map.md`
4. `README.md`
5. `scripts/run_research_upgrade.py`
6. `src/features/text_signals.py`
7. `src/backtest/cross_sectional.py`
8. `src/analysis/compare_yoy_relative_all_signals.py`

## scripts/

`scripts/` 里的文件应该理解成“命令行按钮”。

### `scripts/download_sec_10k_risk_factors.py`

用途：下载 SEC 10-K Item 1A risk factor 文本。

现在这个脚本支持三种模式：

```bash
--mode current
--mode prior
--mode both
```

它本身不应该放复杂业务逻辑。真正的 SEC 下载、filing metadata 获取、Item 1A 提取、保存 CSV 逻辑在：

```text
src/data/sec_filings.py
```

常用命令：

```bash
python3 scripts/download_sec_10k_risk_factors.py \
  --mode current \
  --start-year 2020 \
  --end-year 2025 \
  --output data/raw/sec_10k_risk_factors.csv
```

```bash
python3 scripts/download_sec_10k_risk_factors.py \
  --mode prior \
  --prior-input data/raw/sec_10k_risk_factors.csv \
  --prior-output data/raw/sec_10k_risk_factors_prior_context.csv
```

### `scripts/download_ticker_metadata.py`

用途：从 `yfinance` 下载当前 ticker metadata。

输出：

```text
data/raw/ticker_metadata.csv
```

真正的下载和保存逻辑在：

```text
src/data/metadata.py
```

这个 metadata 主要用于 sector / size neutralization。

### `scripts/extract_llm_text_signals.py`

用途：跑 DeepSeek absolute LLM signal extraction。

这个文件只是一个很薄的 wrapper，实际逻辑在：

```text
src/llm/extract_text_signals.py
src/llm/deepseek_client.py
src/llm/prompts.py
src/llm/schema.py
```

对应的是 Round 2 的 LLM absolute signal。

### `scripts/run_research_upgrade.py`

用途：跑 Round 1 deterministic robustness experiment。

它会：

```text
load SEC text
    -> build before_text_signal
    -> build enhanced_text_signal
    -> build enhanced_sector_size_neutral
    -> run long-short backtest
    -> run random no-text Monte Carlo baseline
    -> write metrics, IC, cumulative returns, report
```

主要输出目录：

```text
reports/round1_deterministic_robustness/
```

这个脚本不跑 DeepSeek。

### `scripts/plot_cumulative_returns.py`

用途：单独从已有 portfolio returns 重画 cumulative return comparison。

现在主要用于 legacy prototype 的旧图，不是当前主实验的核心入口。

### `scripts/analyze_round7_error_and_portfolio_variants.py`

用途：基于已生成的 Round 7 post-repair signal 做 error analysis，并测试组合构造变体。

它不会重新调用 DeepSeek。主要读取：

```text
data/processed/llm_diff_surprise_features_deepseek_item1a_repair.csv
reports/round7_item1a_repair_rerun/round7_item1a_repair_deepseek_diff_surprise_sector_size_neutral.csv
```

主要输出：

```text
reports/round7_item1a_repair_rerun/round7_error_analysis_and_portfolio_variants.md
reports/round7_item1a_repair_rerun/round7_portfolio_variant_metrics.csv
reports/round7_item1a_repair_rerun/round7_monthly_error_analysis.csv
reports/round7_item1a_repair_rerun/round7_worst_month_holdings.csv
```

## src/data/

`src/data/` 负责数据层：下载、读取、清洗输入数据。

### `src/data/sec_filings.py`

用途：SEC filings 相关的核心逻辑。

它负责：

```text
SEC ticker map
10-K filing metadata
document URL
Item 1A Risk Factors extraction
current filing records
prior context records
CSV save
```

关键函数：

| 函数 | 用途 |
| --- | --- |
| `save_sec_10k_risk_factors()` | 下载并保存 current 10-K Item 1A |
| `download_prior_context_records()` | 根据 current filing 往前下载 prior context |
| `extract_item_1a_risk_factors()` | 从 10-K HTML 中抽 Item 1A 文本 |
| `get_recent_10k_filings()` | 获取公司 10-K filing metadata |

### `src/data/metadata.py`

用途：ticker metadata 下载和读取。

关键函数：

| 函数 | 用途 |
| --- | --- |
| `fetch_ticker_metadata()` | 从 yfinance 抓 sector / industry / market cap |
| `save_ticker_metadata()` | 保存 metadata CSV |
| `load_ticker_metadata()` | 读取 metadata，并生成 `log_market_cap` |

### `src/data/prices.py`

用途：价格数据。

它负责：

```text
yfinance adjusted close download
monthly price conversion
monthly returns
forward returns
synthetic prices for offline checks
```

回测用的是 forward returns，也就是当前 signal 对下一期收益的预测。

### `src/data/texts.py`

用途：读取 text dataset CSV。

主要读取：

```text
data/raw/sec_10k_risk_factors.csv
data/processed/llm_text_features_deepseek.csv
data/processed/llm_yoy_relative_features_deepseek.csv
```

## src/features/

`src/features/` 负责把文本或随机数变成 signal matrix。

### `src/features/text_signals.py`

用途：deterministic text signal。

这里是 before / enhanced dictionary signal 的核心。

关键概念：

```text
text records
    -> score_text_records()
    -> text_signal / enhanced_text_signal
    -> build_point_in_time_text_signal_matrix()
    -> monthly ticker x date signal matrix
```

主要 signal：

```text
text_signal
enhanced_text_signal
```

### `src/features/neutralization.py`

用途：sector / size neutralization。

它把 signal 对 sector dummy 和 log market cap 做横截面中性化，得到：

```text
enhanced_sector_size_neutral
```

### `src/features/placeholder.py`

用途：random no-text signal。

主要用于：

```text
random baseline
Monte Carlo baseline
sanity check
```

## src/llm/

`src/llm/` 负责 DeepSeek extraction。

### Absolute LLM Signal

对应 Round 2。

相关文件：

```text
src/llm/extract_text_signals.py
src/llm/deepseek_client.py
src/llm/prompts.py
src/llm/schema.py
```

输入：

```text
data/raw/sec_10k_risk_factors.csv
```

输出：

```text
data/processed/llm_text_features_deepseek.csv
```

signal：

```text
llm_text_signal
```

### YoY Relative LLM Signal

对应 Round 3 / Round 4。

相关文件：

```text
src/llm/extract_yoy_relative_signals.py
src/llm/deepseek_yoy_relative_client.py
src/llm/yoy_relative_prompts.py
src/llm/yoy_relative_schema.py
```

输入：

```text
data/raw/sec_10k_risk_factors.csv
data/raw/sec_10k_risk_factors_prior_context.csv
data/raw/ticker_metadata.csv
```

输出：

```text
data/processed/llm_yoy_relative_features_deepseek.csv
```

signal：

```text
llm_yoy_relative_signal
```

### Diff-Surprise YoY LLM Signal

对应 Round 6 Stage B 和 Round 7 post-repair rerun。

相关文件：

```text
src/features/risk_section_diff.py
src/llm/extract_diff_surprise_signals.py
src/llm/deepseek_diff_surprise_client.py
src/llm/diff_surprise_prompts.py
src/llm/diff_surprise_schema.py
scripts/run_round6_diff_surprise_workflow.py
scripts/run_round7_item1a_repair_comparison.py
```

输入：

```text
data/raw/sec_10k_risk_factors.csv
data/raw/sec_10k_risk_factors_prior_context.csv
data/raw/ticker_metadata.csv
```

输出：

```text
data/processed/llm_diff_surprise_features_deepseek.csv
data/processed/llm_diff_surprise_features_deepseek_item1a_repair.csv
reports/round6/round6_diff_surprise_*
reports/round7_item1a_repair_rerun/round7_item1a_repair_*
```

signal：

```text
llm_diff_surprise_signal
```

核心区别：先用 deterministic block diff 找 current/prior Item 1A 的新增、删除、修改段落，再让 DeepSeek 只判断这些 changed sections 是否包含 company-specific investable surprise。Round 7 使用修复后的 Item 1A parser 重新生成 raw text，并 full rerun 211 条 diff-surprise LLM features。

### `src/llm/mock.py`

用途：不调用 API 的 mock LLM output。

主要用于离线测试，不是最终结果。

## src/backtest/

`src/backtest/` 负责投资组合构造和 performance metrics。

### `src/backtest/cross_sectional.py`

用途：横截面 long-short 回测。

它做的是：

```text
每个月按 signal 排序
    -> 买 signal 高的一组
    -> 空 signal 低的一组
    -> long_return - short_return
```

输出包括：

```text
long_return
short_return
long_short_return
n_long
n_short
n_stocks
```

### `src/backtest/metrics.py`

用途：计算 performance summary。

包括：

```text
annualized_return
annualized_volatility
Sharpe
max_drawdown
positive rate
```

## src/analysis/

`src/analysis/` 负责实验结果比较、Monte Carlo、画图。

### `src/analysis/compare_llm_results.py`

用途：Round 2 DeepSeek absolute comparison。

比较：

```text
original_text_signal
deepseek_llm_text_signal
random_no_text
```

主要输出：

```text
reports/round2_deepseek_absolute/
```

### `src/analysis/compare_yoy_relative_all_signals.py`

用途：Round 4 YoY relative all-signal comparison。

比较：

```text
before_text_signal
enhanced_text_signal
enhanced_sector_size_neutral
deepseek_absolute_llm_text_signal
deepseek_yoy_relative_signal
random_no_text
```

主要输出：

```text
reports/round4_yoy_relative_full/
```

### `src/analysis/comparison.py`

用途：把多个 strategy 的 metrics 合成对比表。

### `src/analysis/monte_carlo.py`

用途：跑很多次 random baseline，然后看目标 strategy 在 random 分布里的 percentile。

### `src/analysis/plots.py`

用途：画 cumulative return 和 random baseline distribution。

注意：

```text
cumulative return CSV 是从 portfolio_returns 的 long_short_return 算出来的。
它是展示用的累计曲线，不包含 long leg / short leg / n_stocks 等细节。
```

## `src/pipeline.py`

这是早期较通用的 pipeline。

用途：

```text
price data
    -> text or random signal
    -> backtest
    -> save outputs
```

现在主研究 round 更多使用：

```text
scripts/run_research_upgrade.py
src.analysis.compare_llm_results
src.analysis.compare_yoy_relative_all_signals
```

所以 `src/pipeline.py` 可以理解成早期基础 pipeline，不是当前最新 YoY LLM 实验的主入口。

## reports/

`reports/` 是结果区。

### `reports/legacy_phase3_real_sec_prototype/`

早期 SEC prototype。

不是当前主结果，只保留作历史参考。

### `reports/round1_deterministic_robustness/`

Round 1。

不使用 DeepSeek。

核心问题：

```text
deterministic dictionary signal 是否比 random no-text baseline 更稳？
```

核心文件：

```text
robustness_strategy_metrics.csv
robustness_cumulative_returns.csv
robustness_cumulative_returns.png
robustness_monte_carlo_significance.csv
random_baseline_trials.csv
robustness_upgrade_report.md
```

详细 audit 文件：

```text
*_portfolio_returns.csv
*_ic.csv
*_annual_stability.csv
```

### `reports/round2_deepseek_absolute/`

Round 2。

核心问题：

```text
DeepSeek absolute LLM signal 是否比 original text signal 和 random baseline 好？
```

结果：表现较差。

### `reports/round3_yoy_relative_initial_169row/`

Round 3 初版。

核心问题：

```text
YoY relative prompt 是否比 absolute prompt 更合理？
```

注意：这一轮只有 169 rows / 40 tickers，后来发现是因为缺少 prior context，不能作为最终结果。

### `reports/round4_yoy_relative_full/`

Round 4。

核心问题：

```text
补齐 prior context 后，YoY relative signal 在完整 211 rows / 42 tickers 上是否有效？
```

这是目前最重要的 LLM comparison round。

### `reports/round5/`

Round 5。

核心问题：

```text
修正 tie handling、random baseline 和 LLM neutralization 后，前几轮结论是否还成立？
```

结果：deterministic `enhanced_sector_size_neutral` 仍是最佳整体 signal；旧 YoY LLM neutralized 后仍然较弱。

### `reports/round6/`

Round 6。

核心问题：

```text
去掉 numeric anchors 是否足够？如果不够，diff-surprise prompt 是否能让 LLM 只关注可投资的公司特异变化？
```

主要结果：

```text
Stage A de-anchored YoY pilot failed the distribution gate.
Stage B diff-surprise prompt completed 211 rows / 42 tickers.
Pre-repair best LLM result: deepseek_diff_surprise_sector_size_neutral, 4.46% annualized return, 0.43 Sharpe, 28.98% final cumulative return.
```

注意：Round 6 现在是 historical / pre-repair result。后续 Item 1A parser repair 改动了 122 / 293 raw rows，所以 Round 6 DeepSeek features 不再作为 current evidence。

### `reports/round7_item1a_repair_rerun/`

Round 7。

核心问题：

```text
修复 SEC Item 1A parser 后，Round 6 diff-surprise LLM result 是否还能成立？
```

主要结果：

```text
Full 211-row DeepSeek diff-surprise rerun completed on repaired text.
deepseek_diff_surprise_sector_size_neutral: 0.15% annualized return, 0.07 Sharpe, 0.88% final cumulative return.
Mean IC remains positive at 1.89%, but portfolio returns are near random.
```

## data/

### `data/raw/sec_10k_risk_factors.csv`

当前 SEC 10-K Item 1A 文本。

用于：

```text
deterministic text signal
DeepSeek absolute LLM signal
YoY current filing input
```

### `data/raw/sec_10k_risk_factors_prior_context.csv`

prior 10-K Item 1A 文本。

用于：

```text
YoY relative LLM signal
```

### `data/raw/ticker_metadata.csv`

当前 ticker metadata。

用于：

```text
sector neutralization
size neutralization
YoY prompt metadata
```

### `data/processed/llm_text_features_deepseek.csv`

DeepSeek absolute LLM extraction output。

用于 Round 2 和 Round 4 comparison。

### `data/processed/llm_yoy_relative_features_deepseek.csv`

DeepSeek YoY relative LLM extraction output。

用于 Round 4 comparison。

也用于 Round 5 soundness-fix comparison。

### `data/processed/llm_diff_surprise_features_deepseek_item1a_repair.csv`

Round 7 post-repair DeepSeek diff-surprise extraction output。

用于：

```text
reports/round7_item1a_repair_rerun/
```

这是当前 diff-surprise LLM 的有效输出；旧的 `data/processed/llm_diff_surprise_features_deepseek.csv` 是 pre-repair Round 6 historical output。

## Round Mapping

| Round | 入口 | 主要输入 | 主要输出 | 目的 |
| --- | --- | --- | --- | --- |
| Legacy | `scripts/plot_cumulative_returns.py` | old processed portfolio returns | `reports/legacy_phase3_real_sec_prototype/` | 早期 prototype 图表 |
| Round 1 | `scripts/run_research_upgrade.py` | SEC text, metadata, prices | `reports/round1_deterministic_robustness/` | deterministic signal robustness |
| Round 2 | `src.llm.extract_text_signals`, `src.analysis.compare_llm_results` | SEC text, DeepSeek absolute output | `reports/round2_deepseek_absolute/` | absolute LLM signal comparison |
| Round 3 | `src.llm.extract_yoy_relative_signals` initial run | incomplete prior context | `reports/round3_yoy_relative_initial_169row/` | YoY prompt first attempt |
| Round 4 | `src.analysis.compare_yoy_relative_all_signals` | full current + prior + LLM outputs | `reports/round4_yoy_relative_full/` | full YoY relative comparison |
| Round 5 | `src.analysis.compare_round5_soundness` | existing LLM outputs, metadata, prices | `reports/round5/` | tie-handling fix, persistent random baseline, LLM sector/size neutralization |
| Round 6A | `scripts/run_round6_deanchored_workflow.py` | de-anchored YoY prompt, 30-row pilot sample | `reports/round6/` | removed old numeric anchors but failed the full-run gate because scores collapsed into coarse buckets |
| Round 6B | `scripts/run_round6_diff_surprise_workflow.py` | deterministic YoY diffs, diff-surprise DeepSeek prompt | `reports/round6/` | pre-repair historical result; later parser repair made these DeepSeek features stale |
| Round 7 | `scripts/run_round7_item1a_repair_comparison.py` | repaired raw text, full 211-row post-repair diff-surprise features | `reports/round7_item1a_repair_rerun/` | current result; neutralized diff-surprise LLM falls to 0.15% annualized return and 0.07 Sharpe |

## Output File Types

| 文件类型 | 含义 |
| --- | --- |
| `*_signal.csv` | 每月每个 ticker 的 signal matrix |
| `*_portfolio_returns.csv` | 每月 long/short/long-short return 和组合股票数 |
| `*_ic.csv` | 每月 information coefficient |
| `*_annual_stability.csv` | 按年份的 return / IC 稳定性 |
| `*_metrics.csv` | 策略整体表现，比如 annualized return, Sharpe, max drawdown |
| `*_cumulative_returns.csv` | 用于画图的累计收益曲线 |
| `*_cumulative_returns.png` | 累计收益图 |
| `random_baseline_trials.csv` | 多次 random no-text baseline 的结果分布 |
| `*_significance.csv` | 目标策略相对 random distribution 的 percentile |

## 常见混淆

### `robustness_cumulative_returns.csv` 和 `*_portfolio_returns.csv`

它们不是完全重复。

```text
*_portfolio_returns.csv
    = 月度 long_return / short_return / long_short_return / n_stocks

robustness_cumulative_returns.csv
    = 用 long_short_return 算出来的累计收益曲线
```

如果只是看图和最终表现，看 cumulative returns 就够。

如果要 debug 为什么某个月策略亏了，或者要重算 metrics，需要 portfolio returns。

### `scripts/` 和 `src/`

```text
scripts/
    人运行的入口

src/
    被入口调用的功能代码
```

不要把所有代码都合进一个文件。文件少不等于清楚。更好的标准是：

```text
入口少
功能分层清楚
输出目录清楚
```

### current SEC data 和 prior SEC data

```text
current:
    当前研究窗口内的 10-K Item 1A
    文件: data/raw/sec_10k_risk_factors.csv

prior:
    每个 ticker 第一条 current filing 之前的历史 10-K
    文件: data/raw/sec_10k_risk_factors_prior_context.csv
```

prior 主要服务于 YoY relative prompt。

## 如果你只想复现当前主结果

当前主结果是 Round 7 post-repair rerun。历史 round 的命令见上面的 Round Mapping；如果只想复现当前 README 里的结果，优先使用已有 post-repair LLM feature file：

This command regenerates Round 7 diagnostics, backtests, random-baseline comparison, and cumulative-return plot without making new API calls:

```bash
python3 scripts/run_round7_item1a_repair_comparison.py
```

If you intentionally want to rerun the 211 DeepSeek calls on repaired text, write to the Round 7 output file and use `--resume`:

```bash
python3 -m src.llm.extract_diff_surprise_signals \
  --input data/raw/sec_10k_risk_factors.csv \
  --metadata data/raw/ticker_metadata.csv \
  --prior-context data/raw/sec_10k_risk_factors_prior_context.csv \
  --output data/processed/llm_diff_surprise_features_deepseek_item1a_repair.csv \
  --resume
```

注意：Round 7 diff-surprise rerun 会产生 DeepSeek API 成本。当前项目已经有 processed post-repair LLM output；不要删除已有 output 后重跑，除非你明确想重新产生 API 成本。

## 当前最重要的文档

| 文件 | 用途 |
| --- | --- |
| `progress.md` | 当前项目进展和下一步 |
| `signal_method.md` | 每一轮 signal method 和结果解释 |
| `README.md` | GitHub 项目首页式介绍、核心结果和研究结论 |
| `code_map.md` | 代码结构导航和运行命令 |
