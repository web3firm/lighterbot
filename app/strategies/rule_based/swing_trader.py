"""
Swing Trading Strategy - 70% allocation
Trend-following with EMA crossover, RSI, MACD, ADX
Target: 15% PnL with 5% stop-loss (3:1 R:R)
"""

import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timezone
import os

logger = logging.getLogger(__name__)


class SwingTradingStrategy:
    """
    Swing trading strategy using multiple technical indicators
    Primary strategy with 70% capital allocation
    """
    
    def __init__(self, symbol: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize swing trading strategy
        
        Args:
            symbol: Trading symbol
            config: Optional configuration override
        """
        self.symbol = symbol
        self.config = config or {}
        self.name = "swing_trader"
        
        # Load from config or environment
        self.leverage = int(os.getenv('MAX_LEVERAGE', '5'))
        self.tp_pct = Decimal(os.getenv('TP_PNL_PCT', '15.0'))
        self.sl_pct = Decimal(os.getenv('SL_PNL_PCT', '5.0'))
        self.position_size_pct = Decimal(os.getenv('POSITION_SIZE_PCT', '50.0'))
        
        # Technical indicator parameters from environment
        self.rsi_period = int(os.getenv('RSI_PERIOD', '14'))
        self.rsi_oversold = int(os.getenv('RSI_OVERSOLD', '30'))
        self.rsi_overbought = int(os.getenv('RSI_OVERBOUGHT', '70'))
        
        self.ema_fast = int(os.getenv('EMA_FAST', '21'))
        self.ema_slow = int(os.getenv('EMA_SLOW', '50'))
        
        self.macd_fast = int(os.getenv('MACD_FAST', '12'))
        self.macd_slow = int(os.getenv('MACD_SLOW', '26'))
        self.macd_signal = int(os.getenv('MACD_SIGNAL', '9'))
        
        self.min_adx = int(os.getenv('ADX_MIN', '25'))
        self.min_signal_score = int(os.getenv('MIN_SIGNAL_SCORE', '5'))
        
        # State
        self.last_signal_time: Optional[datetime] = None
        self.signal_cooldown_seconds = 60
        self.signals_generated = 0
        
        swing_alloc = int(os.getenv('SWING_ALLOCATION', '70'))
        logger.info(f"✅ Swing Trading Strategy initialized for {symbol}")
        logger.info(f"   Allocation: {swing_alloc}% | Leverage: {self.leverage}x")
        logger.info(f"   TP: +{self.tp_pct}% PnL | SL: -{self.sl_pct}% PnL (R:R 1:{float(self.tp_pct/self.sl_pct)})")
        logger.info(f"   Min ADX: {self.min_adx} | Min Score: {self.min_signal_score}/8")
    
    async def generate_signal(self, market_data: Dict[str, Any],
                             account_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate trading signal based on swing trading logic
        
        Args:
            market_data: Market data with price, volume, indicators
            account_state: Account state
            
        Returns:
            Signal dict or None
        """
        try:
            # Check cooldown
            if self.last_signal_time:
                elapsed = (datetime.now(timezone.utc) - self.last_signal_time).total_seconds()
                if elapsed < self.signal_cooldown_seconds:
                    return None
            
            # Extract indicators
            indicators = market_data.get('indicators', {})
            current_price = Decimal(str(market_data.get('mark_price', 0)))
            
            if current_price == 0:
                return None
            
            rsi = indicators.get('rsi', 50)
            ema_fast_val = indicators.get('ema_fast', current_price)
            ema_slow_val = indicators.get('ema_slow', current_price)
            macd = indicators.get('macd', {})
            adx = indicators.get('adx', 0)
            volume_ratio = indicators.get('volume_ratio', 1.0)
            
            # Calculate signal score (0-8 points)
            score = 0
            side = None
            
            # 1. EMA Trend (2 points)
            if ema_fast_val > ema_slow_val * 1.005:  # Fast > Slow by 0.5%
                score += 2
                side = 'buy'
            elif ema_fast_val < ema_slow_val * 0.995:  # Fast < Slow by 0.5%
                score += 2
                side = 'sell'
            
            # 2. RSI (2 points)
            if side == 'buy' and rsi < self.rsi_oversold + 5:  # RSI 30-35
                score += 2
            elif side == 'sell' and rsi > self.rsi_overbought - 5:  # RSI 65-70
                score += 2
            
            # 3. MACD (2 points)
            macd_histogram = macd.get('histogram', 0)
            if side == 'buy' and macd_histogram > 0:
                score += 2
            elif side == 'sell' and macd_histogram < 0:
                score += 2
            
            # 4. ADX Trend Strength (1 point)
            if adx >= self.min_adx:
                score += 1
            
            # 5. Volume (1 point)
            if volume_ratio > 1.2:  # 20% above average
                score += 1
            
            # Check minimum score
            if score < self.min_signal_score or not side:
                return None
            
            # Calculate prices
            from app.utils.position_calculator import get_calculator
            calc = get_calculator()
            
            entry_price = current_price
            sl_price = calc.calculate_stop_loss_price(entry_price, side, self.sl_pct, self.leverage)
            tp_price = calc.calculate_take_profit_price(entry_price, side, self.tp_pct, self.leverage)
            
            # Round prices
            entry_price = calc.round_price(entry_price)
            sl_price = calc.round_price(sl_price)
            tp_price = calc.round_price(tp_price)
            
            # Calculate position size
            account_value = Decimal(str(account_state.get('account_value', 0)))
            position_size = calc.calculate_position_size(
                account_value, self.position_size_pct, self.leverage, entry_price
            )
            
            # Create signal
            signal = {
                'strategy': self.name,
                'symbol': self.symbol,
                'side': side,
                'entry_price': float(entry_price),
                'sl_price': float(sl_price),
                'tp_price': float(tp_price),
                'size': float(position_size),
                'leverage': self.leverage,
                'signal_strength': score,
                'max_strength': 8,
                'confidence': score / 8.0,
                'indicators': {
                    'rsi': rsi,
                    'ema_fast': float(ema_fast_val),
                    'ema_slow': float(ema_slow_val),
                    'macd': macd_histogram,
                    'adx': adx,
                    'volume_ratio': volume_ratio
                },
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            # Update state
            self.last_signal_time = datetime.now(timezone.utc)
            self.signals_generated += 1
            
            logger.info(f"🎯 SWING SIGNAL: {side.upper()} {self.symbol}")
            logger.info(f"   Score: {score}/8 ({score/8*100:.0f}%)")
            logger.info(f"   Entry: ${entry_price} | SL: ${sl_price} | TP: ${tp_price}")
            logger.info(f"   Size: {position_size:.6f}")
            
            return signal
            
        except Exception as e:
            logger.error(f"❌ Error generating swing signal: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics"""
        return {
            'name': self.name,
            'signals_generated': self.signals_generated,
            'last_signal_time': self.last_signal_time.isoformat() if self.last_signal_time else None
        }
