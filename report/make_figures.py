"""Generate all figures for report/report.tex from the round artifacts.

Run from the repo root:  .venv/bin/python report/make_figures.py
Outputs vector PDFs into report/figures/.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "report", "figures")
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({
    "font.size": 9, "axes.grid": True, "grid.alpha": 0.3,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.autolayout": True, "legend.frameon": False,
})

def save(fig, name):
    """Write a vector PDF for LaTeX and a raster PNG for the GitHub README."""
    fig.savefig(os.path.join(OUT, name + ".pdf"))
    fig.savefig(os.path.join(OUT, name + ".png"), dpi=160)
    plt.close(fig)


def rd(path):
    d = pd.read_csv(os.path.join(ROOT, path), parse_dates=["date"])
    return d.sort_values("date").reset_index(drop=True)

def cum(d):
    return (1.0 + d["long_short_return"]).cumprod() - 1.0

R10B = "reports/round10b_llm_backtest/"
R11 = "reports/round11_mdna/"

# ---- Fig 1: cross-sectional breadth, Round 10 universe vs Round 11 universe ----
a, b = rd(R10B + "round10b_enhanced_text_signal_BM_portfolio_returns.csv"), rd(R11 + "round11_item1a_enhanced_portfolio_returns.csv")
fig, ax = plt.subplots(figsize=(6.0, 2.6))
ax.plot(a["date"], a["n_stocks"], lw=1.4, label="Round 10/10B download (`recent` array only)")
ax.plot(b["date"], b["n_stocks"], lw=1.4, label="Round 11 download (`include_older=True`)")
ax.set_ylabel("Stocks in cross-section")
ax.set_title("Monthly cross-sectional breadth, same nominal 150-name universe")
ax.legend(loc="lower right", fontsize=8)
save(fig, "fig-coverage")

# ---- Fig 2: Round 10B, LLM vs deterministic benchmark ----
llm, bm = rd(R10B + "round10b_deepseek_diff_surprise_portfolio_returns.csv"), rd(R10B + "round10b_enhanced_text_signal_BM_portfolio_returns.csv")
fig, ax = plt.subplots(figsize=(6.0, 2.9))
ax.plot(bm["date"], cum(bm) * 100, lw=1.5, color="#1b6ca8", label="enhanced_text_signal (deterministic)  Sharpe +0.68")
ax.plot(llm["date"], cum(llm) * 100, lw=1.5, color="#b22222", label="deepseek_diff_surprise (LLM)  Sharpe $-$0.83")
ax.axhline(0, color="k", lw=0.6)
ax.set_ylabel("Cumulative long-short return (%)")
ax.set_title("Round 10/10B: identical construction, opposite outcomes")
ax.legend(loc="upper left", fontsize=8)
save(fig, "fig-r10b-cumulative")

# ---- Fig 3: Round 11 signals ----
spec = [("round11_mdna_similarity_portfolio_returns.csv", "mdna_similarity (H1)", "#b22222", "-"),
        ("round11_mdna_enhanced_portfolio_returns.csv", "mdna_enhanced (H2)", "#d08c00", "-"),
        ("round11_item1a_enhanced_portfolio_returns.csv", "item1a_enhanced", "#1b6ca8", "-"),
        ("round11_item1a_similarity_portfolio_returns.csv", "item1a_similarity", "#4a9c5d", "--"),
        ("round11_mdna_tone_change_portfolio_returns.csv", "mdna_tone_change", "#777777", ":")]
fig, ax = plt.subplots(figsize=(6.0, 3.0))
for f, lab, c, ls in spec:
    d = rd(R11 + f)
    ax.plot(d["date"], cum(d) * 100, lw=1.4, color=c, ls=ls, label=lab)
ax.axhline(0, color="k", lw=0.6)
ax.set_ylabel("Cumulative long-short return (%)")
ax.set_title("Round 11: MD&A vs Item 1A signals, full-coverage universe")
ax.legend(loc="upper left", fontsize=8, ncol=2)
save(fig, "fig-r11-cumulative")

# ---- Fig 4: headline Sharpe trajectory by round ----
rounds = ["R1", "R2", "R4", "R5", "R6", "R7", "R10/10B", "R11"]
llm_s = [None, -0.512, 0.151, 0.103, 0.435, 0.570, -0.829, None]
det_s = [0.504, 0.504, 0.504, 0.477, 0.477, -0.333, 0.676, 0.487]
x = range(len(rounds))
fig, ax = plt.subplots(figsize=(6.0, 2.9))
ax.plot([i for i, v in zip(x, llm_s) if v is not None], [v for v in llm_s if v is not None],
        "o-", lw=1.5, ms=5, color="#b22222", label="Best LLM signal")
ax.plot(list(x), det_s, "s-", lw=1.5, ms=5, color="#1b6ca8", label="Deterministic benchmark")
ax.axhline(0, color="k", lw=0.6)
ax.set_xticks(list(x)); ax.set_xticklabels(rounds)
ax.set_ylabel("Sharpe ratio"); ax.set_xlabel("Round")
ax.set_title("Headline Sharpe by round")
ax.legend(loc="lower left", fontsize=8)
ax.annotate("parser repair", xy=(5, -0.333), xytext=(4.0, -0.72), fontsize=7.5,
            arrowprops=dict(arrowstyle="->", lw=0.7))
ax.annotate("6x sample", xy=(6, -0.829), xytext=(6.1, -0.60), fontsize=7.5,
            arrowprops=dict(arrowstyle="->", lw=0.7))
save(fig, "fig-sharpe-by-round")

# ---- Fig 5: LLM score distribution (negativity bias) ----
d = pd.read_csv(os.path.join(ROOT, "data/processed/round10b_llm_diff_surprise_features_deepseek.csv"))
ns = d["diff_net_signal"].dropna()
fig, ax = plt.subplots(figsize=(6.0, 2.5))
vals = sorted(ns.unique())
counts = [int((ns == v).sum()) for v in vals]
ax.bar(vals, counts, width=0.7, color=["#b22222" if v < 0 else ("#999999" if v == 0 else "#1b6ca8") for v in vals])
ax.set_xlabel("net_signal (integer; prompt-permitted range -5 to +5)")
ax.set_ylabel("Filing pairs")
ax.set_title("Round 10B LLM score distribution (n = 1,307): the positive tail is never used")
ax.set_xticks(range(-5, 6))
save(fig, "fig-llm-distribution")

print("wrote:", sorted(os.listdir(OUT)))
