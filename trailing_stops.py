"""
Dynamic Trailing Stop-Loss Manager
Automatically adjusts stops based on ATR and price movement
"""
from typing import Optional, Dict
from dataclasses import dataclass
from datetime import datetime

from indicators import TechnicalIndicators
from logger import logger


@dataclass
class TrailingStop:
    """Trailing stop configuration for a position"""
    position_id: str
    market_id: int
    is_long: bool
    entry_price: float
    current_stop: float
    highest_price: float  # For long positions
    lowest_price: float   # For short positions
    initial_risk: float
    atr: float
    breakeven_triggered: bool
    created_at: datetime
    updated_at: datetime


class TrailingStopManager:
    """
    Manages dynamic trailing stops for all positions
    
    Features:
    - ATR-based stop distance (adapts to volatility)
    - Trailing stop (locks in profits)
    - Breakeven protection (move to B/E after 1:1 R:R)
    - Automatic tightening as profit increases
    """
    
    def __init__(self):
        self.stops: Dict[str, TrailingStop] = {}
        self.atr_multiplier = 2.0  # 2x ATR for initial stop
        self.trailing_multiplier = 1.5  # 1.5x ATR for trailing
        self.breakeven_buffer = 0.5  # 0.5x ATR buffer at breakeven
        logger.info("TrailingStopManager initialized")
    
    def create_stop(
        self,
        position_id: str,
        market_id: int,
        is_long: bool,
        entry_price: float,
        atr: float
    ) -> TrailingStop:
        """
        Create initial trailing stop for position
        
        Args:
            position_id: Unique position identifier
            market_id: Market ID
            is_long: True for long, False for short
            entry_price: Position entry price
            atr: Current ATR (14-period)
        """
        initial_risk = self.atr_multiplier * atr
        
        if is_long:
            initial_stop = entry_price - initial_risk
            highest_price = entry_price
            lowest_price = 0
        else:
            initial_stop = entry_price + initial_risk
            highest_price = 0
            lowest_price = entry_price
        
        stop = TrailingStop(
            position_id=position_id,
            market_id=market_id,
            is_long=is_long,
            entry_price=entry_price,
            current_stop=initial_stop,
            highest_price=highest_price,
            lowest_price=lowest_price,
            initial_risk=initial_risk,
            atr=atr,
            breakeven_triggered=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        self.stops[position_id] = stop
        
        logger.info(
            f"Created {'LONG' if is_long else 'SHORT'} trailing stop: "
            f"Entry={entry_price:.2f}, Initial Stop={initial_stop:.2f}, "
            f"ATR={atr:.2f}, Risk={initial_risk:.2f}"
        )
        
        return stop
    
    def update_stop(
        self,
        position_id: str,
        current_price: float,
        atr: Optional[float] = None
    ) -> tuple[float, bool, str]:
        """
        Update trailing stop based on current price
        
        Returns:
            (new_stop_price, should_close, reason)
        """
        if position_id not in self.stops:
            return 0.0, False, "No stop found"
        
        stop = self.stops[position_id]
        
        # Update ATR if provided
        if atr:
            stop.atr = atr
        
        # Track price extremes
        if stop.is_long:
            stop.highest_price = max(stop.highest_price, current_price)
        else:
            stop.lowest_price = min(stop.lowest_price, current_price) if stop.lowest_price > 0 else current_price
        
        # Calculate profit
        if stop.is_long:
            profit = current_price - stop.entry_price
            profit_ratio = profit / stop.initial_risk if stop.initial_risk > 0 else 0
        else:
            profit = stop.entry_price - current_price
            profit_ratio = profit / stop.initial_risk if stop.initial_risk > 0 else 0
        
        # Decision logic
        new_stop = stop.current_stop
        reason = "No change"
        
        # RULE 1: Check if stop hit
        if stop.is_long and current_price <= stop.current_stop:
            return stop.current_stop, True, f"Stop hit at {stop.current_stop:.2f}"
        elif not stop.is_long and current_price >= stop.current_stop:
            return stop.current_stop, True, f"Stop hit at {stop.current_stop:.2f}"
        
        # RULE 2: Move to breakeven after 1:1 R:R
        if profit_ratio >= 1.0 and not stop.breakeven_triggered:
            breakeven_buffer = self.breakeven_buffer * stop.atr
            
            if stop.is_long:
                new_stop = stop.entry_price + breakeven_buffer
                reason = f"Breakeven triggered (profit={profit:.2f}, 1:1 R:R achieved)"
            else:
                new_stop = stop.entry_price - breakeven_buffer
                reason = f"Breakeven triggered (profit={profit:.2f}, 1:1 R:R achieved)"
            
            stop.breakeven_triggered = True
            logger.info(f"Position {position_id}: {reason}, new stop={new_stop:.2f}")
        
        # RULE 3: Trailing stop
        elif profit_ratio > 1.0:  # Only trail after breakeven
            trailing_distance = self.trailing_multiplier * stop.atr
            
            if stop.is_long:
                # Trail behind highest price
                trailing_stop = stop.highest_price - trailing_distance
                
                # Only move stop up, never down
                if trailing_stop > stop.current_stop:
                    new_stop = trailing_stop
                    reason = f"Trailing stop (highest={stop.highest_price:.2f}, distance={trailing_distance:.2f})"
            
            else:  # Short position
                # Trail behind lowest price
                trailing_stop = stop.lowest_price + trailing_distance
                
                # Only move stop down, never up
                if trailing_stop < stop.current_stop:
                    new_stop = trailing_stop
                    reason = f"Trailing stop (lowest={stop.lowest_price:.2f}, distance={trailing_distance:.2f})"
        
        # Update stop if changed
        if new_stop != stop.current_stop:
            old_stop = stop.current_stop
            stop.current_stop = new_stop
            stop.updated_at = datetime.now()
            
            logger.info(
                f"Position {position_id} stop updated: {old_stop:.2f} → {new_stop:.2f} "
                f"(Price={current_price:.2f}, Profit={profit:.2f}, {reason})"
            )
        
        return new_stop, False, reason
    
    def get_stop(self, position_id: str) -> Optional[TrailingStop]:
        """Get current stop for position"""
        return self.stops.get(position_id)
    
    def remove_stop(self, position_id: str):
        """Remove stop when position is closed"""
        if position_id in self.stops:
            del self.stops[position_id]
            logger.info(f"Removed trailing stop for position {position_id}")
    
    def get_all_stops(self) -> Dict[str, TrailingStop]:
        """Get all active stops"""
        return self.stops.copy()
    
    def check_all_positions(
        self,
        positions: Dict[str, float]  # position_id -> current_price
    ) -> Dict[str, tuple[bool, str]]:
        """
        Check all positions and return which should be closed
        
        Args:
            positions: Dict of position_id -> current_price
            
        Returns:
            Dict of position_id -> (should_close, reason)
        """
        results = {}
        
        for position_id, current_price in positions.items():
            if position_id in self.stops:
                _, should_close, reason = self.update_stop(position_id, current_price)
                if should_close:
                    results[position_id] = (True, reason)
        
        return results


# Global instance
trailing_stop_manager = TrailingStopManager()
