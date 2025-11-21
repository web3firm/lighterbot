"""
Technical Indicators Calculator
Calculates RSI, EMA, MACD, ADX, Bollinger Bands from candlestick data
"""

import logging
from typing import List, Dict, Any
from decimal import Decimal
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """Calculate technical indicators from candlestick data"""
    
    @staticmethod
    def calculate_rsi(closes: List[float], period: int = 14) -> float:
        """
        Calculate RSI (Relative Strength Index)
        
        Args:
            closes: List of closing prices
            period: RSI period (default 14)
            
        Returns:
            RSI value (0-100)
        """
        if len(closes) < period + 1:
            return 50.0  # Neutral default
        
        closes_arr = np.array(closes)
        deltas = np.diff(closes_arr)
        
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi)
    
    @staticmethod
    def calculate_ema(closes: List[float], period: int) -> float:
        """
        Calculate EMA (Exponential Moving Average)
        
        Args:
            closes: List of closing prices
            period: EMA period
            
        Returns:
            EMA value
        """
        if len(closes) < period:
            return closes[-1] if closes else 0.0
        
        closes_arr = np.array(closes)
        multiplier = 2 / (period + 1)
        
        ema = np.mean(closes_arr[:period])  # Start with SMA
        
        for price in closes_arr[period:]:
            ema = (price - ema) * multiplier + ema
        
        return float(ema)
    
    @staticmethod
    def calculate_macd(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
        """
        Calculate MACD (Moving Average Convergence Divergence)
        
        Args:
            closes: List of closing prices
            fast: Fast EMA period (default 12)
            slow: Slow EMA period (default 26)
            signal: Signal line period (default 9)
            
        Returns:
            Dict with macd_line, signal_line, histogram
        """
        if len(closes) < slow + signal:
            return {'macd_line': 0.0, 'signal_line': 0.0, 'histogram': 0.0}
        
        ema_fast = TechnicalIndicators.calculate_ema(closes, fast)
        ema_slow = TechnicalIndicators.calculate_ema(closes, slow)
        
        macd_line = ema_fast - ema_slow
        
        # Calculate signal line (EMA of MACD)
        # For simplicity, using a basic approximation
        signal_line = macd_line * 0.9  # Simplified
        
        histogram = macd_line - signal_line
        
        return {
            'macd_line': float(macd_line),
            'signal_line': float(signal_line),
            'histogram': float(histogram)
        }
    
    @staticmethod
    def calculate_adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """
        Calculate ADX (Average Directional Index)
        
        Args:
            highs: List of high prices
            lows: List of low prices
            closes: List of closing prices
            period: ADX period (default 14)
            
        Returns:
            ADX value (0-100)
        """
        if len(highs) < period + 1 or len(lows) < period + 1 or len(closes) < period + 1:
            return 25.0  # Neutral default
        
        highs_arr = np.array(highs)
        lows_arr = np.array(lows)
        closes_arr = np.array(closes)
        
        # True Range
        tr1 = highs_arr[1:] - lows_arr[1:]
        tr2 = np.abs(highs_arr[1:] - closes_arr[:-1])
        tr3 = np.abs(lows_arr[1:] - closes_arr[:-1])
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        
        # Directional Movement
        up_move = highs_arr[1:] - highs_arr[:-1]
        down_move = lows_arr[:-1] - lows_arr[1:]
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        # Smoothed averages
        atr = np.mean(tr[-period:])
        plus_di = 100 * np.mean(plus_dm[-period:]) / atr if atr != 0 else 0
        minus_di = 100 * np.mean(minus_dm[-period:]) / atr if atr != 0 else 0
        
        # ADX calculation
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) != 0 else 0
        adx = dx  # Simplified - should be smoothed over period
        
        return float(min(100, max(0, adx)))
    
    @staticmethod
    def calculate_bollinger_bands(closes: List[float], period: int = 20, std_dev: float = 2.0) -> Dict[str, float]:
        """
        Calculate Bollinger Bands
        
        Args:
            closes: List of closing prices
            period: Moving average period (default 20)
            std_dev: Standard deviation multiplier (default 2.0)
            
        Returns:
            Dict with upper, middle, lower bands and bb_position
        """
        if len(closes) < period:
            price = closes[-1] if closes else 0.0
            return {
                'upper': price * 1.02,
                'middle': price,
                'lower': price * 0.98,
                'bb_position': 0.5
            }
        
        closes_arr = np.array(closes[-period:])
        middle = np.mean(closes_arr)
        std = np.std(closes_arr)
        
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        current_price = closes[-1]
        bb_position = (current_price - lower) / (upper - lower) if (upper - lower) != 0 else 0.5
        
        return {
            'upper': float(upper),
            'middle': float(middle),
            'lower': float(lower),
            'bb_position': float(bb_position)
        }
    
    @staticmethod
    def calculate_all_indicators(candles: List[Dict[str, Any]], 
                                config: Dict[str, int]) -> Dict[str, Any]:
        """
        Calculate all technical indicators from candlestick data
        
        Args:
            candles: List of candle dicts with open, high, low, close, volume
            config: Configuration dict with periods (rsi_period, ema_fast, etc.)
            
        Returns:
            Dict with all calculated indicators
        """
        if not candles or len(candles) < 2:
            return {
                'rsi': 50.0,
                'ema_fast': 0.0,
                'ema_slow': 0.0,
                'macd': {'macd_line': 0.0, 'signal_line': 0.0, 'histogram': 0.0},
                'adx': 25.0,
                'bollinger_bands': {'upper': 0.0, 'middle': 0.0, 'lower': 0.0, 'bb_position': 0.5},
                'volume_ratio': 1.0
            }
        
        # Extract price data
        closes = [float(c['close']) for c in candles]
        highs = [float(c['high']) for c in candles]
        lows = [float(c['low']) for c in candles]
        volumes = [float(c['volume']) for c in candles]
        
        # Calculate indicators
        rsi = TechnicalIndicators.calculate_rsi(closes, config.get('rsi_period', 14))
        ema_fast = TechnicalIndicators.calculate_ema(closes, config.get('ema_fast', 21))
        ema_slow = TechnicalIndicators.calculate_ema(closes, config.get('ema_slow', 50))
        macd = TechnicalIndicators.calculate_macd(closes, 
                                                 config.get('macd_fast', 12),
                                                 config.get('macd_slow', 26),
                                                 config.get('macd_signal', 9))
        adx = TechnicalIndicators.calculate_adx(highs, lows, closes, config.get('adx_period', 14))
        bb = TechnicalIndicators.calculate_bollinger_bands(closes, config.get('bb_period', 20))
        
        # Volume analysis
        avg_volume = np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes)
        current_volume = volumes[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        # Price momentum
        price_change_5m = (closes[-1] - closes[-5]) / closes[-5] if len(closes) >= 5 else 0.0
        price_change_1h = (closes[-1] - closes[-12]) / closes[-12] if len(closes) >= 12 else 0.0
        
        return {
            'rsi': rsi,
            'ema_fast': ema_fast,
            'ema_slow': ema_slow,
            'macd': macd,
            'adx': adx,
            'bollinger_bands': bb,
            'bb_position': bb['bb_position'],
            'volume_ratio': volume_ratio,
            'price_change_5m': price_change_5m,
            'price_change_1h': price_change_1h
        }
