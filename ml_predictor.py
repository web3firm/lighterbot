"""
Machine Learning Price Prediction
Predicts next candle direction using recent patterns
"""
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass
from collections import deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class PricePrediction:
    """ML prediction result"""
    direction: str  # "up" or "down"
    confidence: float  # 0-1
    target_price: float
    probability: float  # Raw probability
    pattern_match: str  # Which pattern matched


class MLPredictor:
    """
    Simple ML predictor using pattern recognition
    
    Methods:
    1. Candle Pattern Recognition (hammer, engulfing, etc.)
    2. Support/Resistance Pattern
    3. Volume Profile Pattern
    4. Momentum Pattern
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.price_history = deque(maxlen=100)
        self.volume_history = deque(maxlen=100)
        self.predictions_correct = 0
        self.predictions_total = 0
        
    def add_candle(self, open_price: float, high: float, low: float, close: float, volume: float):
        """Add candle data for learning"""
        self.price_history.append({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })
        self.volume_history.append(volume)
    
    def predict_next_candle(
        self,
        current_price: float,
        recent_highs: List[float],
        recent_lows: List[float],
        recent_volumes: List[float]
    ) -> Optional[PricePrediction]:
        """
        Predict next candle direction using multiple patterns
        
        Returns:
            PricePrediction with direction and confidence
        """
        if len(self.price_history) < 20:
            return None
        
        predictions = []
        
        # 1. Candle Pattern Analysis
        candle_pred = self._analyze_candle_patterns()
        if candle_pred:
            predictions.append(candle_pred)
        
        # 2. Support/Resistance Analysis
        sr_pred = self._analyze_support_resistance(current_price, recent_highs, recent_lows)
        if sr_pred:
            predictions.append(sr_pred)
        
        # 3. Volume Pattern Analysis
        vol_pred = self._analyze_volume_pattern(recent_volumes)
        if vol_pred:
            predictions.append(vol_pred)
        
        # 4. Momentum Analysis
        momentum_pred = self._analyze_momentum()
        if momentum_pred:
            predictions.append(momentum_pred)
        
        if not predictions:
            return None
        
        # Combine predictions (weighted voting)
        up_votes = sum(1 for p in predictions if p['direction'] == 'up')
        down_votes = sum(1 for p in predictions if p['direction'] == 'down')
        total_votes = len(predictions)
        
        if up_votes > down_votes:
            direction = "up"
            confidence = up_votes / total_votes
        elif down_votes > up_votes:
            direction = "down"
            confidence = down_votes / total_votes
        else:
            # Tie - use strongest signal
            strongest = max(predictions, key=lambda x: x['confidence'])
            direction = strongest['direction']
            confidence = strongest['confidence']
        
        # Calculate target price (1-2% move)
        move_percent = 0.015  # 1.5% target
        if direction == "up":
            target = current_price * (1 + move_percent)
        else:
            target = current_price * (1 - move_percent)
        
        # Get pattern name from strongest signal
        strongest_pattern = max(predictions, key=lambda x: x['confidence'])
        
        return PricePrediction(
            direction=direction,
            confidence=confidence,
            target_price=target,
            probability=confidence,
            pattern_match=strongest_pattern['pattern']
        )
    
    def _analyze_candle_patterns(self) -> Optional[dict]:
        """Detect bullish/bearish candle patterns"""
        if len(self.price_history) < 3:
            return None
        
        candles = list(self.price_history)
        last = candles[-1]
        prev = candles[-2]
        
        # Bullish Engulfing
        if (prev['close'] < prev['open'] and  # Previous red
            last['close'] > last['open'] and  # Current green
            last['open'] < prev['close'] and  # Opens below prev close
            last['close'] > prev['open']):    # Closes above prev open
            return {'direction': 'up', 'confidence': 0.75, 'pattern': 'Bullish Engulfing'}
        
        # Bearish Engulfing
        if (prev['close'] > prev['open'] and  # Previous green
            last['close'] < last['open'] and  # Current red
            last['open'] > prev['close'] and  # Opens above prev close
            last['close'] < prev['open']):    # Closes below prev open
            return {'direction': 'down', 'confidence': 0.75, 'pattern': 'Bearish Engulfing'}
        
        # Hammer (bullish reversal)
        body = abs(last['close'] - last['open'])
        lower_wick = min(last['open'], last['close']) - last['low']
        upper_wick = last['high'] - max(last['open'], last['close'])
        
        if lower_wick > body * 2 and upper_wick < body * 0.3:
            return {'direction': 'up', 'confidence': 0.65, 'pattern': 'Hammer'}
        
        # Shooting Star (bearish reversal)
        if upper_wick > body * 2 and lower_wick < body * 0.3:
            return {'direction': 'down', 'confidence': 0.65, 'pattern': 'Shooting Star'}
        
        # Three Consecutive Candles (momentum)
        if len(candles) >= 3:
            last_3 = candles[-3:]
            all_green = all(c['close'] > c['open'] for c in last_3)
            all_red = all(c['close'] < c['open'] for c in last_3)
            
            if all_green:
                return {'direction': 'up', 'confidence': 0.70, 'pattern': 'Three Green Candles'}
            if all_red:
                return {'direction': 'down', 'confidence': 0.70, 'pattern': 'Three Red Candles'}
        
        return None
    
    def _analyze_support_resistance(
        self,
        current_price: float,
        recent_highs: List[float],
        recent_lows: List[float]
    ) -> Optional[dict]:
        """Detect bounce from support/resistance"""
        if not recent_highs or not recent_lows:
            return None
        
        # Find nearby support/resistance levels
        support = min(recent_lows[-20:]) if len(recent_lows) >= 20 else min(recent_lows)
        resistance = max(recent_highs[-20:]) if len(recent_highs) >= 20 else max(recent_highs)
        
        range_size = resistance - support
        if range_size == 0:
            return None
        
        # Near support (within 2% above)
        if current_price <= support * 1.02:
            return {'direction': 'up', 'confidence': 0.70, 'pattern': 'Support Bounce'}
        
        # Near resistance (within 2% below)
        if current_price >= resistance * 0.98:
            return {'direction': 'down', 'confidence': 0.70, 'pattern': 'Resistance Rejection'}
        
        return None
    
    def _analyze_volume_pattern(self, recent_volumes: List[float]) -> Optional[dict]:
        """Detect volume-based signals"""
        if len(recent_volumes) < 10 or len(self.price_history) < 2:
            return None
        
        current_vol = recent_volumes[-1]
        avg_vol = sum(recent_volumes[-10:]) / 10
        
        last_candle = list(self.price_history)[-1]
        is_green = last_candle['close'] > last_candle['open']
        
        # High volume breakout
        if current_vol > avg_vol * 1.5:
            if is_green:
                return {'direction': 'up', 'confidence': 0.68, 'pattern': 'Volume Breakout Up'}
            else:
                return {'direction': 'down', 'confidence': 0.68, 'pattern': 'Volume Breakout Down'}
        
        return None
    
    def _analyze_momentum(self) -> Optional[dict]:
        """Detect momentum continuation"""
        if len(self.price_history) < 10:
            return None
        
        candles = list(self.price_history)[-10:]
        closes = [c['close'] for c in candles]
        
        # Calculate momentum (price change over 10 candles)
        momentum = (closes[-1] - closes[0]) / closes[0]
        
        # Strong upward momentum
        if momentum > 0.02:  # 2% up
            return {'direction': 'up', 'confidence': 0.60, 'pattern': 'Momentum Up'}
        
        # Strong downward momentum
        if momentum < -0.02:  # 2% down
            return {'direction': 'down', 'confidence': 0.60, 'pattern': 'Momentum Down'}
        
        return None
    
    def record_prediction_result(self, was_correct: bool):
        """Track prediction accuracy"""
        self.predictions_total += 1
        if was_correct:
            self.predictions_correct += 1
        
        if self.predictions_total > 0:
            accuracy = self.predictions_correct / self.predictions_total
            self.logger.info(f"ML Prediction Accuracy: {accuracy:.1%} ({self.predictions_correct}/{self.predictions_total})")
    
    def get_accuracy(self) -> float:
        """Get current prediction accuracy"""
        if self.predictions_total == 0:
            return 0.5
        return self.predictions_correct / self.predictions_total


# Global instance
ml_predictor = MLPredictor()
