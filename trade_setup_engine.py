import pandas as pd
from strategies import get_strategy, get_all_strategy_names

class TradeSetupEngine:
    """
    TradeSetupEngine acts as the Live Execution Runner for the Modular Strategy Framework.
    It takes the raw market snapshot and the AI context, builds the DataFrame, and feeds it 
    into the selected Strategy for evaluation.
    """
    def __init__(self, ai_data, confluence, strategy_name="ICT 2022 Model"):
        self.ai_data = ai_data
        self.confluence = confluence
        self.symbol = ai_data.get('symbol', 'UNKNOWN')
        self.timeframe = ai_data.get('timeframe', 'UNKNOWN')
        
        # Load Strategy
        self.strategy_name = strategy_name
        self.strategy = get_strategy(strategy_name)
        if not self.strategy:
            # Fallback
            self.strategy = get_strategy("Trend Continuation")

    def determine_setup(self):
        """
        Main entry point to evaluate the current market context using the selected strategy.
        """
        # 1. Check macro/filter invalidations first
        if self._is_macro_blocked():
            return self.strategy.build_no_trade("HIGH MACRO RISK: Imminent high-impact news event.")
            
        # 2. Build the DataFrame from raw candles
        raw_candles = self.ai_data.get('raw_candles', [])
        if not raw_candles:
            return self.strategy.build_no_trade("No raw market data available.")
            
        df = pd.DataFrame(raw_candles)
        if df.empty or len(df) < 50:
            return self.strategy.build_no_trade("Insufficient candle data for strategy evaluation.")
            
        # Calculate ATR and basic indicators needed if not already present
        if 'ATR' not in df.columns:
            df['ATR'] = self.ai_data.get('factual_data', {}).get('atr', 0.001)
            
        # 3. Execute the Modular Strategy logic on the LIVE edge (current_index = len(df)-1)
        # We pass self.ai_data as the context for advanced strategies
        setup = self.strategy.analyze(df, current_index=len(df)-1, context=self.ai_data)
        
        # 4. Attach metadata for UI tracking
        setup['symbol'] = self.symbol
        setup['timeframe'] = self.timeframe
        
        # Ensure fallback defaults if strategy omitted them
        setup.setdefault('setup_quality', 'C')
        setup.setdefault('confidence', 'Medium')
        
        return setup

    def _is_macro_blocked(self):
        macro = self.ai_data.get('macro_data', {})
        macro_risk = macro.get('risk_level', 'LOW')
        # Block setups 30 mins before HIGH risk news
        if macro_risk == 'HIGH':
            return True
        return False
