"""
Breakout & Aggressive Move Detection
Detects strong price moves and breakouts for aggressive trading
"""
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class BreakoutSignal:
    """Breakout detection result"""
    type: str  # "breakout_up", "breakout_down", "momentum_surge", "volume_spike"
    strength: float  # 0-1 (how strong the signal is)
    entry_price: float
    target_price: float
    stop_loss: float
    reason: str
    urgency: str  # "high", "medium", "low"


class BreakoutDetector:
    """
    Detects aggressive price moves and breakouts
    
    Signals:
    1. Support/Resistance Breakouts
    2. Volume Spikes with Momentum
    3. Rapid Price Acceleration
    4. Consolidation Breakouts
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.last_breakout_time = None
        self.breakout_cooldown = 300  # 5 minutes cooldown between breakouts
    
    def detect_breakout(
        self,
        current_price: float,
        recent_highs: List[float],
        recent_lows: List[float],
        recent_volumes: List[float],
        recent_closes: List[float]
    ) -> Optional[BreakoutSignal]:
        """
        Detect if there's a breakout opportunity
        
        Returns:
            BreakoutSignal if detected, None otherwise
        """
        if len(recent_closes) < 20:
            return None
        
        # Check cooldown
        if self.last_breakout_time:
            elapsed = (datetime.now() - self.last_breakout_time).total_seconds()
            if elapsed < self.breakout_cooldown:
                return None
        
        # 1. Check for resistance/support breakout
        breakout = self._check_level_breakout(current_price, recent_highs, recent_lows, recent_closes)
        if breakout:
            self.last_breakout_time = datetime.now()
            return breakout
        
        # 2. Check for momentum surge
        momentum = self._check_momentum_surge(current_price, recent_closes, recent_volumes)
        if momentum:
            self.last_breakout_time = datetime.now()
            return momentum
        
        # 3. Check for volume spike
        vol_spike = self._check_volume_spike(current_price, recent_closes, recent_volumes)
        if vol_spike:
            self.last_breakout_time = datetime.now()
            return vol_spike
        
        # 4. Check for consolidation breakout
        consolidation = self._check_consolidation_breakout(current_price, recent_highs, recent_lows, recent_closes)
        if consolidation:
            self.last_breakout_time = datetime.now()
            return consolidation
        
        return None
    
    def _check_level_breakout(
        self,
        current_price: float,
        recent_highs: List[float],
        recent_lows: List[float],
        recent_closes: List[float]
    ) -> Optional[BreakoutSignal]:
        """Detect breakout above resistance or below support"""
        
        # Calculate resistance (recent high)
        resistance = max(recent_highs[-20:])
        # Calculate support (recent low)
        support = min(recent_lows[-20:])
        
        # Breakout above resistance
        if current_price > resistance * 1.005:  # 0.5% above resistance
            target = current_price * 1.025  # 2.5% target
            stop = resistance * 0.995  # Stop just below broken resistance
            
            return BreakoutSignal(
                type="breakout_up",
                strength=0.85,
                entry_price=current_price,
                target_price=target,
                stop_loss=stop,
                reason=f"Broke resistance ${resistance:.2f}",
                urgency="high"
            )
        
        # Breakdown below support
        if current_price < support * 0.995:  # 0.5% below support
            target = current_price * 0.975  # 2.5% target
            stop = support * 1.005  # Stop just above broken support
            
            return BreakoutSignal(
                type="breakout_down",
                strength=0.85,
                entry_price=current_price,
                target_price=target,
                stop_loss=stop,
                reason=f"Broke support ${support:.2f}",
                urgency="high"
            )
        
        return None
    
    def _check_momentum_surge(
        self,
        current_price: float,
        recent_closes: List[float],
        recent_volumes: List[float]
    ) -> Optional[BreakoutSignal]:
        """Detect rapid price acceleration"""
        
        # Compare last 3 candles vs previous 10
        last_3_avg = sum(recent_closes[-3:]) / 3
        prev_10_avg = sum(recent_closes[-13:-3]) / 10
        
        change = (last_3_avg - prev_10_avg) / prev_10_avg
        
        # Strong upward momentum
        if change > 0.015:  # 1.5% surge
            target = current_price * 1.03  # 3% target
            stop = current_price * 0.985  # 1.5% stop
            
            return BreakoutSignal(
                type="momentum_surge",
                strength=0.80,
                entry_price=current_price,
                target_price=target,
                stop_loss=stop,
                reason=f"Strong upward momentum ({change*100:.1f}%)",
                urgency="high"
            )
        
        # Strong downward momentum
        if change < -0.015:  # 1.5% drop
            target = current_price * 0.97  # 3% target
            stop = current_price * 1.015  # 1.5% stop
            
            return BreakoutSignal(
                type="momentum_surge",
                strength=0.80,
                entry_price=current_price,
                target_price=target,
                stop_loss=stop,
                reason=f"Strong downward momentum ({abs(change)*100:.1f}%)",
                urgency="high"
            )
        
        return None
    
    def _check_volume_spike(
        self,
        current_price: float,
        recent_closes: List[float],
        recent_volumes: List[float]
    ) -> Optional[BreakoutSignal]:
        """Detect volume spike with direction"""
        
        if len(recent_volumes) < 10:
            return None
        
        current_vol = recent_volumes[-1]
        avg_vol = sum(recent_volumes[-10:-1]) / 9
        
        # Volume spike (2x average)
        if current_vol > avg_vol * 2:
            # Determine direction from price
            price_change = (recent_closes[-1] - recent_closes[-2]) / recent_closes[-2]
            
            # Upward volume spike
            if price_change > 0.005:  # 0.5% up
                target = current_price * 1.025  # 2.5% target
                stop = current_price * 0.985  # 1.5% stop
                
                return BreakoutSignal(
                    type="volume_spike",
                    strength=0.75,
                    entry_price=current_price,
                    target_price=target,
                    stop_loss=stop,
                    reason=f"Volume spike {current_vol/avg_vol:.1f}x with upward move",
                    urgency="medium"
                )
            
            # Downward volume spike
            if price_change < -0.005:  # 0.5% down
                target = current_price * 0.975  # 2.5% target
                stop = current_price * 1.015  # 1.5% stop
                
                return BreakoutSignal(
                    type="volume_spike",
                    strength=0.75,
                    entry_price=current_price,
                    target_price=target,
                    stop_loss=stop,
                    reason=f"Volume spike {current_vol/avg_vol:.1f}x with downward move",
                    urgency="medium"
                )
        
        return None
    
    def _check_consolidation_breakout(
        self,
        current_price: float,
        recent_highs: List[float],
        recent_lows: List[float],
        recent_closes: List[float]
    ) -> Optional[BreakoutSignal]:
        """Detect breakout from consolidation/range"""
        
        # Look at last 15 candles
        highs = recent_highs[-15:]
        lows = recent_lows[-15:]
        
        # Calculate range
        high_avg = sum(highs) / len(highs)
        low_avg = sum(lows) / len(lows)
        range_size = (high_avg - low_avg) / low_avg
        
        # Tight consolidation (range < 2%)
        if range_size < 0.02:
            recent_high = max(highs)
            recent_low = min(lows)
            
            # Breakout above consolidation
            if current_price > recent_high * 1.003:  # 0.3% above range
                target = current_price * 1.02  # 2% target
                stop = recent_high * 0.997  # Stop just below breakout
                
                return BreakoutSignal(
                    type="breakout_up",
                    strength=0.78,
                    entry_price=current_price,
                    target_price=target,
                    stop_loss=stop,
                    reason="Broke out of consolidation range",
                    urgency="medium"
                )
            
            # Breakdown below consolidation
            if current_price < recent_low * 0.997:  # 0.3% below range
                target = current_price * 0.98  # 2% target
                stop = recent_low * 1.003  # Stop just above breakdown
                
                return BreakoutSignal(
                    type="breakout_down",
                    strength=0.78,
                    entry_price=current_price,
                    target_price=target,
                    stop_loss=stop,
                    reason="Broke down from consolidation range",
                    urgency="medium"
                )
        
        return None


# Global instance
breakout_detector = BreakoutDetector()
