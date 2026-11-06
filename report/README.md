# Report build

`report.tex` is a standalone LaTeX article. Figures are vector PDFs in `figures/`,
regenerated from the round artifacts in `reports/`.

## Regenerate figures

```bash
.venv/bin/python report/make_figures.py
```

Reads `reports/round10b_llm_backtest/`, `reports/round11_mdna/`, and
`data/processed/round10b_llm_diff_surprise_features_deepseek.csv`.

## Build the PDF

No LaTeX is installed on this machine. Two options:

**Overleaf (no install).** Upload the whole `report/` folder, set `report.tex`
as the main document, compile with pdfLaTeX.

**Local.** Install a TeX distribution first:

```bash
brew install --cask basictex
```

Then open a new shell (it adds `/Library/TeX/texbin` to PATH) and run:

```bash
cd report && pdflatex report.tex && pdflatex report.tex
```

Run it twice so the table of contents and cross-references resolve.
BasicTeX may prompt for missing packages; install them with
`sudo tlmgr install <package>`.

## Status

The source passed a static check (environment pairing, brace and math-mode
balance, escaping, figure paths, cross-references) but **has not been compiled**,
because no TeX engine is available here. Expect to fix minor spacing or float
placement on the first real build.
