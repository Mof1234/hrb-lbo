# Leveraged Buyout Model — H&R Block Case

Integrated LBO model with operating projections, debt schedules, cash waterfall, and sponsor returns. Includes an interactive Streamlit dashboard with sensitivity analysis.

## Features

- **Base-case LBO (5-year hold)**: IRR, MOIC, exit equity value
- **3 statements** (IS / BS / CF) for projection years
- **Debt schedules**: TLB + Revolver with mandatory amort and cash sweep
- **Cash waterfall**: FCF → mandatory amort → maintain min cash → revolver paydown → TLB sweep
- **EBITDA normalization** framework for one-time items (addbacks via `mapping.yaml`)
- **Sensitivity table**: Entry Multiple × Exit Multiple → IRR / MOIC grids
- **Outputs** saved to `outputs/*.csv` plus a clean printed summary

## Project Structure

```
hrb-lbo/
  data/
    historical_is.csv
    historical_bs.csv
    historical_cf.csv
    assumptions.yaml
    mapping.yaml
  src/
    io.py           # Load financials, assumptions, mapping
    normalize.py    # EBITDA addbacks / normalization
    operating_model.py
    statements.py   # IS, BS, CF projections
    debt.py         # TLB, Revolver, cash waterfall
    returns.py      # Exit, IRR, MOIC
    sensitivity.py
    utils.py
  outputs/
    projected_is.csv
    projected_bs.csv
    projected_cf.csv
    debt_schedule.csv
    equity_returns.csv
    sensitivity_irr.csv
    sensitivity_moic.csv
  main.py          # CLI batch run
  app.py           # Interactive Streamlit dashboard
  requirements.txt
```

## Setup

```bash
cd hrb-lbo
python3 -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Run

**CLI (batch):**
```bash
python3 main.py
```

**Interactive Dashboard (Streamlit):**
```bash
streamlit run app.py
```

The dashboard provides:
- Sidebar controls for entry/exit multiples, leverage, revenue CAGR, EBITDA margin, tax rate
- KPI metrics (IRR, MOIC, entry/exit equity)
- Pages: Overview, Operating Model, Debt Schedule, 3 Statements, Sensitivity heatmaps

> **Note:** On macOS, use `python3` (not `python`). After activating the venv, you can use either.

## Assumptions (`data/assumptions.yaml`)

- **Transaction**: entry/exit multiples, leverage %, fees, min cash
- **Operating**: revenue CAGR, EBITDA margin, D&A %, CapEx %, NWC %
- **Debt**: TLB rate, revolver limit/rate, mandatory amort %
- **Model**: start year, projection years, tax rate

## Normalization (`data/mapping.yaml`)

One-off adjustments (e.g. restructuring, impairment) are added back to EBITDA:

```yaml
adjustments:
  2024:
    restructuring: 45000000
  2023:
    restructuring: 20000000
```

## Architecture

Modular design for extension: dividend recap, covenant checks, downside/upside scenarios.

## License

MIT
