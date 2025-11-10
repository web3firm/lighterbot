"""
Trading strategy framework and example strategies
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from market_data import MarketData
from order_manager import OrderManager, Position
from risk_manager import RiskManager


@dataclass
class Signal:
    """Trading signal"""
    symbol: str
    action: str  # "buy", "sell", "close", "hold"
    size: Optional[float] = None
    price: Optional[float] = None
    confidence: float = 1.0
    reason: str = ""
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class Strategy(ABC):
    """Base class for trading strategies"""
    
    def __init__(self, symbol: str, market_data: MarketData, 
                 order_manager: OrderManager, risk_manager: RiskManager):
        self.symbol = symbol
        self.market_data = market_data
        self.order_manager = order_manager
        self.risk_manager = risk_manager
        
        # Strategy state
        self.enabled = True
        self.last_signal: Optional[Signal] = None
        self.performance_history = []
    
    @abstractmethod
    def generate_signal(self) -> Signal:
        """
        Generate trading signal based on strategy logic
        
        Returns:
            Signal object with action and details
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Return strategy name"""
        pass
    
    def execute_signal(self, signal: Signal) -> bool:
        """
        Execute a trading signal
        
        Args:
            signal: Signal to execute
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            print(f"Strategy {self.get_name()} is disabled")
            return False
        
        if signal.action == "hold":
            return True
        
        # Check risk before executing
        if signal.action in ["buy", "sell"]:
            size = signal.size or self.risk_manager.calculate_safe_order_size(
                signal.symbol, signal.action, target_leverage=5
            )
            
            passed, reason = self.risk_manager.check_order_risk(
                signal.symbol, signal.action, size, signal.price
            )
            
            if not passed:
                print(f"Order rejected by risk manager: {reason}")
                return False
            
            # Place order
            if signal.price:
                order = self.order_manager.place_limit_order(
                    signal.symbol, signal.action, size, signal.price
                )
            else:
                order = self.order_manager.place_market_order(
                    signal.symbol, signal.action, size
                )
            
            if order:
                print(f"Signal executed: {signal.action} {size} {signal.symbol} - {signal.reason}")
                self.last_signal = signal
                return True
            else:
                print(f"Failed to execute signal: {signal.action} {signal.symbol}")
                return False
        
        elif signal.action == "close":
            # Close position
            order = self.order_manager.close_position(signal.symbol)
            if order:
                print(f"Position closed for {signal.symbol} - {signal.reason}")
                self.last_signal = signal
                return True
            else:
                print(f"Failed to close position for {signal.symbol}")
                return False
        
        return False
    
    def run(self) -> bool:
        """
        Run one iteration of the strategy
        
        Returns:
            True if signal was generated and executed
        """
        try:
            signal = self.generate_signal()
            if signal.action != "hold":
                return self.execute_signal(signal)
            return True
        except Exception as e:
            print(f"Error running strategy {self.get_name()}: {e}")
            return False


class EMACrossoverStrategy(Strategy):
    """
    EMA Crossover Strategy
    - Buy when fast EMA crosses above slow EMA
    - Sell when fast EMA crosses below slow EMA
    """
    
    def __init__(self, symbol: str, market_data: MarketData,
                 order_manager: OrderManager, risk_manager: RiskManager,
                 fast_period: int = 12, slow_period: int = 26):
        super().__init__(symbol, market_data, order_manager, risk_manager)
        self.fast_period = fast_period
        self.slow_period = slow_period
        
        # Price history
        self.price_history = []
        self.max_history = max(fast_period, slow_period) * 2
        
        # EMA state
        self.fast_ema: Optional[float] = None
        self.slow_ema: Optional[float] = None
        self.prev_fast_ema: Optional[float] = None
        self.prev_slow_ema: Optional[float] = None
    
    def get_name(self) -> str:
        return f"EMA_Crossover_{self.fast_period}_{self.slow_period}"
    
    def _calculate_ema(self, prices: list, period: int, prev_ema: Optional[float] = None) -> float:
        """Calculate EMA"""
        if len(prices) < period:
            return sum(prices) / len(prices) if prices else 0.0
        
        if prev_ema is None:
            # Initialize with SMA
            return sum(prices[-period:]) / period
        
        # EMA formula: EMA = (Price - Previous EMA) * multiplier + Previous EMA
        multiplier = 2 / (period + 1)
        return (prices[-1] - prev_ema) * multiplier + prev_ema
    
    def _update_price_history(self):
        """Update price history"""
        current_price = self.market_data.get_current_price(self.symbol)
        if current_price > 0:
            self.price_history.append(current_price)
            
            # Keep only max_history prices
            if len(self.price_history) > self.max_history:
                self.price_history = self.price_history[-self.max_history:]
    
    def _update_emas(self):
        """Update EMA values"""
        if len(self.price_history) < self.slow_period:
            return
        
        # Store previous values
        self.prev_fast_ema = self.fast_ema
        self.prev_slow_ema = self.slow_ema
        
        # Calculate new EMAs
        self.fast_ema = self._calculate_ema(self.price_history, self.fast_period, self.prev_fast_ema)
        self.slow_ema = self._calculate_ema(self.price_history, self.slow_period, self.prev_slow_ema)
    
    def generate_signal(self) -> Signal:
        """Generate signal based on EMA crossover"""
        # Update data
        self._update_price_history()
        self._update_emas()
        
        # Need enough history
        if self.fast_ema is None or self.slow_ema is None:
            return Signal(self.symbol, "hold", reason="Insufficient data for EMAs")
        
        if self.prev_fast_ema is None or self.prev_slow_ema is None:
            return Signal(self.symbol, "hold", reason="Waiting for EMA history")
        
        # Get current position
        position = self.order_manager.get_position(self.symbol)
        
        # Check for crossovers
        # Bullish crossover: fast crosses above slow
        if self.prev_fast_ema <= self.prev_slow_ema and self.fast_ema > self.slow_ema:
            if position and position.is_short:
                # Close short position first
                return Signal(
                    self.symbol, "close",
                    reason=f"Bullish crossover (close short) - Fast EMA: {self.fast_ema:.2f}, Slow EMA: {self.slow_ema:.2f}"
                )
            elif not position or position.size == 0:
                # Open long position
                size = self.risk_manager.calculate_safe_order_size(self.symbol, "buy", target_leverage=3)
                return Signal(
                    self.symbol, "buy", size=size,
                    reason=f"Bullish crossover - Fast EMA: {self.fast_ema:.2f}, Slow EMA: {self.slow_ema:.2f}",
                    confidence=0.8
                )
        
        # Bearish crossover: fast crosses below slow
        elif self.prev_fast_ema >= self.prev_slow_ema and self.fast_ema < self.slow_ema:
            if position and position.is_long:
                # Close long position first
                return Signal(
                    self.symbol, "close",
                    reason=f"Bearish crossover (close long) - Fast EMA: {self.fast_ema:.2f}, Slow EMA: {self.slow_ema:.2f}"
                )
            elif not position or position.size == 0:
                # Open short position
                size = self.risk_manager.calculate_safe_order_size(self.symbol, "sell", target_leverage=3)
                return Signal(
                    self.symbol, "sell", size=size,
                    reason=f"Bearish crossover - Fast EMA: {self.fast_ema:.2f}, Slow EMA: {self.slow_ema:.2f}",
                    confidence=0.8
                )
        
        # Check if we should close position due to risk
        if position and position.size != 0:
            should_close, reason = self.risk_manager.should_emergency_close(self.symbol)
            if should_close:
                return Signal(self.symbol, "close", reason=f"Emergency close: {reason}")
        
        return Signal(self.symbol, "hold", reason=f"Fast EMA: {self.fast_ema:.2f}, Slow EMA: {self.slow_ema:.2f}")


class MomentumStrategy(Strategy):
    """
    Momentum Strategy
    - Buy when price momentum is strongly positive
    - Sell when price momentum is strongly negative
    """
    
    def __init__(self, symbol: str, market_data: MarketData,
                 order_manager: OrderManager, risk_manager: RiskManager,
                 lookback_period: int = 20, threshold: float = 0.02):
        super().__init__(symbol, market_data, order_manager, risk_manager)
        self.lookback_period = lookback_period
        self.threshold = threshold  # 2% momentum threshold
        
        self.price_history = []
        self.max_history = lookback_period * 2
    
    def get_name(self) -> str:
        return f"Momentum_{self.lookback_period}"
    
    def _calculate_momentum(self) -> Optional[float]:
        """Calculate price momentum as percentage change"""
        if len(self.price_history) < self.lookback_period:
            return None
        
        old_price = self.price_history[-self.lookback_period]
        current_price = self.price_history[-1]
        
        return (current_price - old_price) / old_price
    
    def generate_signal(self) -> Signal:
        """Generate signal based on momentum"""
        # Update price history
        current_price = self.market_data.get_current_price(self.symbol)
        if current_price > 0:
            self.price_history.append(current_price)
            if len(self.price_history) > self.max_history:
                self.price_history = self.price_history[-self.max_history:]
        
        # Calculate momentum
        momentum = self._calculate_momentum()
        if momentum is None:
            return Signal(self.symbol, "hold", reason="Insufficient data for momentum")
        
        # Get current position
        position = self.order_manager.get_position(self.symbol)
        
        # Strong positive momentum
        if momentum > self.threshold:
            if not position or position.size == 0:
                size = self.risk_manager.calculate_safe_order_size(self.symbol, "buy", target_leverage=3)
                return Signal(
                    self.symbol, "buy", size=size,
                    reason=f"Strong positive momentum: {momentum:.2%}",
                    confidence=min(momentum / self.threshold, 1.0)
                )
            elif position.is_short:
                return Signal(
                    self.symbol, "close",
                    reason=f"Positive momentum, closing short: {momentum:.2%}"
                )
        
        # Strong negative momentum
        elif momentum < -self.threshold:
            if not position or position.size == 0:
                size = self.risk_manager.calculate_safe_order_size(self.symbol, "sell", target_leverage=3)
                return Signal(
                    self.symbol, "sell", size=size,
                    reason=f"Strong negative momentum: {momentum:.2%}",
                    confidence=min(abs(momentum) / self.threshold, 1.0)
                )
            elif position.is_long:
                return Signal(
                    self.symbol, "close",
                    reason=f"Negative momentum, closing long: {momentum:.2%}"
                )
        
        # Check emergency close
        if position and position.size != 0:
            should_close, reason = self.risk_manager.should_emergency_close(self.symbol)
            if should_close:
                return Signal(self.symbol, "close", reason=f"Emergency close: {reason}")
        
        return Signal(self.symbol, "hold", reason=f"Momentum: {momentum:.2%}")


class StrategyManager:
    """Manager for multiple strategies"""
    
    def __init__(self):
        self.strategies: Dict[str, Strategy] = {}
    
    def add_strategy(self, strategy: Strategy):
        """Add a strategy"""
        self.strategies[strategy.get_name()] = strategy
        print(f"Strategy added: {strategy.get_name()}")
    
    def remove_strategy(self, name: str):
        """Remove a strategy"""
        if name in self.strategies:
            del self.strategies[name]
            print(f"Strategy removed: {name}")
    
    def enable_strategy(self, name: str):
        """Enable a strategy"""
        if name in self.strategies:
            self.strategies[name].enabled = True
            print(f"Strategy enabled: {name}")
    
    def disable_strategy(self, name: str):
        """Disable a strategy"""
        if name in self.strategies:
            self.strategies[name].enabled = False
            print(f"Strategy disabled: {name}")
    
    def run_all(self) -> Dict[str, bool]:
        """
        Run all enabled strategies
        
        Returns:
            Dictionary of strategy results
        """
        results = {}
        for name, strategy in self.strategies.items():
            if strategy.enabled:
                try:
                    success = strategy.run()
                    results[name] = success
                except Exception as e:
                    print(f"Error running strategy {name}: {e}")
                    results[name] = False
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all strategies"""
        status = {}
        for name, strategy in self.strategies.items():
            status[name] = {
                "enabled": strategy.enabled,
                "last_signal": strategy.last_signal.action if strategy.last_signal else None,
                "last_signal_time": strategy.last_signal.timestamp if strategy.last_signal else None
            }
        return status
