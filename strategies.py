"""
Advanced Trading Strategies
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import asyncio
from datetime import datetime

from indicators import TechnicalIndicators
from orderflow_analyzer import OrderFlowAnalyzer
from sentiment_analyzer import SentimentAnalyzer
from config import settings
from logger import logger


class SignalType(Enum):
    """Trading signal types"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"


@dataclass
class Signal:
    """Trading signal"""
    signal_type: SignalType
    strength: float  # 0.0 to 1.0
    price: float
    reason: str
    timestamp: datetime


@dataclass
class MarketData:
    """Market data snapshot"""
    symbol: str
    price: float
    bid: float
    ask: float
    spread: float
    volume_24h: float
    price_history: List[float]
    high_history: List[float]
    low_history: List[float]
    volume_history: List[float]
    timestamp: datetime


class BaseStrategy(ABC):
    """Base class for all trading strategies"""
    
    def __init__(self, name: str):
        self.name = name
        self.enabled = True
        self.min_signal_strength = 0.6
    
    @abstractmethod
    async def analyze(self, market_data: MarketData) -> Optional[Signal]:
        """
        Analyze market data and generate trading signal
        
        Args:
            market_data: Current market data
            
        Returns:
            Signal or None if no clear signal
        """
        pass
    
    def _validate_signal_strength(self, strength: float) -> bool:
        """Check if signal strength meets minimum threshold"""
        return strength >= self.min_signal_strength


class MomentumStrategy(BaseStrategy):
    """
    Momentum/Trend Following Strategy
    
    - Uses RSI, MACD, and EMA for trend detection
    - Buys on strong uptrends, sells on strong downtrends
    - Includes momentum confirmation
    """
    
    def __init__(self):
        super().__init__("Momentum")
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        self.ema_fast = 12
        self.ema_slow = 26
    
    async def analyze(self, market_data: MarketData) -> Optional[Signal]:
        """Analyze momentum indicators"""
        
        if len(market_data.price_history) < self.ema_slow:
            return None
        
        # Calculate indicators
        rsi = TechnicalIndicators.rsi(market_data.price_history)
        ema_fast = TechnicalIndicators.ema(market_data.price_history, self.ema_fast)
        ema_slow = TechnicalIndicators.ema(market_data.price_history, self.ema_slow)
        macd_line, signal_line, histogram = TechnicalIndicators.macd(market_data.price_history)
        
        current_price = market_data.price
        
        # Bullish signals
        if (rsi < self.rsi_oversold and 
            ema_fast > ema_slow and 
            histogram > 0 and
            current_price > ema_fast):
            
            strength = min(1.0, (self.rsi_overbought - rsi) / self.rsi_overbought + 0.3)
            
            if self._validate_signal_strength(strength):
                return Signal(
                    signal_type=SignalType.BUY,
                    strength=strength,
                    price=current_price,
                    reason=f"Momentum bullish: RSI={rsi:.1f}, EMA crossover positive, MACD histogram={histogram:.4f}",
                    timestamp=market_data.timestamp
                )
        
        # Bearish signals
        elif (rsi > self.rsi_overbought and 
              ema_fast < ema_slow and 
              histogram < 0 and
              current_price < ema_fast):
            
            strength = min(1.0, (rsi - self.rsi_oversold) / self.rsi_overbought + 0.3)
            
            if self._validate_signal_strength(strength):
                return Signal(
                    signal_type=SignalType.SELL,
                    strength=strength,
                    price=current_price,
                    reason=f"Momentum bearish: RSI={rsi:.1f}, EMA crossover negative, MACD histogram={histogram:.4f}",
                    timestamp=market_data.timestamp
                )
        
        return None


class MeanReversionStrategy(BaseStrategy):
    """
    Mean Reversion Strategy
    
    - Uses Bollinger Bands and RSI
    - Buys at lower band when oversold
    - Sells at upper band when overbought
    """
    
    def __init__(self):
        super().__init__("MeanReversion")
        self.bb_period = 20
        self.bb_std = 2.0
        self.rsi_period = 14
    
    async def analyze(self, market_data: MarketData) -> Optional[Signal]:
        """Analyze mean reversion indicators"""
        
        if len(market_data.price_history) < self.bb_period:
            return None
        
        # Calculate Bollinger Bands
        upper, middle, lower = TechnicalIndicators.bollinger_bands(
            market_data.price_history, 
            self.bb_period, 
            self.bb_std
        )
        
        rsi = TechnicalIndicators.rsi(market_data.price_history, self.rsi_period)
        current_price = market_data.price
        
        # Calculate position relative to bands
        band_width = upper - lower
        if band_width == 0:
            return None
        
        position_in_band = (current_price - lower) / band_width
        
        # Buy signal: Price at lower band + oversold RSI
        if position_in_band < 0.2 and rsi < 35:
            strength = 1.0 - position_in_band + (0.5 - rsi/100)
            strength = min(1.0, max(0.0, strength))
            
            if self._validate_signal_strength(strength):
                return Signal(
                    signal_type=SignalType.BUY,
                    strength=strength,
                    price=current_price,
                    reason=f"Mean reversion buy: Price at {position_in_band:.1%} of BB, RSI={rsi:.1f}",
                    timestamp=market_data.timestamp
                )
        
        # Sell signal: Price at upper band + overbought RSI
        elif position_in_band > 0.8 and rsi > 65:
            strength = position_in_band + (rsi/100 - 0.5)
            strength = min(1.0, max(0.0, strength))
            
            if self._validate_signal_strength(strength):
                return Signal(
                    signal_type=SignalType.SELL,
                    strength=strength,
                    price=current_price,
                    reason=f"Mean reversion sell: Price at {position_in_band:.1%} of BB, RSI={rsi:.1f}",
                    timestamp=market_data.timestamp
                )
        
        return None


class MarketMakingStrategy(BaseStrategy):
    """
    Market Making Strategy
    
    - Places orders on both sides of the order book
    - Adjusts spreads based on volatility
    - Manages inventory to avoid accumulating too much position
    """
    
    def __init__(self):
        super().__init__("MarketMaking")
        self.target_spread_bps = 10  # 10 basis points
        self.min_spread_bps = 5
        self.max_spread_bps = 50
        self.inventory_skew_factor = 0.1
        self.volatility_multiplier = 2.0
    
    async def analyze(self, market_data: MarketData) -> Optional[Signal]:
        """
        Generate market making orders
        
        Returns bid/ask prices instead of buy/sell signals
        """
        
        if len(market_data.price_history) < 20:
            return None
        
        # Calculate volatility using ATR
        atr = TechnicalIndicators.atr(
            market_data.high_history,
            market_data.low_history,
            market_data.price_history
        )
        
        mid_price = (market_data.bid + market_data.ask) / 2
        
        # Adjust spread based on volatility
        volatility_ratio = atr / mid_price if mid_price > 0 else 0
        adjusted_spread_bps = self.target_spread_bps * (1 + volatility_ratio * self.volatility_multiplier)
        adjusted_spread_bps = max(self.min_spread_bps, min(self.max_spread_bps, adjusted_spread_bps))
        
        half_spread = mid_price * (adjusted_spread_bps / 10000) / 2
        
        # Market making signals (both buy and sell)
        return Signal(
            signal_type=SignalType.HOLD,  # Special: represents market making
            strength=0.8,
            price=mid_price,
            reason=f"Market making: spread={adjusted_spread_bps:.1f}bps, half_spread=${half_spread:.4f}, volatility={volatility_ratio:.2%}",
            timestamp=market_data.timestamp
        )


class GridTradingStrategy(BaseStrategy):
    """
    Grid Trading Strategy
    
    - Places buy orders at fixed price intervals below current price
    - Places sell orders at fixed intervals above current price
    - Profits from ranging markets
    """
    
    def __init__(self):
        super().__init__("GridTrading")
        self.grid_levels = 5
        self.grid_spacing_pct = 0.5  # 0.5% between levels
        self.min_price_move = 0.002  # 0.2% minimum move to trigger
    
    async def analyze(self, market_data: MarketData) -> Optional[Signal]:
        """Analyze grid trading opportunities"""
        
        if len(market_data.price_history) < 2:
            return None
        
        current_price = market_data.price
        previous_price = market_data.price_history[-2]
        
        # Calculate price movement
        price_change_pct = abs(current_price - previous_price) / previous_price
        
        if price_change_pct < self.min_price_move:
            return None
        
        # Check if price is at a grid level
        grid_spacing = current_price * self.grid_spacing_pct / 100
        
        # Buy at lower grid levels
        if current_price < previous_price:
            strength = min(1.0, price_change_pct / self.min_price_move * 0.5)
            
            return Signal(
                signal_type=SignalType.BUY,
                strength=strength,
                price=current_price,
                reason=f"Grid buy: Price dropped to grid level, spacing=${grid_spacing:.4f}",
                timestamp=market_data.timestamp
            )
        
        # Sell at upper grid levels
        elif current_price > previous_price:
            strength = min(1.0, price_change_pct / self.min_price_move * 0.5)
            
            return Signal(
                signal_type=SignalType.SELL,
                strength=strength,
                price=current_price,
                reason=f"Grid sell: Price rose to grid level, spacing=${grid_spacing:.4f}",
                timestamp=market_data.timestamp
            )
        
        return None


class StrategyManager:
    """Manages multiple trading strategies"""
    
    def __init__(self):
        self.strategies: List[BaseStrategy] = []
        self.active_signals: Dict[str, Signal] = {}
    
    def add_strategy(self, strategy: BaseStrategy):
        """Add a strategy to the manager"""
        self.strategies.append(strategy)
        logger.info(f"Added strategy: {strategy.name}")
    
    async def analyze_market(self, market_data: MarketData) -> List[Signal]:
        """
        Run all strategies and collect signals
        
        Args:
            market_data: Current market data
            
        Returns:
            List of signals from all strategies
        """
        signals = []
        
        for strategy in self.strategies:
            if not strategy.enabled:
                continue
            
            try:
                signal = await strategy.analyze(market_data)
                if signal:
                    signals.append(signal)
                    logger.info(f"Strategy {strategy.name} generated signal: {signal.signal_type.value} (strength={signal.strength:.2f})")
            
            except Exception as e:
                logger.error(f"Error in strategy {strategy.name}: {e}")
        
        return signals
    
    def get_consensus_signal(self, signals: List[Signal]) -> Optional[Signal]:
        """
        Combine multiple signals into a consensus
        
        Args:
            signals: List of signals from different strategies
            
        Returns:
            Consensus signal or None
        """
        if not signals:
            return None
        
        # Count signals by type
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        sell_signals = [s for s in signals if s.signal_type == SignalType.SELL]
        
        # Calculate weighted strength
        buy_strength = sum(s.strength for s in buy_signals) / len(signals) if buy_signals else 0
        sell_strength = sum(s.strength for s in sell_signals) / len(signals) if sell_signals else 0
        
        # Determine consensus
        if buy_strength > sell_strength and buy_strength > 0.5:
            strongest_buy = max(buy_signals, key=lambda s: s.strength)
            return Signal(
                signal_type=SignalType.BUY,
                strength=buy_strength,
                price=strongest_buy.price,
                reason=f"Consensus BUY ({len(buy_signals)}/{len(signals)} strategies agree)",
                timestamp=strongest_buy.timestamp
            )
        
        elif sell_strength > buy_strength and sell_strength > 0.5:
            strongest_sell = max(sell_signals, key=lambda s: s.strength)
            return Signal(
                signal_type=SignalType.SELL,
                strength=sell_strength,
                price=strongest_sell.price,
                reason=f"Consensus SELL ({len(sell_signals)}/{len(signals)} strategies agree)",
                timestamp=strongest_sell.timestamp
            )
        
        return None


class OrderFlowStrategy(BaseStrategy):
    """
    Order Flow Analysis Strategy
    
    Analyzes:
    - Order book imbalance (bid/ask ratio)
    - Large orders (whale activity)
    - Recent trade flow (aggressive buyers vs sellers)
    """
    
    def __init__(self):
        super().__init__("OrderFlow")
        self.analyzer = OrderFlowAnalyzer()
    
    async def analyze(self, market_data: Dict, position_info: Optional[Dict] = None) -> Optional[Signal]:
        """Analyze order flow for trading signals"""
        try:
            # Access MarketData object attributes, not dict keys
            current_price = market_data.price if hasattr(market_data, 'price') else 0
            if current_price == 0:
                return None
            
            # Get order flow signal
            signal = await self.analyzer.get_combined_orderflow_signal(
                market_id=settings.trading_market_id
            )
            
            if not signal:
                return None
            
            # Convert order flow signal to trading signal
            if signal.signal == "bullish" and signal.strength >= 0.6:
                return Signal(
                    signal_type=SignalType.BUY,
                    strength=signal.strength,
                    price=current_price,
                    reason=f"Order Flow: {signal.reason} (imbalance={signal.metrics.get('bid_ask_imbalance', 0):.2f})",
                    timestamp=datetime.now()
                )
            
            elif signal.signal == "bearish" and signal.strength >= 0.6:
                return Signal(
                    signal_type=SignalType.SELL,
                    strength=signal.strength,
                    price=current_price,
                    reason=f"Order Flow: {signal.reason} (imbalance={signal.metrics.get('bid_ask_imbalance', 0):.2f})",
                    timestamp=datetime.now()
                )
            
            return None
        
        except Exception as e:
            logger.error(f"OrderFlow strategy error: {e}")
            return None


class SentimentStrategy(BaseStrategy):
    """
    News & Sentiment Analysis Strategy
    
    Analyzes:
    - Crypto Fear & Greed Index
    - News sentiment (positive/negative keywords)
    - CoinGecko community sentiment
    - Social media trends
    """
    
    def __init__(self, symbol: str = "BTC"):
        super().__init__("Sentiment")
        self.analyzer = SentimentAnalyzer()
        self.symbol = symbol
    
    async def analyze(self, market_data: Dict, position_info: Optional[Dict] = None) -> Optional[Signal]:
        """Analyze market sentiment for trading signals"""
        try:
            # Access MarketData object attributes, not dict keys
            current_price = market_data.price if hasattr(market_data, 'price') else 0
            if current_price == 0:
                return None
            
            # Get combined sentiment
            signal = await self.analyzer.get_combined_sentiment(self.symbol)
            
            if not signal:
                return None
            
            # Convert sentiment to trading signal
            # Note: Sentiment is a longer-term signal, so we use lower strength
            if signal.sentiment == "bullish" and signal.confidence >= 0.6:
                return Signal(
                    signal_type=SignalType.BUY,
                    strength=signal.confidence * 0.7,  # Reduce weight slightly
                    price=current_price,
                    reason=f"Sentiment: {signal.reason} (score={signal.score:.2f})",
                    timestamp=datetime.now()
                )
            
            elif signal.sentiment == "bearish" and signal.confidence >= 0.6:
                return Signal(
                    signal_type=SignalType.SELL,
                    strength=signal.confidence * 0.7,  # Reduce weight slightly
                    price=current_price,
                    reason=f"Sentiment: {signal.reason} (score={signal.score:.2f})",
                    timestamp=datetime.now()
                )
            
            return None
        
        except Exception as e:
            logger.error(f"Sentiment strategy error: {e}")
            return None
    
    async def close(self):
        """Cleanup resources"""
        await self.analyzer.close()

