"""
Technical indicators for trading strategies
"""
import numpy as np
import pandas as pd
from typing import List, Tuple, Optional


class TechnicalIndicators:
    """Collection of technical analysis indicators"""
    
    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> float:
        """
        Calculate Relative Strength Index
        
        Args:
            prices: List of prices (most recent last)
            period: RSI period (default 14)
            
        Returns:
            RSI value (0-100)
        """
        if len(prices) < period + 1:
            return 50.0  # Neutral if not enough data
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def ema(prices: List[float], period: int) -> float:
        """
        Calculate Exponential Moving Average
        
        Args:
            prices: List of prices
            period: EMA period
            
        Returns:
            EMA value
        """
        if len(prices) < period:
            return np.mean(prices)
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    @staticmethod
    def sma(prices: List[float], period: int) -> float:
        """Simple Moving Average"""
        if len(prices) < period:
            return np.mean(prices)
        return np.mean(prices[-period:])
    
    @staticmethod
    def macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[float, float, float]:
        """
        Calculate MACD (Moving Average Convergence Divergence)
        
        Returns:
            (macd_line, signal_line, histogram)
        """
        if len(prices) < slow:
            return (0.0, 0.0, 0.0)
        
        ema_fast = TechnicalIndicators.ema(prices, fast)
        ema_slow = TechnicalIndicators.ema(prices, slow)
        macd_line = ema_fast - ema_slow
        
        # For signal line, we'd need historical MACD values
        # Simplified: use current MACD as signal
        signal_line = macd_line
        histogram = macd_line - signal_line
        
        return (macd_line, signal_line, histogram)
    
    @staticmethod
    def bollinger_bands(prices: List[float], period: int = 20, std_dev: float = 2.0) -> Tuple[float, float, float]:
        """
        Calculate Bollinger Bands
        
        Returns:
            (upper_band, middle_band, lower_band)
        """
        if len(prices) < period:
            mean = np.mean(prices)
            return (mean, mean, mean)
        
        recent_prices = prices[-period:]
        middle = np.mean(recent_prices)
        std = np.std(recent_prices)
        
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        
        return (upper, middle, lower)
    
    @staticmethod
    def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """
        Calculate Average True Range (volatility indicator)
        
        Args:
            highs: List of high prices
            lows: List of low prices
            closes: List of close prices
            period: ATR period
            
        Returns:
            ATR value
        """
        if len(closes) < 2:
            return 0.0
        
        true_ranges = []
        for i in range(1, len(closes)):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i-1])
            low_close = abs(lows[i] - closes[i-1])
            true_range = max(high_low, high_close, low_close)
            true_ranges.append(true_range)
        
        if len(true_ranges) < period:
            return np.mean(true_ranges)
        
        return np.mean(true_ranges[-period:])
    
    @staticmethod
    def obv(prices: List[float], volumes: List[float]) -> float:
        """
        On-Balance Volume indicator
        
        Args:
            prices: List of prices
            volumes: List of volumes
            
        Returns:
            OBV value
        """
        if len(prices) < 2 or len(volumes) < 2:
            return 0.0
        
        obv = 0
        for i in range(1, len(prices)):
            if prices[i] > prices[i-1]:
                obv += volumes[i]
            elif prices[i] < prices[i-1]:
                obv -= volumes[i]
        
        return obv
    
    @staticmethod
    def stochastic_oscillator(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Tuple[float, float]:
        """
        Stochastic Oscillator
        
        Returns:
            (%K, %D) values (0-100)
        """
        if len(closes) < period:
            return (50.0, 50.0)
        
        recent_highs = highs[-period:]
        recent_lows = lows[-period:]
        current_close = closes[-1]
        
        highest_high = max(recent_highs)
        lowest_low = min(recent_lows)
        
        if highest_high == lowest_low:
            return (50.0, 50.0)
        
        k = 100 * (current_close - lowest_low) / (highest_high - lowest_low)
        d = k  # Simplified: %D would normally be 3-period SMA of %K
        
        return (k, d)
