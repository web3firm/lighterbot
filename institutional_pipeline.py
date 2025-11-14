"""
Institutional Trading Filter Pipeline

Combines all institutional-grade filters into one clean interface.
Call this BEFORE executing any trade.
"""

from typing import Tuple, Optional
from logger import get_logger
from config import settings

# Import all filters
from strategy_performance import strategy_tracker
from drawdown_protection import drawdown_protection
from time_filter import is_trading_hours, get_trading_session
from multi_timeframe import mtf_analyzer

logger = get_logger()

# FAST MODE for 1-minute scalping (disable slow multi-timeframe)
FAST_SCALPING_MODE = True  # Set False for swing trading


class InstitutionalFilterPipeline:
    """
    One-stop filter for all institutional checks
    
    Usage:
        pipeline = InstitutionalFilterPipeline()
        approved, reason, adjustments = await pipeline.should_execute_trade(
            signal=signal,
            market_data=market_data
        )
        
        if approved:
            # Apply adjustments (size multiplier, confidence boost)
            execute_trade_with_adjustments(adjustments)
    """
    
    def __init__(self):
        self.logger = logger
        self.logger.info("✅ Institutional Filter Pipeline initialized")
        self.logger.info("   📊 Strategy Performance Tracker")
        self.logger.info("   🛡️ Drawdown Protection")
        self.logger.info("   ⏰ Time-of-Day Filter")
        self.logger.info("   📈 Multi-Timeframe Analysis")
    
    async def should_execute_trade(
        self,
        signal,  # Signal object
        market_data,  # MarketData object
    ) -> Tuple[bool, str, dict]:
        """
        Run all institutional filters
        
        Returns:
            (approved, reason, adjustments)
            
            adjustments = {
                'size_multiplier': float,  # 0.25-1.0
                'confidence_boost': float,  # 0.0-0.4
                'mtf_confidence': float,    # Multi-timeframe confidence
            }
        """
        
        adjustments = {
            'size_multiplier': 1.0,
            'confidence_boost': 0.0,
            'mtf_confidence': 0.0,
        }
        
        # ========================================
        # FILTER 1: Time-of-Day
        # ========================================
        trading_allowed, time_reason = is_trading_hours()
        if not trading_allowed:
            return False, f"⏰ {time_reason}", adjustments
        
        session = get_trading_session()
        self.logger.debug(f"📅 {session}")
        
        # ========================================
        # FILTER 2: Drawdown Protection
        # ========================================
        allowed, dd_reason = drawdown_protection.should_allow_trading()
        if not allowed:
            return False, f"🛑 {dd_reason}", adjustments
        
        # Get size multiplier (0.25-1.0)
        adjustments['size_multiplier'] = drawdown_protection.get_size_multiplier()
        
        if adjustments['size_multiplier'] < 1.0:
            self.logger.warning(
                f"⚠️ Drawdown protection: Size {adjustments['size_multiplier']*100:.0f}%"
            )
        
        # ========================================
        # FILTER 3: Strategy Performance
        # ========================================
        strategy_name = signal.reason.split(':')[0] if ':' in signal.reason else "unknown"
        if not strategy_tracker.is_strategy_enabled(strategy_name):
            return False, f"❌ Strategy {strategy_name} disabled (poor performance)", adjustments
        
        # ========================================
        # FILTER 4: Multi-Timeframe Analysis (OPTIONAL in fast mode)
        # ========================================
        if not FAST_SCALPING_MODE:
            signal_direction = 'long' if signal.signal_type.value == 'buy' else 'short'
            
            mtf_approved, mtf_confidence, mtf_reason = await mtf_analyzer.get_multi_timeframe_signal(
                market_data,
                signal_direction
            )
            
            if not mtf_approved:
                return False, f"📊 Multi-TF: {mtf_reason}", adjustments
            
            # Store multi-timeframe confidence for boost
            adjustments['mtf_confidence'] = mtf_confidence
            adjustments['confidence_boost'] = mtf_confidence * 0.4  # Up to +40% confidence
        else:
            # FAST MODE: Skip multi-timeframe, use pure signal strength
            self.logger.debug("⚡ FAST MODE: Skipping multi-timeframe for 1m scalping")
            adjustments['mtf_confidence'] = 1.0
            adjustments['confidence_boost'] = signal.strength * 0.2  # Use signal strength
        
        self.logger.info(
            f"✅ ALL FILTERS PASSED | "
            f"Size: {adjustments['size_multiplier']*100:.0f}% | "
            f"Conf boost: +{adjustments['confidence_boost']*100:.0f}%"
        )
        
        return True, "All filters passed", adjustments
    
    def record_trade_closed(
        self,
        strategy_name: str,
        pnl_percent: float,
        entry_price: float,
        exit_price: float,
        balance: float
    ):
        """
        Record a closed trade for all trackers
        
        Call this when a position closes.
        """
        
        is_win = pnl_percent > 0
        
        # Update strategy tracker
        strategy_tracker.record_trade(
            strategy_name=strategy_name,
            pnl_percent=pnl_percent,
            entry_price=entry_price,
            exit_price=exit_price
        )
        
        # Update drawdown protection
        drawdown_protection.record_trade_result(
            is_win=is_win,
            pnl_pct=pnl_percent,
            balance=balance
        )
        
        self.logger.info(
            f"📊 Trade recorded: {strategy_name} {pnl_percent:+.2f}% | "
            f"DD Status: {drawdown_protection.get_status_summary()}"
        )
    
    def get_status_report(self) -> str:
        """Get comprehensive status of all filters"""
        
        lines = ["\n" + "=" * 80]
        lines.append("🏛️ INSTITUTIONAL FILTERS STATUS")
        lines.append("=" * 80)
        
        # Time filter
        allowed, reason = is_trading_hours()
        session = get_trading_session()
        status_icon = "✅" if allowed else "❌"
        lines.append(f"{status_icon} Time Filter: {session} - {reason}")
        
        # Drawdown protection
        dd_allowed, dd_reason = drawdown_protection.should_allow_trading()
        dd_icon = "✅" if dd_allowed else "🛑"
        lines.append(f"{dd_icon} Drawdown: {drawdown_protection.get_status_summary()}")
        
        # Strategy performance
        best_strategies = strategy_tracker.get_best_strategies(3)
        if best_strategies:
            lines.append(f"🏆 Best Strategies: {', '.join(best_strategies)}")
        
        lines.append("=" * 80)
        
        # Full strategy report
        lines.append(strategy_tracker.get_summary())
        
        return "\n".join(lines)


# Global instance
institutional_pipeline = InstitutionalFilterPipeline()
