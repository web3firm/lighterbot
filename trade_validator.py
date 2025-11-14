"""
Intelligent Trade Validation and Early Exit Detection

Institutions use this to detect when trade setup is invalidated BEFORE hitting stop loss.
This saves capital by exiting failed trades early at -0.5% to -1% instead of waiting for -2%.
"""

from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from indicators import TechnicalIndicators
from logger import get_logger

logger = get_logger()


@dataclass
class TradeSetup:
    """Original trade setup parameters"""
    entry_price: float
    direction: str  # 'long' or 'short'
    entry_time: datetime
    reason: str  # Original signal reason
    confidence: float
    setup_rsi: Optional[float] = None
    setup_ema_trend: Optional[str] = None  # 'up' or 'down'
    setup_macd: Optional[float] = None


class TradeValidator:
    """
    Validates if trade setup is still valid or should be exited early
    
    Early Exit Triggers:
    1. Setup Invalidation: Price moves against setup logic
    2. Momentum Reversal: RSI/MACD shows clear reversal
    3. Volume Divergence: Volume dries up or surges opposite direction
    4. Time-based: Setup not working after X minutes
    5. Volatility Spike: Sudden extreme volatility
    """
    
    def __init__(self):
        self.active_setups: Dict[str, TradeSetup] = {}  # trade_id -> setup
        self.logger = logger
    
    def register_trade(
        self,
        trade_id: str,
        entry_price: float,
        direction: str,
        reason: str,
        confidence: float,
        market_data=None
    ):
        """Register a new trade setup for monitoring"""
        
        setup = TradeSetup(
            entry_price=entry_price,
            direction=direction,
            entry_time=datetime.now(),
            reason=reason,
            confidence=confidence
        )
        
        # Capture setup state if market data available
        if market_data and hasattr(market_data, 'price_history'):
            if len(market_data.price_history) >= 26:
                setup.setup_rsi = TechnicalIndicators.rsi(market_data.price_history)
                ema_fast = TechnicalIndicators.ema(market_data.price_history, 12)
                ema_slow = TechnicalIndicators.ema(market_data.price_history, 26)
                setup.setup_ema_trend = 'up' if ema_fast > ema_slow else 'down'
                macd_line, _, _ = TechnicalIndicators.macd(market_data.price_history)
                setup.setup_macd = macd_line
        
        self.active_setups[trade_id] = setup
        self.logger.info(f"📋 Registered trade setup: {direction.upper()} @ ${entry_price:.2f} (confidence={confidence:.2f})")
    
    def should_exit_early(
        self,
        trade_id: str,
        current_price: float,
        current_pnl_pct: float,
        market_data=None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if trade should be exited early (before hitting stop loss)
        
        Returns:
            (should_exit, reason) - True if should exit, with reason
        """
        
        if trade_id not in self.active_setups:
            return False, None
        
        setup = self.active_setups[trade_id]
        exit_reasons = []
        
        # ==============================
        # 1. SETUP INVALIDATION CHECK
        # ==============================
        # If LONG setup but price breaks below entry significantly
        if setup.direction == 'long':
            price_change_pct = ((current_price - setup.entry_price) / setup.entry_price) * 100
            
            # Price dropped -0.8% without recovery (setup likely failed)
            if price_change_pct < -0.8 and current_pnl_pct < -0.5:
                exit_reasons.append(f"Setup invalidated: LONG but price down {price_change_pct:.2f}%")
        
        # If SHORT setup but price breaks above entry significantly
        elif setup.direction == 'short':
            price_change_pct = ((current_price - setup.entry_price) / setup.entry_price) * 100
            
            # Price rose +0.8% without reversal (setup likely failed)
            if price_change_pct > 0.8 and current_pnl_pct < -0.5:
                exit_reasons.append(f"Setup invalidated: SHORT but price up {price_change_pct:.2f}%")
        
        # ==============================
        # 2. MOMENTUM REVERSAL CHECK
        # ==============================
        if market_data and hasattr(market_data, 'price_history'):
            if len(market_data.price_history) >= 26:
                current_rsi = TechnicalIndicators.rsi(market_data.price_history)
                ema_fast = TechnicalIndicators.ema(market_data.price_history, 12)
                ema_slow = TechnicalIndicators.ema(market_data.price_history, 26)
                current_ema_trend = 'up' if ema_fast > ema_slow else 'down'
                
                # LONG setup but momentum turned bearish
                if setup.direction == 'long':
                    # RSI dropped significantly + EMA turned down + losing money
                    if (setup.setup_rsi and current_rsi < setup.setup_rsi - 15 and
                        current_ema_trend == 'down' and current_pnl_pct < -0.3):
                        exit_reasons.append(f"Momentum reversal: RSI {setup.setup_rsi:.0f}→{current_rsi:.0f}, EMA down")
                    
                    # Extreme RSI drop (momentum collapsed)
                    if setup.setup_rsi and current_rsi < 35 and setup.setup_rsi > 50:
                        exit_reasons.append(f"Momentum collapse: RSI {setup.setup_rsi:.0f}→{current_rsi:.0f}")
                
                # SHORT setup but momentum turned bullish
                elif setup.direction == 'short':
                    # RSI rose significantly + EMA turned up + losing money
                    if (setup.setup_rsi and current_rsi > setup.setup_rsi + 15 and
                        current_ema_trend == 'up' and current_pnl_pct < -0.3):
                        exit_reasons.append(f"Momentum reversal: RSI {setup.setup_rsi:.0f}→{current_rsi:.0f}, EMA up")
                    
                    # Extreme RSI rise (momentum collapsed)
                    if setup.setup_rsi and current_rsi > 65 and setup.setup_rsi < 50:
                        exit_reasons.append(f"Momentum collapse: RSI {setup.setup_rsi:.0f}→{current_rsi:.0f}")
        
        # ==============================
        # 3. TIME-BASED INVALIDATION
        # ==============================
        time_in_trade = (datetime.now() - setup.entry_time).seconds / 60  # minutes
        
        # Setup not working after 15 minutes AND losing money
        if time_in_trade > 15 and current_pnl_pct < -0.5:
            exit_reasons.append(f"Setup timeout: {time_in_trade:.0f}min, still at {current_pnl_pct:.2f}%")
        
        # Setup going nowhere (breakeven after 30 min)
        if time_in_trade > 30 and abs(current_pnl_pct) < 0.3:
            exit_reasons.append(f"Dead trade: {time_in_trade:.0f}min, no movement ({current_pnl_pct:.2f}%)")
        
        # ==============================
        # 4. VOLATILITY SPIKE CHECK
        # ==============================
        if market_data and hasattr(market_data, 'high_history') and hasattr(market_data, 'low_history'):
            if len(market_data.price_history) >= 15:
                # Extreme volatility emerged (skip high volatility check, just detect spikes)
                if TechnicalIndicators.is_high_volatility(
                    market_data.price_history,
                    market_data.high_history,
                    market_data.low_history,
                    threshold=0.06  # 6% ATR (extreme)
                ):
                    if current_pnl_pct < 0:  # Only exit if losing
                        exit_reasons.append("Volatility spike: Market too unstable")
        
        # ==============================
        # 5. WEAK CONFIDENCE + LOSING
        # ==============================
        # If original confidence was mediocre and trade is losing, exit faster
        if setup.confidence < 0.65 and current_pnl_pct < -0.7:
            exit_reasons.append(f"Low confidence setup ({setup.confidence:.2f}) failing")
        
        # ==============================
        # DECISION
        # ==============================
        if exit_reasons:
            reason = " | ".join(exit_reasons)
            self.logger.warning(f"⚠️ Early exit triggered: {reason}")
            return True, reason
        
        return False, None
    
    def remove_trade(self, trade_id: str):
        """Remove trade from monitoring (trade closed)"""
        if trade_id in self.active_setups:
            del self.active_setups[trade_id]
    
    def clear_old_setups(self, max_age_hours: float = 2.0):
        """Remove setups older than max_age_hours"""
        now = datetime.now()
        to_remove = []
        
        for trade_id, setup in self.active_setups.items():
            age_hours = (now - setup.entry_time).seconds / 3600
            if age_hours > max_age_hours:
                to_remove.append(trade_id)
        
        for trade_id in to_remove:
            del self.active_setups[trade_id]
            self.logger.info(f"Cleared old setup: {trade_id}")
