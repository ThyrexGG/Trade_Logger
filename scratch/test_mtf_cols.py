import sys
sys.path.insert(0, ".")
import yfinance as yf
import pandas as pd
import strategies.smc_utils as smc_utils
import strategies.mtf_engine as mtf_engine

df = yf.download('USDJPY=X', period='60d', interval='15m', progress=False)
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.droplevel(1)
df_bias = yf.download('USDJPY=X', period='60d', interval='4h', progress=False)
if isinstance(df_bias.columns, pd.MultiIndex):
    df_bias.columns = df_bias.columns.droplevel(1)

df = smc_utils.add_smc_features(df)
df_bias = smc_utils.add_smc_features(df_bias)
df = mtf_engine.align_htf_to_ltf(df, df_bias, "_BIAS", "4h")

bias_cols = [c for c in df.columns if "bias" in c.lower() or "htf" in c.lower()]
print("Bias columns in aligned df:", bias_cols)
if bias_cols:
    print("Value counts:", df[bias_cols[0]].value_counts(dropna=False))
