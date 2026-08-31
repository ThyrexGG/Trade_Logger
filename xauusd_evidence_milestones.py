"""
Phase 28 — XAUUSD Evidence Milestone Engine
Tracks forward sample accumulation milestones (N = 30, 50, 75, 100, 125, 150, 200),
evaluates statistical reliability tiers, completion percentages, and documents what remains unknown.
"""

from typing import Dict, List, Any


class EvidenceMilestoneEngine:
    """
    Evaluates progressive sample size milestones and evidence reliability.
    """
    MILESTONE_DEFINITIONS = [
        {
            "target_n": 30,
            "stage_name": "Stage 1 (Early Evidence)",
            "reliability_tier": "LIMITED SAMPLE",
            "evidence_quality": "Initial directional tendency; high statistical uncertainty.",
            "what_remains_unknown": "Whether performance is consistent across multiple quarterly macro regimes.",
            "human_meaning": "We have enough observations to start monitoring directional behavior, but not enough to evaluate structural edge."
        },
        {
            "target_n": 50,
            "stage_name": "Stage 2 (Forward Validation)",
            "reliability_tier": "MODERATE SAMPLE",
            "evidence_quality": "Multi-month regime diversification; preliminary confidence interval narrowing.",
            "what_remains_unknown": "How the strategy absorbs prolonged high-volatility news events or extended liquidity droughts.",
            "human_meaning": "We have enough observations to evaluate directional consistency, but not enough to treat the forward result as fully established."
        },
        {
            "target_n": 75,
            "stage_name": "Intermediate Validation",
            "reliability_tier": "EXPANDED MODERATE SAMPLE",
            "evidence_quality": "Subgroup stability across London, NY, and Overlap trading sessions.",
            "what_remains_unknown": "Long-term tail-risk behavior and maximum multi-month excursion bounds.",
            "human_meaning": "Session-level distributions are stabilizing, but sample size remains below formal human review threshold."
        },
        {
            "target_n": 100,
            "stage_name": "Stage 3 (Human Review Eligibility)",
            "reliability_tier": "STRONG EVIDENCE",
            "evidence_quality": "Sufficient statistical power to assess baseline retention and reject zero-expectancy null hypothesis if CI lower > 0.",
            "what_remains_unknown": "Long-term macroeconomic structural shifts spanning multiple calendar years.",
            "human_meaning": "The sample size satisfies formal research criteria to compile a complete dossier for Human Review. Live trading remains permanently disabled."
        },
        {
            "target_n": 125,
            "stage_name": "Extended Validation Tier 1",
            "reliability_tier": "HIGH PRECISION",
            "evidence_quality": "Narrow confidence interval width with tight standard errors.",
            "what_remains_unknown": "Impact of major central bank policy regime pivots.",
            "human_meaning": "Provides higher statistical precision to verify that positive expectancy is not a temporary statistical artifact."
        },
        {
            "target_n": 150,
            "stage_name": "Extended Validation Tier 2",
            "reliability_tier": "ROBUST SAMPLE",
            "evidence_quality": "Longitudinal stability across full multi-month market cycles.",
            "what_remains_unknown": "Unprecedented geopolitical black swan market dislocations.",
            "human_meaning": "Substantially eliminates sampling noise and provides clear empirical distribution parameters."
        },
        {
            "target_n": 200,
            "stage_name": "Longitudinal Benchmark",
            "reliability_tier": "DEFINITIVE RESEARCH SAMPLE",
            "evidence_quality": "Comprehensive statistical certainty matching or exceeding historical training datasets.",
            "what_remains_unknown": "Future structural microstructure market reforms.",
            "human_meaning": "Comprehensive longitudinal validation sample offering maximum empirical rigor."
        }
    ]

    @staticmethod
    def evaluate_milestones(current_n: int) -> Dict[str, Any]:
        """
        Evaluates current progress against all predefined milestones.
        """
        milestone_cards = []
        next_milestone_info = None

        for m in EvidenceMilestoneEngine.MILESTONE_DEFINITIONS:
            target = m["target_n"]
            is_reached = current_n >= target
            remaining = max(0, target - current_n)
            pct = min(100.0, (current_n / target) * 100.0) if target > 0 else 0.0

            card = {
                "target_n": target,
                "stage_name": m["stage_name"],
                "reliability_tier": m["reliability_tier"],
                "is_reached": is_reached,
                "current_n": current_n,
                "remaining_trades": remaining,
                "pct_completion": round(pct, 1),
                "evidence_quality": m["evidence_quality"],
                "what_remains_unknown": m["what_remains_unknown"],
                "human_meaning": m["human_meaning"]
            }
            milestone_cards.append(card)

            if not is_reached and next_milestone_info is None:
                next_milestone_info = card

        if next_milestone_info is None:
            next_milestone_info = milestone_cards[-1]

        # Overall sample tier
        if current_n < 30:
            current_tier = "INSUFFICIENT DATA"
        elif current_n < 50:
            current_tier = "LIMITED SAMPLE"
        elif current_n < 100:
            current_tier = "MODERATE SAMPLE"
        else:
            current_tier = "STRONG EVIDENCE"

        return {
            "current_n": current_n,
            "current_tier": current_tier,
            "next_milestone_target": next_milestone_info["target_n"],
            "next_milestone_remaining": next_milestone_info["remaining_trades"],
            "next_milestone_stage": next_milestone_info["stage_name"],
            "next_milestone_human_meaning": next_milestone_info["human_meaning"],
            "milestones": milestone_cards
        }
