import unittest
from unittest.mock import patch
import pandas as pd
import numpy as np
import backtester

class TestBacktester(unittest.TestCase):

    def setUp(self):
        # Create an artificial dataset
        dates = pd.date_range("2026-01-01", periods=30, freq="1h", tz="UTC")
        # Just repeat the 10 values 3 times
        base_open = [100, 102, 105, 108, 106, 110, 112, 115, 114, 116] * 3
        base_high = [101, 104, 106, 109, 107, 111, 113, 116, 115, 117] * 3
        base_low = [99, 101, 104, 107, 105, 109, 111, 114, 113, 115] * 3
        base_close = [102, 105, 108, 106, 110, 112, 115, 114, 116, 118] * 3
        
        self.df = pd.DataFrame({
            "Open": base_open,
            "High": base_high,
            "Low": base_low,
            "Close": base_close
        }, index=dates)

    @patch("yfinance.download")
    def test_no_look_ahead_bias(self, mock_yf):
        df_mock = self.df.copy()
        mock_yf.return_value = df_mock
        with patch("backtester.calc_rsi") as mock_rsi, patch("backtester.calc_atr") as mock_atr:
            mock_rsi.return_value = pd.Series([50]*2 + [20] + [50]*27, index=df_mock.index)
            mock_atr.return_value = pd.Series([1]*30, index=df_mock.index)
            res = backtester.run_backtest("EURUSD", strategy="Mean Reversion", slippage=0, commission_pct=0)
            print(res)
            self.assertNotIn("error", res)
            first_trade = res["trades"][0]
            self.assertEqual(first_trade["entry_price"], df_mock.iloc[3]["Open"])
            self.assertEqual(first_trade["entry_time"], df_mock.index[3])

    @patch("yfinance.download")
    def test_sl_tp_same_candle(self, mock_yf):
        df_mock = self.df.copy()
        mock_yf.return_value = df_mock
        with patch("backtester.calc_rsi") as mock_rsi, patch("backtester.calc_atr") as mock_atr:
            mock_rsi.return_value = pd.Series([50, 20] + [50]*28, index=df_mock.index)
            mock_atr.return_value = pd.Series([1]*30, index=df_mock.index)
            df_mock.at[df_mock.index[2], "High"] = 110 # Hits TP
            df_mock.at[df_mock.index[2], "Low"] = 90  # Hits SL
            res = backtester.run_backtest("EURUSD", strategy="Mean Reversion", slippage=0, commission_pct=0, sl_atr=1.5, tp_atr=2.0)
            first_trade = res["trades"][0]
            self.assertEqual(first_trade["exit_price"], 105 - 1.5)
            self.assertTrue(first_trade["pnl"] < 0)

    @patch("yfinance.download")
    def test_commission_and_slippage(self, mock_yf):
        df_mock = self.df.copy()
        mock_yf.return_value = df_mock
        with patch("backtester.calc_rsi") as mock_rsi, patch("backtester.calc_atr") as mock_atr:
            mock_rsi.return_value = pd.Series([50, 20] + [50]*28, index=df_mock.index)
            mock_atr.return_value = pd.Series([1]*30, index=df_mock.index)
            res = backtester.run_backtest("EURUSD", strategy="Mean Reversion", slippage=0.5, commission_pct=1.0)
            first_trade = res["trades"][0]
            self.assertEqual(first_trade["entry_price"], 105.5)
            self.assertEqual(first_trade["commission"], 100.0)
            self.assertEqual(first_trade["pnl"], first_trade["gross_pnl"] - 100.0)

    @patch("yfinance.download")
    def test_timezone_normalization(self, mock_yf):
        df_mock = self.df.copy()
        df_mock.index = df_mock.index.tz_convert("America/New_York")
        mock_yf.return_value = df_mock
        with patch("backtester.calc_rsi") as mock_rsi, patch("backtester.calc_atr") as mock_atr:
            mock_rsi.return_value = pd.Series([50, 20] + [50]*28, index=df_mock.index)
            mock_atr.return_value = pd.Series([1]*30, index=df_mock.index)
            res = backtester.run_backtest("EURUSD", strategy="Mean Reversion")
            self.assertNotIn("error", res)
            # Verify the returned curve has UTC timestamps
            first_time = res["equity_curve"][0]["time"]
            self.assertEqual(str(first_time.tzinfo), "UTC")

    @patch("yfinance.download")
    def test_fixed_spread_model(self, mock_yf):
        df_mock = self.df.copy()
        mock_yf.return_value = df_mock
        with patch("backtester.calc_rsi") as mock_rsi, patch("backtester.calc_atr") as mock_atr:
            mock_rsi.return_value = pd.Series([50, 20] + [50]*28, index=df_mock.index)
            mock_atr.return_value = pd.Series([1]*30, index=df_mock.index)
            # Apply 1.0 fixed spread
            res = backtester.run_backtest("EURUSD", strategy="Mean Reversion", slippage=0, commission_pct=0, fixed_spread=1.0)
            first_trade = res["trades"][0]
            # Entry row 2 open=105. Spread 1.0 -> Entry price = 106.0
            self.assertEqual(first_trade["entry_price"], 106.0)

    @patch("yfinance.download")
    def test_lot_rounding(self, mock_yf):
        df_mock = self.df.copy()
        mock_yf.return_value = df_mock
        with patch("backtester.calc_rsi") as mock_rsi, patch("backtester.calc_atr") as mock_atr:
            mock_rsi.return_value = pd.Series([50, 20] + [50]*28, index=df_mock.index)
            mock_atr.return_value = pd.Series([1]*30, index=df_mock.index)
            res = backtester.run_backtest("EURUSD", strategy="Mean Reversion", capital=10000, risk_pct=1.0, sl_atr=1.5)
            # Risk = 100. SL distance = 1.5. Shares = 100 / 1.5 = 66.666...
            # EURUSD qty_step = 0.01. So shares should be 66.67
            first_trade = res["trades"][0]
            self.assertEqual(first_trade["position_size"], 66.67)
            
    @patch("yfinance.download")
    def test_out_of_sample_split(self, mock_yf):
        df_mock = self.df.copy()
        mock_yf.return_value = df_mock
        with patch("backtester.calc_rsi") as mock_rsi, patch("backtester.calc_atr") as mock_atr:
            # Signal at index 2 (IS) and index 20 (OOS)
            mock_rsi.return_value = pd.Series([50, 50, 20] + [50]*17 + [20] + [50]*9, index=df_mock.index)
            mock_atr.return_value = pd.Series([1]*30, index=df_mock.index)
            
            # Split at 0.5 (first 15 rows IS, last 15 rows OOS)
            res = backtester.run_backtest("EURUSD", strategy="Mean Reversion", train_split=0.5, tp_atr=0.5, sl_atr=0.5)
            self.assertTrue(len(res["trades"]) == 2)
            self.assertFalse(res["trades"][0]["is_oos"])
            self.assertTrue(res["trades"][1]["is_oos"])
            self.assertIsNotNone(res["metrics_oos"])
            self.assertEqual(res["metrics_oos"]["Total Trades"], 1)

if __name__ == "__main__":
    unittest.main()
