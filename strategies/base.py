from abc import ABC, abstractmethod
import pandas as pd

class BaseStrategy(ABC):
    """
    Abstract Base Class for all deterministic TradeLogger strategies.
    A strategy must evaluate a market context (DataFrame) and return a standard setup dictionary.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """The human-readable name of the strategy (e.g., 'Trend Continuation')."""
        pass
        
    @property
    @abstractmethod
    def description(self) -> str:
        """A brief description of what the strategy does."""
        pass

    @property
    def version(self) -> str:
        """The semver version of the strategy for research run reproducibility (e.g. '1.1.0')."""
        return "1.0.0"

    @abstractmethod
    def analyze(self, df: pd.DataFrame, current_index: int, context: dict = None) -> dict:
        """
        Analyzes the market at `current_index`.
        
        Args:
            df (pd.DataFrame): The market data DataFrame.
            current_index (int): The index in the DataFrame currently being evaluated.
            context (dict, optional): Additional AI or factual data (e.g., macro risk). Defaults to None.
            
        Returns:
            dict: A standard setup dictionary containing:
                - status (str): "NO TRADE", "WATCHING", "WAITING", "READY", "INVALIDATED"
                - setup (str): "LONG" or "SHORT"
                - execution_model (str): "LIMIT" or "MARKET"
                - expiration_bars (int): Number of bars a limit order stays valid
                - entry_zone (str): Descriptive entry zone (e.g., "1.0500 - 1.0520")
                - ideal_entry (float or "N/A"): The exact entry price
                - stop_loss (float or "N/A"): The hard stop loss price
                - tp1 (float or "N/A"): Target 1 price
                - tp2 (float or "N/A"): Target 2 price
                - risk_reward (str): E.g., "1:2.5"
                - trigger (str): The logical condition that triggers execution
                - invalidation (str): The condition that invalidates the setup
                - confidence (str): "Low", "Medium", "High"
                - setup_quality (str): "A+", "A", "B", "C"
                - liquidity_type (str): E.g., "BSL_PDH", "SSL_ASIAN"
                - session (str): "ASIA", "LONDON", "NEW_YORK", or "OUT_OF_SESSION"
                - reason (str): Why no trade was taken, if status == "NO TRADE"
        """
        pass
        
    def build_no_trade(self, reason: str, context: dict = None) -> dict:
        """Helper to quickly return a NO TRADE payload."""
        return {
            "status": "NO TRADE",
            "setup": "N/A",
            "execution_model": "N/A",
            "expiration_bars": 0,
            "entry_zone": "N/A",
            "ideal_entry": "N/A",
            "stop_loss": "N/A",
            "tp1": "N/A",
            "tp2": "N/A",
            "risk_reward": "N/A",
            "trigger": "N/A",
            "invalidation": "N/A",
            "confidence": "N/A",
            "setup_quality": "N/A",
            "liquidity_type": "N/A",
            "liquidity_timeframe": "N/A",
            "session": "N/A",
            "reason": reason,
            "bias_timeframe": context.get('bias_tf', 'N/A') if context else 'N/A',
            "structure_timeframe": context.get('struct_tf', 'N/A') if context else 'N/A',
            "htf_bias": "N/A",
            "confluence_score": "0",
            "confluence_reasons": []
        }
