# -*- coding: utf-8 -*-
"""
FastAPI Risk Router — Stage 3 Pre-Trade Risk Calculation Preview Endpoint
Strictly calculation-only. Prohibits order creation, mutation, and live broker transmission.
Directly consumes authoritative risk_gateway.calculate_pre_trade_risk_preview().
"""
from fastapi import APIRouter
from api.schemas import RiskPreviewRequest, RiskPreviewResponse
from risk_gateway import calculate_pre_trade_risk_preview

router = APIRouter(prefix="/api/risk", tags=["Risk Gateway"])


@router.post("/preview", response_model=RiskPreviewResponse)
async def preview_pre_trade_risk(req: RiskPreviewRequest) -> RiskPreviewResponse:
    """
    Calculates pre-trade position sizing, lot size, worst-case risk, reward targets,
    and portfolio correlation constraints using the authoritative risk gateway.
    Does NOT transmit orders, mutate state, or execute trades.
    """
    raw_preview = calculate_pre_trade_risk_preview(
        symbol=req.symbol,
        side=req.side,
        entry_price=req.entry_price,
        stop_loss=req.stop_loss,
        take_profit_1=req.take_profit_1,
        take_profit_2=req.take_profit_2,
        requested_risk_pct=req.requested_risk_pct,
        account_balance=req.account_balance
    )

    return RiskPreviewResponse(
        symbol=raw_preview["symbol"],
        side=raw_preview["side"],
        entry_price=raw_preview["entry_price"],
        stop_loss=raw_preview["stop_loss"],
        take_profit_1=raw_preview["take_profit_1"],
        take_profit_2=raw_preview["take_profit_2"],
        account_balance=raw_preview["account_balance"],
        target_risk_usd=raw_preview["target_risk_usd"],
        calculated_lot_size=raw_preview["calculated_lot_size"],
        actual_risk_usd=raw_preview["actual_risk_usd"],
        actual_risk_pct=raw_preview["actual_risk_pct"],
        reward_tp1_usd=raw_preview["reward_tp1_usd"],
        reward_tp1_pct=raw_preview["reward_tp1_pct"],
        reward_tp2_usd=raw_preview["reward_tp2_usd"],
        reward_tp2_pct=raw_preview["reward_tp2_pct"],
        risk_reward_ratio=raw_preview["risk_reward_ratio"],
        estimated_margin_usd=raw_preview["estimated_margin_usd"],
        is_valid=raw_preview["is_valid"],
        warnings=raw_preview["warnings"],
        errors=raw_preview["errors"],
        live_broker_transmission="BLOCKED"
    )
