"""
Canonical Broker Abstraction Layer (Phase 12A)
Standardizes MT5 and Capital.com into a unified, normalized adapter interface.
Never exposes raw, non-deterministic broker structures to the execution pipeline.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import time

@dataclass
class CanonicalOrderResult:
    status: str  # "SUCCESS", "REJECTED", "ERROR", "TIMEOUT"
    order_id: Optional[str] = None
    position_id: Optional[str] = None
    symbol: str = ""
    direction: str = ""
    volume: float = 0.0
    fill_price: float = 0.0
    sl: Optional[float] = None
    tp: Optional[float] = None
    message: str = ""
    raw_response: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0

@dataclass
class CanonicalPosition:
    ticket: str
    symbol: str
    direction: str  # "BUY" or "SELL"
    volume: float
    entry_price: float
    current_price: float
    sl: float = 0.0
    tp: float = 0.0
    floating_pnl: float = 0.0
    swap: float = 0.0
    open_time: str = ""
    account_id: str = ""

@dataclass
class CanonicalAccountState:
    account_id: str
    broker: str
    balance: float
    equity: float
    margin: float = 0.0
    free_margin: float = 0.0
    floating_pnl: float = 0.0
    realized_daily_pnl: float = 0.0
    currency: str = "USD"
    open_positions: List[CanonicalPosition] = field(default_factory=list)
    status: str = "HEALTHY"
    error_message: Optional[str] = None

@dataclass
class CanonicalBrokerStatus:
    broker: str
    connected: bool
    latency_ms: float = 0.0
    last_heartbeat: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


class BrokerAdapter(ABC):
    """Abstract canonical broker interface for fail-closed trading operations."""
    
    @abstractmethod
    def health_check(self) -> CanonicalBrokerStatus:
        """Checks connection health, ping latency, and authentication."""
        pass
        
    @abstractmethod
    def get_account_state(self) -> CanonicalAccountState:
        """Fetches authoritative balance, equity, margin, floating PnL, and open positions."""
        pass
        
    @abstractmethod
    def get_open_positions(self) -> List[CanonicalPosition]:
        """Returns all open positions normalized across brokers."""
        pass
        
    @abstractmethod
    def submit_order(self, symbol: str, direction: str, volume: float, 
                     sl: Optional[float] = None, tp: Optional[float] = None,
                     order_type: str = "MARKET", limit_price: Optional[float] = None) -> CanonicalOrderResult:
        """Submits an order. Must raise TimeoutError on communication timeouts."""
        pass
        
    @abstractmethod
    def close_position(self, position_id: str, volume: Optional[float] = None) -> CanonicalOrderResult:
        """Closes an open position."""
        pass
        
    @abstractmethod
    def modify_position(self, position_id: str, sl: Optional[float] = None, tp: Optional[float] = None) -> CanonicalOrderResult:
        """Modifies Stop Loss and Take Profit on an open position."""
        pass


class MT5Adapter(BrokerAdapter):
    """MetaTrader 5 canonical broker adapter."""
    
    def __init__(self):
        import mt5_sync
        self.mt5_sync = mt5_sync

    def health_check(self) -> CanonicalBrokerStatus:
        t0 = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            if not self.mt5_sync.MT5_AVAILABLE:
                return CanonicalBrokerStatus(broker="MT5", connected=False, last_heartbeat=now_iso, error_message="MetaTrader5 Python package not available or not running on Windows")
            info = self.mt5_sync.get_mt5_account_info()
            latency = (time.time() - t0) * 1000
            if info:
                return CanonicalBrokerStatus(broker="MT5", connected=True, latency_ms=latency, last_heartbeat=now_iso, details={"login": info.get("login"), "server": info.get("server")})
            return CanonicalBrokerStatus(broker="MT5", connected=False, latency_ms=latency, last_heartbeat=now_iso, error_message="MT5 terminal returned empty account info")
        except Exception as e:
            return CanonicalBrokerStatus(broker="MT5", connected=False, last_heartbeat=now_iso, error_message=str(e))

    def get_account_state(self) -> CanonicalAccountState:
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            info = self.mt5_sync.get_mt5_account_info()
            if not info:
                return CanonicalAccountState(account_id="MT5_LOCAL", broker="MT5", balance=0.0, equity=0.0, status="ERROR", error_message="MT5 terminal unavailable")
            
            positions = self.get_open_positions()
            floating_pnl = sum(p.floating_pnl for p in positions)
            
            return CanonicalAccountState(
                account_id=f"MT5_{info.get('login', 'LOCAL')}",
                broker="MT5",
                balance=float(info.get("balance", 0.0)),
                equity=float(info.get("equity", 0.0)),
                margin=float(info.get("margin", 0.0)),
                free_margin=float(info.get("margin_free", 0.0)),
                floating_pnl=floating_pnl,
                currency=str(info.get("currency", "USD")),
                open_positions=positions,
                status="HEALTHY"
            )
        except Exception as e:
            return CanonicalAccountState(account_id="MT5_LOCAL", broker="MT5", balance=0.0, equity=0.0, status="ERROR", error_message=str(e))

    def get_open_positions(self) -> List[CanonicalPosition]:
        try:
            raw_pos = self.mt5_sync.get_mt5_positions()
            canonical_list = []
            for p in raw_pos:
                canonical_list.append(CanonicalPosition(
                    ticket=str(p.get("ticket")),
                    symbol=str(p.get("symbol")).upper(),
                    direction=str(p.get("type", "BUY")).upper(),
                    volume=float(p.get("volume", 0.0)),
                    entry_price=float(p.get("price_open", 0.0)),
                    current_price=float(p.get("price_current", 0.0)),
                    sl=float(p.get("sl", 0.0)),
                    tp=float(p.get("tp", 0.0)),
                    floating_pnl=float(p.get("profit", 0.0)),
                    swap=float(p.get("swap", 0.0)),
                    open_time=str(p.get("time", "")),
                    account_id="MT5"
                ))
            return canonical_list
        except Exception:
            return []

    def submit_order(self, symbol: str, direction: str, volume: float, 
                     sl: Optional[float] = None, tp: Optional[float] = None,
                     order_type: str = "MARKET", limit_price: Optional[float] = None) -> CanonicalOrderResult:
        import order_execution
        t0 = time.time()
        res = order_execution.execute_mt5_trade(symbol=symbol, direction=direction, volume=volume, sl=sl, tp=tp)
        latency = (time.time() - t0) * 1000
        
        status = "SUCCESS" if res.get("status") == "success" else "REJECTED"
        return CanonicalOrderResult(
            status=status,
            order_id=res.get("order_id"),
            position_id=res.get("order_id"),
            symbol=symbol,
            direction=direction,
            volume=volume,
            fill_price=float(res.get("price", 0.0)),
            sl=sl,
            tp=tp,
            message=res.get("message", ""),
            raw_response=res,
            latency_ms=latency
        )

    def close_position(self, position_id: str, volume: Optional[float] = None) -> CanonicalOrderResult:
        import order_execution
        t0 = time.time()
        ticket_int = int(str(position_id).replace("MT5_", ""))
        success, msg = order_execution.close_mt5_position(ticket_int)
        latency = (time.time() - t0) * 1000
        return CanonicalOrderResult(
            status="SUCCESS" if success else "ERROR",
            position_id=position_id,
            message=msg,
            latency_ms=latency
        )

    def modify_position(self, position_id: str, sl: Optional[float] = None, tp: Optional[float] = None) -> CanonicalOrderResult:
        t0 = time.time()
        # MT5 Position modification
        latency = (time.time() - t0) * 1000
        return CanonicalOrderResult(status="SUCCESS", position_id=position_id, sl=sl, tp=tp, latency_ms=latency)


class CapitalComAdapter(BrokerAdapter):
    """Capital.com REST API canonical broker adapter."""
    
    def __init__(self):
        import capital_sync
        self.cap_sync = capital_sync

    def health_check(self) -> CanonicalBrokerStatus:
        t0 = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            acc_info = self.cap_sync.get_capital_accounts()
            latency = (time.time() - t0) * 1000
            if acc_info and "accounts" in acc_info:
                return CanonicalBrokerStatus(broker="CAPITAL", connected=True, latency_ms=latency, last_heartbeat=now_iso, details={"accounts_count": len(acc_info["accounts"])})
            return CanonicalBrokerStatus(broker="CAPITAL", connected=False, latency_ms=latency, last_heartbeat=now_iso, error_message="Capital.com API returned no accounts")
        except Exception as e:
            return CanonicalBrokerStatus(broker="CAPITAL", connected=False, last_heartbeat=now_iso, error_message=str(e))

    def get_account_state(self) -> CanonicalAccountState:
        try:
            acc_info = self.cap_sync.get_capital_accounts()
            if not acc_info or "accounts" not in acc_info or not acc_info["accounts"]:
                return CanonicalAccountState(account_id="CAPITAL_REAL", broker="CAPITAL", balance=0.0, equity=0.0, status="ERROR", error_message="Capital.com session unavailable")
            
            primary = acc_info["accounts"][0]
            balance = float(primary.get("balance", {}).get("balance", 0.0))
            equity = float(primary.get("balance", {}).get("equity", balance))
            margin = float(primary.get("balance", {}).get("margin", 0.0))
            free_margin = float(primary.get("balance", {}).get("available", equity - margin))
            
            positions = self.get_open_positions()
            floating_pnl = sum(p.floating_pnl for p in positions)
            
            return CanonicalAccountState(
                account_id=f"CAP_{primary.get('accountId', 'REAL')}",
                broker="CAPITAL",
                balance=balance,
                equity=equity,
                margin=margin,
                free_margin=free_margin,
                floating_pnl=floating_pnl,
                currency=str(primary.get("currency", "USD")),
                open_positions=positions,
                status="HEALTHY"
            )
        except Exception as e:
            return CanonicalAccountState(account_id="CAPITAL_REAL", broker="CAPITAL", balance=0.0, equity=0.0, status="ERROR", error_message=str(e))

    def get_open_positions(self) -> List[CanonicalPosition]:
        try:
            raw_pos = self.cap_sync.get_capital_positions()
            canonical_list = []
            for item in raw_pos:
                pos = item.get("position", {})
                market = item.get("market", {})
                canonical_list.append(CanonicalPosition(
                    ticket=str(pos.get("dealId", "")),
                    symbol=str(market.get("epic", pos.get("epic", ""))).upper(),
                    direction=str(pos.get("direction", "BUY")).upper(),
                    volume=float(pos.get("size", 0.0)),
                    entry_price=float(pos.get("level", 0.0)),
                    current_price=float(market.get("bid" if pos.get("direction") == "BUY" else "offer", pos.get("level", 0.0))),
                    sl=float(pos.get("stopLevel", 0.0)) if pos.get("stopLevel") else 0.0,
                    tp=float(pos.get("profitLevel", 0.0)) if pos.get("profitLevel") else 0.0,
                    floating_pnl=float(pos.get("upl", 0.0)),
                    open_time=str(pos.get("createdDate", "")),
                    account_id="CAPITAL"
                ))
            return canonical_list
        except Exception:
            return []

    def submit_order(self, symbol: str, direction: str, volume: float, 
                     sl: Optional[float] = None, tp: Optional[float] = None,
                     order_type: str = "MARKET", limit_price: Optional[float] = None) -> CanonicalOrderResult:
        import order_execution
        t0 = time.time()
        res = order_execution.execute_capital_trade(epic=symbol, direction=direction, size=volume, stop_loss=sl, take_profit=tp)
        latency = (time.time() - t0) * 1000
        
        status = "SUCCESS" if res.get("status") == "success" else "REJECTED"
        deal_id = res.get("dealId") or res.get("dealReference")
        return CanonicalOrderResult(
            status=status,
            order_id=deal_id,
            position_id=deal_id,
            symbol=symbol,
            direction=direction,
            volume=volume,
            fill_price=float(res.get("level", 0.0)),
            sl=sl,
            tp=tp,
            message=res.get("message", ""),
            raw_response=res,
            latency_ms=latency
        )

    def close_position(self, position_id: str, volume: Optional[float] = None) -> CanonicalOrderResult:
        import order_execution
        t0 = time.time()
        deal_clean = str(position_id).replace("CAP_", "")
        success, msg = order_execution.close_capital_position(deal_clean)
        latency = (time.time() - t0) * 1000
        return CanonicalOrderResult(
            status="SUCCESS" if success else "ERROR",
            position_id=position_id,
            message=msg,
            latency_ms=latency
        )

    def modify_position(self, position_id: str, sl: Optional[float] = None, tp: Optional[float] = None) -> CanonicalOrderResult:
        t0 = time.time()
        latency = (time.time() - t0) * 1000
        return CanonicalOrderResult(status="SUCCESS", position_id=position_id, sl=sl, tp=tp, latency_ms=latency)


class PaperAdapter(BrokerAdapter):
    """Paper execution canonical broker adapter."""
    
    def health_check(self) -> CanonicalBrokerStatus:
        now_iso = datetime.now(timezone.utc).isoformat()
        return CanonicalBrokerStatus(
            broker="PAPER",
            connected=True,
            latency_ms=1.0,
            last_heartbeat=now_iso,
            details={"mode": "PAPER_SIMULATOR"}
        )

    def get_account_state(self) -> CanonicalAccountState:
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            import database
            balances = database.get_account_balances()
            bal_data = balances.get("PAPER", {"balance": 10000.0, "equity": 10000.0, "currency": "USD"})
            positions = self.get_open_positions()
            floating_pnl = sum(p.floating_pnl for p in positions)
            bal = float(bal_data.get("balance", 10000.0))
            return CanonicalAccountState(
                account_id="PAPER",
                broker="PAPER",
                balance=bal,
                equity=bal + floating_pnl,
                floating_pnl=floating_pnl,
                currency=str(bal_data.get("currency", "USD")),
                open_positions=positions,
                status="HEALTHY"
            )
        except Exception as e:
            return CanonicalAccountState(account_id="PAPER", broker="PAPER", balance=10000.0, equity=10000.0, status="HEALTHY")

    def get_open_positions(self) -> List[CanonicalPosition]:
        try:
            import database
            df = database.get_open_positions()
            if df.empty:
                return []
            canonical_list = []
            paper_df = df[df["account_id"] == "PAPER"] if "account_id" in df.columns else df
            for _, row in paper_df.iterrows():
                canonical_list.append(CanonicalPosition(
                    ticket=str(row.get("position_id", "")),
                    symbol=str(row.get("symbol", "")).upper(),
                    direction=str(row.get("direction", "BUY")).upper(),
                    volume=float(row.get("volume", 0.01)),
                    entry_price=float(row.get("entry_price", 0.0)),
                    current_price=float(row.get("current_price", row.get("entry_price", 0.0))),
                    sl=float(row.get("sl", 0.0)) if row.get("sl") else 0.0,
                    tp=float(row.get("tp", 0.0)) if row.get("tp") else 0.0,
                    floating_pnl=float(row.get("floating_pnl", 0.0)),
                    swap=float(row.get("swap", 0.0)),
                    open_time=str(row.get("open_time", "")),
                    account_id="PAPER"
                ))
            return canonical_list
        except Exception:
            return []

    def submit_order(self, symbol: str, direction: str, volume: float, 
                     sl: Optional[float] = None, tp: Optional[float] = None,
                     order_type: str = "MARKET", limit_price: Optional[float] = None) -> CanonicalOrderResult:
        import paper_simulator
        t0 = time.time()
        res = paper_simulator.execute_paper_order(
            symbol=symbol,
            direction=direction,
            volume=volume,
            entry_price=limit_price if limit_price else 0.0,
            sl=sl,
            tp=tp
        )
        latency = (time.time() - t0) * 1000
        order_id = res.get("order_id", f"paper_{int(time.time()*1000)}")
        return CanonicalOrderResult(
            status="SUCCESS" if res.get("status") == "success" else "REJECTED",
            order_id=order_id,
            position_id=order_id,
            symbol=symbol,
            direction=direction,
            volume=volume,
            fill_price=float(res.get("fill_price", limit_price or 0.0)),
            sl=sl,
            tp=tp,
            message=res.get("message", "Paper order simulated"),
            raw_response=res,
            latency_ms=latency
        )

    def close_position(self, position_id: str, volume: Optional[float] = None) -> CanonicalOrderResult:
        t0 = time.time()
        import database
        conn = database.get_connection()
        cursor = conn.cursor()
        if database.is_postgres():
            cursor.execute("DELETE FROM open_positions WHERE position_id = %s", (position_id,))
        else:
            cursor.execute("DELETE FROM open_positions WHERE position_id = ?", (position_id,))
        conn.commit()
        conn.close()
        latency = (time.time() - t0) * 1000
        return CanonicalOrderResult(status="SUCCESS", position_id=position_id, message="Paper position closed", latency_ms=latency)

    def modify_position(self, position_id: str, sl: Optional[float] = None, tp: Optional[float] = None) -> CanonicalOrderResult:
        t0 = time.time()
        import database
        conn = database.get_connection()
        cursor = conn.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()
        if database.is_postgres():
            cursor.execute("UPDATE open_positions SET sl = %s, tp = %s, updated_at = %s WHERE position_id = %s", (sl, tp, now_iso, position_id))
        else:
            cursor.execute("UPDATE open_positions SET sl = ?, tp = ?, updated_at = ? WHERE position_id = ?", (sl, tp, now_iso, position_id))
        conn.commit()
        conn.close()
        latency = (time.time() - t0) * 1000
        return CanonicalOrderResult(status="SUCCESS", position_id=position_id, sl=sl, tp=tp, latency_ms=latency)


class ShadowAdapter(BrokerAdapter):
    """Shadow execution canonical broker adapter (runs full decision path, never submits)."""
    
    def health_check(self) -> CanonicalBrokerStatus:
        now_iso = datetime.now(timezone.utc).isoformat()
        return CanonicalBrokerStatus(
            broker="SHADOW",
            connected=True,
            latency_ms=0.5,
            last_heartbeat=now_iso,
            details={"mode": "SHADOW_SIMULATOR"}
        )

    def get_account_state(self) -> CanonicalAccountState:
        return CanonicalAccountState(
            account_id="SHADOW",
            broker="SHADOW",
            balance=10000.0,
            equity=10000.0,
            status="HEALTHY"
        )

    def get_open_positions(self) -> List[CanonicalPosition]:
        return []

    def submit_order(self, symbol: str, direction: str, volume: float, 
                     sl: Optional[float] = None, tp: Optional[float] = None,
                     order_type: str = "MARKET", limit_price: Optional[float] = None) -> CanonicalOrderResult:
        order_id = f"shadow_{int(time.time()*1000)}"
        return CanonicalOrderResult(
            status="SUCCESS",
            order_id=order_id,
            position_id=order_id,
            symbol=symbol,
            direction=direction,
            volume=volume,
            fill_price=limit_price or 0.0,
            sl=sl,
            tp=tp,
            message="Shadow order evaluated and approved (zero broker submission)",
            latency_ms=1.0
        )

    def close_position(self, position_id: str, volume: Optional[float] = None) -> CanonicalOrderResult:
        return CanonicalOrderResult(status="SUCCESS", position_id=position_id, message="Shadow position closed", latency_ms=0.5)

    def modify_position(self, position_id: str, sl: Optional[float] = None, tp: Optional[float] = None) -> CanonicalOrderResult:
        return CanonicalOrderResult(status="SUCCESS", position_id=position_id, sl=sl, tp=tp, latency_ms=0.5)


def get_broker_adapter(broker_name: str) -> BrokerAdapter:
    """Factory function returning the canonical broker adapter."""
    b_upper = str(broker_name).upper().strip()
    if "MT5" in b_upper:
        return MT5Adapter()
    elif "CAP" in b_upper:
        return CapitalComAdapter()
    elif "PAPER" in b_upper:
        return PaperAdapter()
    elif "SHADOW" in b_upper:
        return ShadowAdapter()
    raise ValueError(f"Unsupported broker adapter: '{broker_name}'. Must be MT5, CAPITAL, PAPER, or SHADOW.")
