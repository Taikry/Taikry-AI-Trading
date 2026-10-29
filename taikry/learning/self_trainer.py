"""
AUTONOMOUS SELF-TRAINING & REINFORCEMENT LEARNING ENGINE
("ប្រព័ន្ធបណ្តុះបណ្តាលខ្លួនឯង / Self-Learning AI Agent Optimization")
====================================================================
Evaluates recorded agent opinions against resolved signal outcomes. It leaves
weights unchanged when there are no eligible outcomes to learn from.
"""

import datetime
import logging
from typing import Dict, Any, List, Optional

from taikry.database.session import SessionLocal
from taikry.database.models import (
    AgentLearningModel,
    XAUUSDTelegramSignalModel
)

logger = logging.getLogger("taikry.learning.self_trainer")

# Metadata and baseline configurations for registered analysis agents
AGENT_METADATA = {
    "ict_smc_analyst": {
        "name": "Agent 2: Institutional ICT / SMC Engine",
        "avatar": "🏛️",
        "specialization": "Liquidity Sweeps, Order Blocks & FVG Alignment",
        "color": "#8b5cf6",
        "baseline_weight": 0.30
    },
    "technical_analyst": {
        "name": "Agent 1: Multi-Timeframe Technical & Trend",
        "avatar": "📈",
        "specialization": "EMA Ribbons, RSI Momentum & Volume Breakouts",
        "color": "#06b6d4",
        "baseline_weight": 0.22
    },
    "risk_validator": {
        "name": "Agent 4: Capital Protection & Risk Arbiter",
        "avatar": "🛡️",
        "specialization": "Configurable paper-trading risk limits, negative R:R veto, and spread checks",
        "color": "#f59e0b",
        "baseline_weight": 0.18
    },
    "macro_analyst": {
        "name": "Agent 3: Macro Catalyst & DXY Cross-Check",
        "avatar": "🌐",
        "specialization": "Forex Factory News, Yields & Monetary Catalysts",
        "color": "#3b82f6",
        "baseline_weight": 0.14
    },
    "orderflow_sentiment_analyst": {
        "name": "Agent 8: Order Flow / CVD / Liquidity Sentiment",
        "avatar": "🌊",
        "specialization": "CVD Divergence, Volume Delta, Bid-Ask Absorption & Liquidity Pool Detection",
        "color": "#10b981",
        "baseline_weight": 0.08
    },
    "fractal_mtf_analyst": {
        "name": "Agent 9: Multi-Timeframe Fractal Trend Analyst",
        "avatar": "🔭",
        "specialization": "EMA Fractal Alignment D1/H4/H1/M15/M5, Counter-Trend Trap Detection",
        "color": "#f97316",
        "baseline_weight": 0.08
    }
}

# Default Baseline Ensemble Weights
DEFAULT_WEIGHTS = {aid: meta["baseline_weight"] for aid, meta in AGENT_METADATA.items()}


class AgentSelfTrainer:
    """Continuous Empirical Reinforcement and Self-Training Engine for AI Agents."""

    def __init__(self):
        self.learning_rate = 0.05
        self.total_epochs_run = 0

    @staticmethod
    def _normalize_weights(raw_weights: Dict[str, float]) -> Dict[str, float]:
        """Normalize weights to one while keeping each agent between 0.10 and 0.50."""
        lower, upper = 0.10, 0.50
        free = list(raw_weights)
        fixed: Dict[str, float] = {}
        remaining = 1.0

        while free:
            total = sum(max(float(raw_weights[key]), 0.0) for key in free)
            shares = {
                key: (remaining / len(free) if total <= 0 else remaining * max(float(raw_weights[key]), 0.0) / total)
                for key in free
            }
            clipped = [(key, lower if shares[key] < lower else upper) for key in free if shares[key] < lower or shares[key] > upper]
            if not clipped:
                fixed.update(shares)
                break
            for key, bound in clipped:
                fixed[key] = bound
                remaining -= bound
                free.remove(key)

        rounded = {key: round(value, 4) for key, value in fixed.items()}
        residue = round(1.0 - sum(rounded.values()), 4)
        if residue:
            for key in rounded:
                adjusted = round(rounded[key] + residue, 4)
                if lower <= adjusted <= upper:
                    rounded[key] = adjusted
                    break
        return rounded

    def get_current_agent_weights(self, symbol: str = "ALL") -> Dict[str, float]:
        """Retrieves active auto-tuned weights from database or defaults."""
        db = SessionLocal()
        try:
            records = db.query(AgentLearningModel).filter(
                AgentLearningModel.symbol.in_([symbol.upper(), "ALL", "XAUUSD"]),
                AgentLearningModel.training_version == 2
            ).order_by(AgentLearningModel.last_trained_at.desc(), AgentLearningModel.id.desc()).all()
            if records:
                weights = DEFAULT_WEIGHTS.copy()
                selected_priority: Dict[str, int] = {}
                for record in records:
                    if record.agent_id in weights:
                        priority = 3 if record.symbol == symbol.upper() else (2 if record.symbol == "ALL" else 1)
                        if priority > selected_priority.get(record.agent_id, 0):
                            weights[record.agent_id] = round(record.current_weight, 4)
                            selected_priority[record.agent_id] = priority
                return weights
        except Exception as e:
            logger.warning(f"Could not load weights from db: {e}")
        finally:
            db.close()
        return DEFAULT_WEIGHTS.copy()

    def evaluate_empirical_contributions(self, symbol: str = "XAUUSD") -> Dict[str, Dict[str, Any]]:
        """
        Scans resolved XAUUSD signal outcomes from persistent SQLite database.
        Extracts each individual agent's prediction at signal creation time and
        evaluates empirical correctness, win/loss record, and Brier quadratic error.
        """
        db = SessionLocal()
        stats = {
            aid: {
                "win_count": 0,
                "loss_count": 0,
                "neutral_count": 0,
                "total_evaluations": 0,
                "brier_sq_errors": [],
                "recent_outcomes": []
            }
            for aid in AGENT_METADATA.keys()
        }

        try:
            # 1. Evaluate dedicated XAUUSD Telegram signals with resolved outcomes
            resolved_xau = db.query(XAUUSDTelegramSignalModel).filter(
                XAUUSDTelegramSignalModel.canonical_symbol == symbol.upper(),
                XAUUSDTelegramSignalModel.outcome.in_(["WIN", "LOSS"])
            ).order_by(XAUUSDTelegramSignalModel.created_at.asc()).all()

            for sig in resolved_xau:
                trade_dir = sig.direction.upper()  # BUY or SELL
                is_win = (sig.outcome == "WIN")
                opinions = sig.agent_opinions or {}

                for aid in stats.keys():
                    agent_op = opinions.get(aid)
                    if not isinstance(agent_op, dict):
                        continue
                    bias = str(agent_op.get("bias", "NEUTRAL")).upper()
                    if bias not in {"BULLISH", "BUY", "LONG", "BEARISH", "SELL", "SHORT"}:
                        continue
                    try:
                        confidence_raw = float(agent_op.get("confidence"))
                    except (TypeError, ValueError):
                        confidence_raw = None
                    conf = confidence_raw / 100.0 if confidence_raw is not None and 0 <= confidence_raw <= 100 else None

                    is_aligned_buy = ("BULLISH" in bias or "BUY" in bias)
                    is_aligned_sell = ("BEARISH" in bias or "SELL" in bias)

                    if is_win:
                        # Trade was successful
                        if (trade_dir == "BUY" and is_aligned_buy) or (trade_dir == "SELL" and is_aligned_sell):
                            stats[aid]["win_count"] += 1
                            if conf is not None:
                                stats[aid]["brier_sq_errors"].append((1.0 - conf) ** 2)
                            stats[aid]["recent_outcomes"].append(1)
                        elif (trade_dir == "BUY" and is_aligned_sell) or (trade_dir == "SELL" and is_aligned_buy):
                            stats[aid]["loss_count"] += 1
                            if conf is not None:
                                stats[aid]["brier_sq_errors"].append((0.0 - conf) ** 2)
                            stats[aid]["recent_outcomes"].append(0)
                        else:
                            continue
                    else:
                        # Trade hit Stop Loss
                        if (trade_dir == "BUY" and is_aligned_buy) or (trade_dir == "SELL" and is_aligned_sell):
                            # Agent advocated losing trade
                            stats[aid]["loss_count"] += 1
                            if conf is not None:
                                stats[aid]["brier_sq_errors"].append((0.0 - conf) ** 2)
                            stats[aid]["recent_outcomes"].append(0)
                        elif (trade_dir == "BUY" and is_aligned_sell) or (trade_dir == "SELL" and is_aligned_buy) or ("WAIT" in bias or "REJECT" in bias):
                            # Agent opposed or warned against losing trade
                            stats[aid]["win_count"] += 1
                            if conf is not None:
                                stats[aid]["brier_sq_errors"].append((1.0 - conf) ** 2)
                            stats[aid]["recent_outcomes"].append(1)
                        else:
                            continue

                    stats[aid]["total_evaluations"] += 1

            return stats
        finally:
            db.close()

    def train_epoch(self, symbol: str = "XAUUSD", **kwargs) -> Dict[str, Any]:
        """
        Tunes agent weights only when resolved signal outcomes contain actual directional opinions.
        """
        db = SessionLocal()
        try:
            empirical_stats = self.evaluate_empirical_contributions(symbol)
            current_weights = self.get_current_agent_weights(symbol)
            measured = {
                aid: stats for aid, stats in empirical_stats.items()
                if stats.get("total_evaluations", 0) > 0
            }
            if not measured:
                return {
                    "epoch": self.total_epochs_run,
                    "symbol": symbol.upper(),
                    "status": "NO_TRAINING_DATA",
                    "message": "No resolved signal outcomes with recorded directional agent opinions are available.",
                    "message_kh": "មិនមានលទ្ធផលសញ្ញាដែលបានបិទ និងមតិទិសដៅរបស់ Agent ដើម្បីប្រើសម្រាប់ហ្វឹកហាត់ទេ។",
                    "updated_weights": current_weights,
                    "scorecard": []
                }

            accuracies: Dict[str, float] = {}
            brier_scores: Dict[str, Optional[float]] = {}
            for aid, s in measured.items():
                wins = s.get("win_count", 0)
                losses = s.get("loss_count", 0)
                total = wins + losses
                if total <= 0:
                    continue
                accuracies[aid] = round(wins / total * 100.0, 1)
                errors = s.get("brier_sq_errors", [])
                brier_scores[aid] = round(sum(errors) / len(errors), 3) if errors else None

            if not accuracies:
                return {
                    "epoch": self.total_epochs_run,
                    "symbol": symbol.upper(),
                    "status": "NO_TRAINING_DATA",
                    "message": "No measurable directional outcomes are available.",
                    "message_kh": "មិនមានលទ្ធផលទិសដៅដែលអាចវាស់វែងបានទេ។",
                    "updated_weights": current_weights,
                    "scorecard": []
                }

            mean_acc = sum(accuracies.values()) / len(accuracies)
            measured_brier = [score for score in brier_scores.values() if score is not None]
            mean_brier = sum(measured_brier) / len(measured_brier) if measured_brier else None

            raw_weights = {}
            for aid, meta in AGENT_METADATA.items():
                w_curr = current_weights.get(aid, meta["baseline_weight"])
                if aid in accuracies:
                    acc_delta = (accuracies[aid] - mean_acc) / 100.0
                    brier_delta = (mean_brier - brier_scores[aid]) if mean_brier is not None and brier_scores[aid] is not None else 0.0
                    w_curr += self.learning_rate * ((0.7 * acc_delta) + (0.3 * brier_delta))
                raw_weights[aid] = max(0.10, min(0.50, w_curr))

            normalized_weights = self._normalize_weights(raw_weights)

            now_utc = datetime.datetime.now(datetime.timezone.utc)
            scorecard = []

            # Persist to database (AgentLearningModel)
            for aid, meta in AGENT_METADATA.items():
                s = empirical_stats.get(aid, {})
                wins = s.get("win_count", 0)
                losses = s.get("loss_count", 0)
                tot = wins + losses

                rec = db.query(AgentLearningModel).filter(
                    AgentLearningModel.agent_id == aid,
                    AgentLearningModel.symbol == symbol.upper()
                ).order_by(AgentLearningModel.id.desc()).first()

                if not rec:
                    rec = AgentLearningModel(
                        agent_id=aid,
                        symbol=symbol.upper(),
                        current_weight=normalized_weights[aid],
                        accuracy_rate=accuracies.get(aid, 0.0),
                        win_trades_count=wins,
                        loss_trades_count=losses,
                        total_evaluations=tot,
                        brier_score=brier_scores.get(aid) or 0.0,
                        learning_rate=self.learning_rate,
                        training_version=2,
                        last_trained_at=now_utc
                    )
                    db.add(rec)
                else:
                    rec.current_weight = normalized_weights[aid]
                    rec.accuracy_rate = accuracies.get(aid, 0.0)
                    rec.win_trades_count = wins
                    rec.loss_trades_count = losses
                    rec.total_evaluations = tot
                    rec.brier_score = brier_scores.get(aid) or 0.0
                    rec.learning_rate = self.learning_rate
                    rec.training_version = 2
                    rec.last_trained_at = now_utc

                if aid in accuracies:
                    status_label = "CALIBRATED" if accuracies[aid] >= 75.0 else "OPTIMIZING"
                    scorecard.append({
                        "agent_id": aid,
                        "name": meta["name"],
                        "avatar": meta["avatar"],
                        "specialization": meta["specialization"],
                        "weight": normalized_weights[aid],
                        "accuracy": accuracies[aid],
                        "win_count": wins,
                        "loss_count": losses,
                        "brier_score": brier_scores[aid],
                        "status": status_label,
                        "sample_size": wins + losses
                    })

            db.commit()
            self.total_epochs_run += 1

            return {
                "epoch": self.total_epochs_run,
                "symbol": symbol.upper(),
                "status": "EPOCH_COMPLETED",
                "stage": "WEIGHTS_OPTIMIZED",
                "message": f"Training run #{self.total_epochs_run} completed from {sum(s.get('total_evaluations', 0) for s in measured.values())} resolved agent opinions.",
                "message_kh": f"ការហ្វឹកហាត់លើកទី #{self.total_epochs_run} បានបញ្ចប់ ដោយប្រើមតិ Agent ដែលមានលទ្ធផលច្បាស់ {sum(s.get('total_evaluations', 0) for s in measured.values())}។",
                "updated_weights": normalized_weights,
                "optimized_weights": normalized_weights,
                "scorecard": scorecard,
                "mean_accuracy": round(mean_acc, 1),
                "timestamp": now_utc.isoformat()
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Error in train_epoch: {e}")
            return {
                "epoch": self.total_epochs_run,
                "status": "FAILED",
                "optimized_weights": DEFAULT_WEIGHTS,
                "error": str(e)
            }
        finally:
            db.close()

    def get_learning_stats(self, symbol: str = "XAUUSD") -> Dict[str, Any]:
        """Returns observed signal outcomes; unavailable accuracy is reported as null."""
        weights = self.get_current_agent_weights(symbol)
        observed = self.evaluate_empirical_contributions(symbol)
        agents_scorecard = []
        total_evaluations = 0
        total_wins = 0
        for aid, meta in AGENT_METADATA.items():
            stats = observed.get(aid, {})
            wins = int(stats.get("win_count", 0))
            losses = int(stats.get("loss_count", 0))
            sample_size = wins + losses
            accuracy = round(wins / sample_size * 100.0, 1) if sample_size else None
            errors = stats.get("brier_sq_errors", [])
            brier = round(sum(errors) / len(errors), 3) if errors else None
            total_evaluations += sample_size
            total_wins += wins
            agents_scorecard.append({
                "agent_id": aid,
                "name": meta["name"],
                "avatar": meta["avatar"],
                "specialization": meta["specialization"],
                "weight": round(weights.get(aid, meta["baseline_weight"]), 4),
                "accuracy": accuracy,
                "win_count": wins,
                "loss_count": losses,
                "sample_size": sample_size,
                "brier_score": brier,
                "status": "MEASURED" if sample_size else "NO_RESOLVED_DATA"
            })

        return {
            "total_epochs": self.total_epochs_run,
            "training_runs_this_process": self.total_epochs_run,
            "overall_accuracy": round(total_wins / total_evaluations * 100.0, 1) if total_evaluations else None,
            "training_data_count": total_evaluations,
            "learning_rate": self.learning_rate,
            "reinforcement_policy": "Empirical Reinforcement Multi-Agent Recalibration (ERMR)",
            "weights": weights,
            "agents_scorecard": agents_scorecard,
            "loss_curve": [],
            "last_trained_utc": None
        }


# Global singleton
agent_self_trainer = AgentSelfTrainer()
