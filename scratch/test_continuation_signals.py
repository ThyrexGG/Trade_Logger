import sys
sys.path.insert(0, ".")
import yfinance as yf
import pandas as pd
import strategies.smc_utils as smc_utils
from strategies.usdjpy_smc_continuation import USDJPYContinuationStrategy

# Download data directly
d = yf.download('USDJPY=X', period='60d', interval='15m', progress=False)
if isinstance(d.columns, pd.MultiIndex):
    d.columns = d.columns.droplevel(1)
d = smc_utils.add_smc_features(d)

strat = USDJPYContinuationStrategy()
signals = []

for i in range(30, len(d)):
    setup = strat.analyze(d, i, {'sl_atr': 1.0, 'tp_atr': 2.5, 'min_displacement_atr': 0.5})
    if setup.get('status') == 'READY':
        signals.append((i, str(d.index[i]), setup['signal'], setup['ideal_entry'], setup['stop_loss'], setup['tp1']))

print(f"Total bars: {len(d)}, Generated signals: {len(signals)}")
if signals:
    print("Sample signals:", signals[:5])
else:
    # Debug why 0 signals
    bull_fvgs = d[pd.notna(d['bullish_fvg_bottom'])]
    print("Bullish FVGs count:", len(bull_fvgs))
    # Check if price ever enters a bullish FVG
    touches = 0
    for i in range(30, len(d)):
        row = d.iloc[i]
        window = d.iloc[max(0, i-20):i+1]
        recent = window[pd.notna(window['bullish_fvg_bottom'])]
        if not recent.empty:
            last_fvg = recent.index[-1]
            top = float(recent.loc[last_fvg, 'bullish_fvg_top'])
            bot = float(recent.loc[last_fvg, 'bullish_fvg_bottom'])
            if bot <= row['Low'] <= top or bot <= row['Close'] <= top:
                touches += 1
    print("FVG Touches:", touches)
