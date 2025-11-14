"""
VWAP Entry Filter - Institution-Grade Entry Timing

VWAP (Volume-Weighted Average Price) is the average price weighted by volume.
Institutions use it to:
1. Identify fair value
2. Enter only when price near VWAP (reduces bad entries at extremes)
3. Exit when price far from VWAP (momentum exhausted)
"""
from typing import Optional, Tuple
from datetime import datetime, timedelta
from logger import get_logger

logger = get_logger()


class VWAPFilter:
    """
    VWAP-based entry filter for 1-minute scalping
    
    Rules:
    - ONLY enter when price within 0.3% of VWAP
    - This prevents buying tops and selling bottoms
    - Institutions call this "mean reversion to fair value"
    """
    
    def __init__(self):
        self.vwap = None
        self.last_vwap_update = None
        self.prices = []
        self.volumes = []
        self.max_history = 50  # 50 periods for VWAP calculation
    
    def update_vwap(self, price: float, volume: float = 1.0):
        """
        Update VWAP calculation with new price/volume data
        
        Args:
            price: Current price
            volume: Trading volume (default 1.0 if unavailable)
        """
        self.prices.append(price)
        self.volumes.append(volume)
        
        # Keep only recent history
        if len(self.prices) > self.max_history:
            self.prices.pop(0)
            self.volumes.pop(0)
        
        # Calculate VWAP: sum(price * volume) / sum(volume)
        if len(self.prices) >= 10:  # Need at least 10 data points
            total_pv = sum(p * v for p, v in zip(self.prices, self.volumes))
            total_volume = sum(self.volumes)
            self.vwap = total_pv / total_volume if total_volume > 0 else self.prices[-1]
            self.last_vwap_update = datetime.now()
    
    def should_enter_trade(
        self,
        current_price: float,
        signal_direction: str,
        threshold_percent: float = 0.3
    ) -> Tuple[bool, str]:
        """
        Check if price is near VWAP (good entry point)
        
        Args:
            current_price: Current market price
            signal_direction: "long" or "short"
            threshold_percent: Maximum distance from VWAP (default 0.3%)
        
        Returns:
            (approved, reason)
        """
        if self.vwap is None:
            logger.warning("⚠️ VWAP not calculated yet (need 10+ prices)")
            return True, "VWAP unavailable, allowing trade"
        
        # Calculate distance from VWAP
        distance_from_vwap = ((current_price - self.vwap) / self.vwap) * 100
        distance_abs = abs(distance_from_vwap)
        
        # Institution rule: Only trade when price near VWAP (fair value)
        if distance_abs > threshold_percent:
            if distance_from_vwap > 0:
                reason = f"❌ Price {distance_abs:.2f}% ABOVE VWAP (overbought, wait for pullback)"
            else:
                reason = f"❌ Price {distance_abs:.2f}% BELOW VWAP (oversold, wait for bounce)"
            
            logger.info(f"VWAP FILTER: {reason}")
            logger.info(f"   Price: ${current_price:.2f}, VWAP: ${self.vwap:.2f}")
            return False, reason
        
        # Additional check: Direction alignment
        if signal_direction == "long" and distance_from_vwap < -0.15:
            # Price below VWAP = good for long (buy dip near fair value)
            logger.info(f"✅ VWAP LONG: Price {distance_from_vwap:.2f}% below VWAP (good dip)")
            return True, f"Price near VWAP ({distance_from_vwap:.2f}%)"
        
        elif signal_direction == "short" and distance_from_vwap > 0.15:
            # Price above VWAP = good for short (sell rally near fair value)
            logger.info(f"✅ VWAP SHORT: Price {distance_from_vwap:.2f}% above VWAP (good rally)")
            return True, f"Price near VWAP ({distance_from_vwap:.2f}%)"
        
        elif distance_abs <= 0.15:
            # Very close to VWAP = neutral zone, allow trade
            logger.info(f"✅ VWAP NEUTRAL: Price {distance_from_vwap:.2f}% from VWAP (fair value)")
            return True, f"Price at VWAP ({distance_from_vwap:.2f}%)"
        
        # Default: Allow if within threshold
        logger.info(f"✅ VWAP OK: Price {distance_from_vwap:.2f}% from VWAP")
        return True, f"Price near VWAP ({distance_from_vwap:.2f}%)"
    
    def get_vwap_info(self) -> dict:
        """Get current VWAP information"""
        return {
            "vwap": self.vwap,
            "last_update": self.last_vwap_update,
            "data_points": len(self.prices),
            "current_price": self.prices[-1] if self.prices else None
        }


# Global instance
vwap_filter = VWAPFilter()
