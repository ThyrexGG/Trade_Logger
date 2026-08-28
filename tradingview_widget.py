import streamlit as st
from streamlit.components.v1 import html

DEFAULT_SYMBOLS = {
    "🥇 Gold (XAU/USD)": "OANDA:XAUUSD",
    "🚀 US Tech 100 (Nasdaq)": "FOREXCOM:NAS100USD",
    "📊 US 500 (S&P 500)": "FOREXCOM:SPX500USD",
    "💱 EUR/USD": "FX:EURUSD",
    "💱 GBP/USD": "FX:GBPUSD",
    "💱 USD/JPY": "FX:USDJPY",
    "₿ Bitcoin (BTC/USDT)": "BINANCE:BTCUSDT",
    "🛢️ US Crude Oil": "TVC:USOIL"
}

def render_tradingview_chart(symbol="OANDA:XAUUSD", interval="15", height=650):
    """
    Renders an interactive TradingView Advanced Real-Time Charting Widget.
    """
    tv_html = f"""
    <!-- TradingView Widget BEGIN -->
    <div class="tradingview-widget-container" style="height:100%;width:100%;border-radius:12px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,0.4);border:1px solid rgba(0,255,204,0.15);">
      <div id="tradingview_advanced_chart" style="height:{height}px;width:100%;"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {{
        "autosize": true,
        "symbol": "{symbol}",
        "interval": "{interval}",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "#0e131f",
        "enable_publishing": false,
        "hide_side_toolbar": false,
        "allow_symbol_change": true,
        "show_popup_button": true,
        "popup_width": "1000",
        "popup_height": "650",
        "container_id": "tradingview_advanced_chart",
        "studies": [
          "MASimple@tv-basicstudies",
          "RSI@tv-basicstudies"
        ],
        "overrides": {{
          "paneProperties.background": "#0c0f16",
          "paneProperties.vertGridProperties.color": "rgba(255, 255, 255, 0.04)",
          "paneProperties.horzGridProperties.color": "rgba(255, 255, 255, 0.04)",
          "mainSeriesProperties.candleStyle.upColor": "#00ffcc",
          "mainSeriesProperties.candleStyle.downColor": "#ff5555",
          "mainSeriesProperties.candleStyle.drawWick": true,
          "mainSeriesProperties.candleStyle.drawBorder": true,
          "mainSeriesProperties.candleStyle.borderColor": "#00ffcc",
          "mainSeriesProperties.candleStyle.borderUpColor": "#00ffcc",
          "mainSeriesProperties.candleStyle.borderDownColor": "#ff5555",
          "mainSeriesProperties.candleStyle.wickUpColor": "#00ffcc",
          "mainSeriesProperties.candleStyle.wickDownColor": "#ff5555"
        }}
      }}
      );
      </script>
    </div>
    <!-- TradingView Widget END -->
    """
    html(tv_html, height=height + 20)
