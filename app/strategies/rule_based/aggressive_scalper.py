"""
Aggressive Scalping Strategy - High Leverage Account Flipping
Risk: EXTREME
Target: Small accounts ($20-$100) looking for rapid growth
"""

import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timezone
import os

logger = logging.getLogger(__name__)


class AggressiveScalperStrategy:
    """
    Aggressive scalping strategy for account flipping
    Uses high leverage and large position sizes on small capital
    """
    
    def __init__(self, symbol: str, config: Optional[Dict[str, Any]] = None):
        """Initialize aggressive strategy"""
        self.symbol = symbol
        self.config = config or {}
        self.name = "aggressive_scalper"
        
        # Strategy parameters - EXTREME DEFAULTS
        self.leverage = int(os.getenv('MAX_LEVERAGE', '20'))
        
        # Aggressive targets (in PnL %)
        # With 20x leverage:
        # 20% PnL = 1% price move (Quick scalp)
        # 50% PnL = 2.5% price move (Safety net)
        self.tp_pct = Decimal(os.getenv('TP_PNL_PCT', '20.0'))
        self.sl_pct = Decimal(os.getenv('SL_PNL_PCT', '50.0'))
        
        # Position sizing: Use almost all available capital for maximum growth (flipping)
        # Default 95% to leave room for fees
        self.position_size_pct = Decimal(os.getenv('POSITION_SIZE_PCT', '95.0'))
        
        # Entry conditions
        # Looser momentum threshold to trade more frequently
        self.min_momentum_threshold = Decimal(os.getenv('MIN_MOMENTUM_PCT', '0.15')) / Decimal('100')
        
        # State
        self.last_signal_time: Optional[datetime] = None
        self.signal_cooldown_seconds = 10  # Rapid fire
        self.signals_generated = 0
        
        logger.info(f"🔥 AGGRESSIVE Strategy initialized for {symbol}")
        logger.info(f"   Leverage: {self.leverage}x | Allocation: {self.position_size_pct}%")
        logger.info(f"   Targets: TP +{self.tp_pct}% | SL -{self.sl_pct}%")
    
    async def generate_signal(self, market_data: Dict[str, Any],
                             account_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate aggressive scalping signal"""
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
            
            # 1. Momentum Check (Primary Driver)
            # We want to catch quick bursts of volatility
            price_change_5m = Decimal(str(indicators.get('price_change_5m', 0)))
            price_change_1h = Decimal(str(indicators.get('price_change_1h', 0)))
            
            momentum = abs(price_change_5m)
            
            # Filter low volatility noise
            if momentum < self.min_momentum_threshold:
                return None
            
            # 2. Trend Confirmation (EMA/RSI)
            # If we have RSI, use it to avoid buying top / selling bottom
            rsi = indicators.get('rsi')
            ema_fast = indicators.get('ema_fast')
            ema_slow = indicators.get('ema_slow')
            
            side = None
            confidence = 0.6
            
            # Determine direction based on momentum
            if price_change_5m > 0:
                # Upward momentum
                # Only buy if not overbought (RSI < 75)
                if rsi is None or rsi < 75:
                    side = 'buy'
                    # boost confidence if trend aligns (1H up or fast > slow)
                    if price_change_1h > 0:
                        confidence += 0.1
                    if ema_fast and ema_slow and ema_fast > ema_slow:
                        confidence += 0.1
            else:
                # Downward momentum
                # Only sell if not oversold (RSI > 25)
                if rsi is None or rsi > 25:
                    side = 'sell'
                    # boost confidence if trend aligns
                    if price_change_1h < 0:
                        confidence += 0.1
                    if ema_fast and ema_slow and ema_fast < ema_slow:
                        confidence += 0.1
            
            if not side:
                return None
                
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
            # For small accounts, we use 'total_raw_usd' (total asset value) to base sizing on
            # This allows compounding: as account grows to $25, $30, we bet more.
            account_value = Decimal(str(account_state.get('total_raw_usd', 0)))
            
            # Safety check: if account is 0 (data error), fallback to collateral
            if account_value == 0:
                account_value = Decimal(str(account_state.get('collateral', 0)))
            
            position_size = calc.calculate_position_size(
                account_value, self.position_size_pct, self.leverage, entry_price
            )
            
            # Check minimum size (approximate)
            # Lighter minimum is usually 0.001 ETH or similar. 
            # With $20 x 20 = $400 position, size is plenty.
            
            signal = {
                'strategy': self.name,
                'symbol': self.symbol,
                'side': side,
                'entry_price': float(entry_price),
                'sl_price': float(sl_price),
                'tp_price': float(tp_price),
                'size': float(position_size),
                'leverage': self.leverage,
                'signal_strength': 8,  # Aggressive signals are "strong"
                'max_strength': 10,
                'confidence': confidence,
                'indicators': {
                    'momentum': float(momentum),
                    'rsi': float(rsi) if rsi else 0,
                    'price_change_5m': float(price_change_5m)
                },
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            self.last_signal_time = datetime.now(timezone.utc)
            self.signals_generated += 1
            
            logger.info(f"⚡ AGGRESSIVE SIGNAL: {side.upper()} {self.symbol}")
            logger.info(f"   Lev: {self.leverage}x | Size: {position_size:.4f}")
            logger.info(f"   Entry: ${entry_price} | TP: ${tp_price} (+{self.tp_pct}%)")
            
            return signal
            
        except Exception as e:
            logger.error(f"❌ Error generating aggressive signal: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics"""
        return {
            'name': self.name,
            'signals_generated': self.signals_generated,
            'last_signal_time': self.last_signal_time.isoformat() if self.last_signal_time else None
        }
