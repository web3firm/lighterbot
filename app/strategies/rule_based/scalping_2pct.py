"""
Scalping Strategy - 30% allocation
Quick 2% moves with tight stop-loss
Target: 2% PnL with 1% stop-loss (2:1 R:R)
"""

import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timezone
import os

logger = logging.getLogger(__name__)


class ScalpingStrategy2Pct:
    """
    Scalping strategy for quick 2% profit moves
    Secondary strategy with 30% capital allocation
    """
    
    def __init__(self, symbol: str, config: Optional[Dict[str, Any]] = None):
        """Initialize scalping strategy"""
        self.symbol = symbol
        self.config = config or {}
        self.name = "scalping_2pct"
        
        # Strategy parameters from environment
        self.leverage = int(os.getenv('MAX_LEVERAGE', '5'))
        self.tp_pct = Decimal(os.getenv('TP_PNL_PCT', '15.0'))
        self.sl_pct = Decimal(os.getenv('SL_PNL_PCT', '5.0'))
        self.position_size_pct = Decimal(os.getenv('POSITION_SIZE_PCT', '50.0'))
        
        # Entry conditions from environment
        self.min_momentum_threshold = Decimal(os.getenv('MIN_MOMENTUM_PCT', '0.3')) / Decimal('100')
        
        # State
        self.last_signal_time: Optional[datetime] = None
        self.signal_cooldown_seconds = 30  # Faster cooldown
        self.signals_generated = 0
        
        scalp_alloc = int(os.getenv('SCALPING_ALLOCATION', '30'))
        logger.info(f"✅ Scalping Strategy initialized for {symbol}")
        logger.info(f"   Allocation: {scalp_alloc}% | Leverage: {self.leverage}x")
        logger.info(f"   TP: +{self.tp_pct}% PnL | SL: -{self.sl_pct}% PnL (R:R 1:2)")
    
    async def generate_signal(self, market_data: Dict[str, Any],
                             account_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate scalping signal"""
        try:
            # Check cooldown
            if self.last_signal_time:
                elapsed = (datetime.now(timezone.utc) - self.last_signal_time).total_seconds()
                if elapsed < self.signal_cooldown_seconds:
                    return None
            
            # Extract data
            indicators = market_data.get('indicators', {})
            current_price = Decimal(str(market_data.get('mark_price', 0)))
            
            if current_price == 0:
                return None
            
            # Check momentum
            price_change_5m = indicators.get('price_change_5m', 0)
            momentum = abs(Decimal(str(price_change_5m)))
            
            if momentum < self.min_momentum_threshold:
                return None
            
            # Determine side
            side = 'buy' if price_change_5m > 0 else 'sell'
            
            # Calculate prices
            from app.utils.position_calculator import get_calculator
            calc = get_calculator()
            
            entry_price = current_price
            sl_price = calc.calculate_stop_loss_price(entry_price, side, self.sl_pct, self.leverage)
            tp_price = calc.calculate_take_profit_price(entry_price, side, self.tp_pct, self.leverage)
            
            entry_price = calc.round_price(entry_price)
            sl_price = calc.round_price(sl_price)
            tp_price = calc.round_price(tp_price)
            
            # Calculate position size
            account_value = Decimal(str(account_state.get('account_value', 0)))
            position_size = calc.calculate_position_size(
                account_value, self.position_size_pct, self.leverage, entry_price
            )
            
            signal = {
                'strategy': self.name,
                'symbol': self.symbol,
                'side': side,
                'entry_price': float(entry_price),
                'sl_price': float(sl_price),
                'tp_price': float(tp_price),
                'size': float(position_size),
                'leverage': self.leverage,
                'signal_strength': 6,
                'max_strength': 10,
                'confidence': 0.6,
                'indicators': {
                    'momentum': float(momentum),
                    'price_change_5m': price_change_5m
                },
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            self.last_signal_time = datetime.now(timezone.utc)
            self.signals_generated += 1
            
            logger.info(f"⚡ SCALP SIGNAL: {side.upper()} {self.symbol}")
            logger.info(f"   Momentum: {momentum*100:.2f}%")
            logger.info(f"   Entry: ${entry_price} | SL: ${sl_price} | TP: ${tp_price}")
            
            return signal
            
        except Exception as e:
            logger.error(f"❌ Error generating scalp signal: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics"""
        return {
            'name': self.name,
            'signals_generated': self.signals_generated,
            'last_signal_time': self.last_signal_time.isoformat() if self.last_signal_time else None
        }
