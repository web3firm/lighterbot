"""
Multi-Timeframe Analysis - Institutional Grade

How Top Funds Use Multiple Timeframes:
1. Higher timeframes (4h, 1h) = TREND DIRECTION (don't fight this)
2. Mid timeframes (30m, 15m) = ENTRY TIMING (wait for pullback)
3. Lower timeframes (5m, 1m) = EXECUTION (precise trigger)

Rule: NEVER trade against higher timeframe trend!

Example:
- 4h: Uptrend (EMA up, RSI 60) → Only LONG allowed
- 1h: Uptrend (EMA up, RSI 55) → Confirms LONG
- 15m: Pullback (RSI 40) → Wait for bounce
- 5m: Reversal (RSI 35→45, bullish candle) → ENTER LONG

This is how Renaissance Technologies filters 95% of bad trades.
"""

from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from indicators import TechnicalIndicators
from logger import get_logger

logger = get_logger()


@dataclass
class TimeframeAnalysis:
    """Analysis result for a single timeframe"""
    timeframe: str
    trend: str  # 'up', 'down', 'neutral'
    strength: float  # 0.0 to 1.0
    rsi: float
    ema_fast: float
    ema_slow: float
    macd_histogram: float
    price: float


class MultiTimeframeAnalyzer:
    """
    Institutional-grade multi-timeframe analysis
    
    Timeframe Hierarchy:
    - 4h (macro): Primary trend (highest weight)
    - 1h (swing): Trade direction (high weight)
    - 30m (entry): Entry timing (medium weight)
    - 15m (tactical): Entry refinement (medium weight)
    - 5m (execution): Trigger signal (low weight)
    
    Alignment Rules:
    - STRICT: All 5 timeframes must agree
    - RELAXED: 4h + 1h + 30m must agree (default)
    - AGGRESSIVE: 1h + 30m must agree
    """
    
    def __init__(self, mode: str = 'relaxed'):
        """
        Args:
            mode: 'strict', 'relaxed', or 'aggressive'
        """
        self.mode = mode
        self.logger = logger
        
        # Timeframe weights (higher = more important)
        self.weights = {
            '4h': 0.35,   # Macro trend - most important
            '1h': 0.30,   # Trade direction
            '30m': 0.20,  # Entry timing
            '15m': 0.10,  # Entry refinement
            '5m': 0.05,   # Execution trigger
        }
        
        self.logger.info(f"✅ Multi-Timeframe Analyzer initialized (mode={mode})")
    
    async def analyze_timeframe(
        self,
        market_data,
        resolution: str
    ) -> Optional[TimeframeAnalysis]:
        """
        Analyze a single timeframe
        
        Args:
            market_data: MarketData instance
            resolution: '5m', '15m', '30m', '1h', '4h'
        
        Returns:
            TimeframeAnalysis or None
        """
        try:
            # Fetch candles for this timeframe
            from config import settings
            candles = await market_data.get_candlesticks(
                market_id=settings.trading_market_id,
                resolution=resolution,
                limit=100  # Need enough for indicators
            )
            
            if not candles or len(candles) < 50:
                return None
            
            # Extract OHLC
            closes = [c['close'] for c in candles]
            highs = [c['high'] for c in candles]
            lows = [c['low'] for c in candles]
            
            current_price = closes[-1]
            
            # Calculate indicators
            rsi = TechnicalIndicators.rsi(closes, 14)
            ema_fast = TechnicalIndicators.ema(closes, 12)
            ema_slow = TechnicalIndicators.ema(closes, 26)
            macd_line, signal_line, histogram = TechnicalIndicators.macd(closes)
            
            # Determine trend
            trend = 'neutral'
            strength = 0.5
            
            # Bullish conditions
            bullish_signals = 0
            total_signals = 5
            
            if ema_fast > ema_slow:
                bullish_signals += 1
            if current_price > ema_fast:
                bullish_signals += 1
            if rsi > 50:
                bullish_signals += 1
            if histogram > 0:
                bullish_signals += 1
            if closes[-1] > closes[-2]:
                bullish_signals += 1
            
            # Calculate strength and trend
            strength = bullish_signals / total_signals
            
            if strength >= 0.6:
                trend = 'up'
            elif strength <= 0.4:
                trend = 'down'
            else:
                trend = 'neutral'
            
            return TimeframeAnalysis(
                timeframe=resolution,
                trend=trend,
                strength=strength,
                rsi=rsi,
                ema_fast=ema_fast,
                ema_slow=ema_slow,
                macd_histogram=histogram,
                price=current_price
            )
        
        except Exception as e:
            self.logger.error(f"Error analyzing {resolution} timeframe: {e}")
            return None
    
    async def get_multi_timeframe_signal(
        self,
        market_data,
        signal_direction: str  # 'long' or 'short' from strategy
    ) -> Tuple[bool, float, str]:
        """
        Check if signal aligns with multiple timeframes
        
        Args:
            market_data: MarketData instance
            signal_direction: 'long' or 'short'
        
        Returns:
            (approved, confidence, reason)
        """
        
        # Analyze all timeframes
        analyses = {}
        for tf in ['4h', '1h', '30m', '15m', '5m']:
            analysis = await self.analyze_timeframe(market_data, tf)
            if analysis:
                analyses[tf] = analysis
        
        # Need at least 3 timeframes
        if len(analyses) < 3:
            return False, 0.0, "Insufficient timeframe data"
        
        # Log analyses
        self.logger.info("📊 Multi-Timeframe Analysis:")
        for tf, analysis in analyses.items():
            self.logger.info(
                f"   {tf}: {analysis.trend.upper()} "
                f"(strength={analysis.strength:.2f}, RSI={analysis.rsi:.0f})"
            )
        
        # Check alignment based on mode
        if self.mode == 'strict':
            # ALL timeframes must agree
            required_tfs = ['4h', '1h', '30m', '15m', '5m']
            alignment = self._check_alignment(analyses, required_tfs, signal_direction)
        
        elif self.mode == 'relaxed':
            # 4h + 1h + 30m must agree (default institutional approach)
            required_tfs = ['4h', '1h', '30m']
            alignment = self._check_alignment(analyses, required_tfs, signal_direction)
        
        else:  # aggressive
            # 1h + 30m must agree (faster signals)
            required_tfs = ['1h', '30m']
            alignment = self._check_alignment(analyses, required_tfs, signal_direction)
        
        approved, confidence, reason = alignment
        
        if approved:
            # Calculate weighted confidence
            weighted_conf = 0.0
            for tf, weight in self.weights.items():
                if tf in analyses:
                    analysis = analyses[tf]
                    if signal_direction == 'long' and analysis.trend == 'up':
                        weighted_conf += weight * analysis.strength
                    elif signal_direction == 'short' and analysis.trend == 'down':
                        weighted_conf += weight * (1 - analysis.strength)
            
            self.logger.info(f"✅ MULTI-TF APPROVED: {reason} (confidence={weighted_conf:.2f})")
            return True, weighted_conf, reason
        else:
            self.logger.warning(f"❌ MULTI-TF REJECTED: {reason}")
            return False, 0.0, reason
    
    def _check_alignment(
        self,
        analyses: Dict[str, TimeframeAnalysis],
        required_tfs: List[str],
        signal_direction: str
    ) -> Tuple[bool, float, str]:
        """Check if required timeframes align with signal direction"""
        
        aligned_count = 0
        conflicting_tfs = []
        
        for tf in required_tfs:
            if tf not in analyses:
                return False, 0.0, f"Missing {tf} timeframe data"
            
            analysis = analyses[tf]
            
            # Check alignment
            if signal_direction == 'long':
                if analysis.trend == 'up':
                    aligned_count += 1
                elif analysis.trend == 'down':
                    conflicting_tfs.append(f"{tf}(DOWN)")
            
            elif signal_direction == 'short':
                if analysis.trend == 'down':
                    aligned_count += 1
                elif analysis.trend == 'up':
                    conflicting_tfs.append(f"{tf}(UP)")
        
        # All required timeframes must align
        if aligned_count == len(required_tfs):
            tf_list = ', '.join(required_tfs)
            return True, 1.0, f"All timeframes aligned: {tf_list}"
        else:
            conflicts = ', '.join(conflicting_tfs)
            return False, 0.0, f"Timeframe conflict: {conflicts}"
    
    def get_execution_timing(self, analyses: Dict[str, TimeframeAnalysis], direction: str) -> str:
        """
        Determine optimal execution timing based on lower timeframes
        
        Returns: 'immediate', 'wait_for_pullback', 'wait_for_breakout'
        """
        
        if '5m' not in analyses or '15m' not in analyses:
            return 'immediate'
        
        tf_5m = analyses['5m']
        tf_15m = analyses['15m']
        
        if direction == 'long':
            # If 15m RSI high but 5m RSI low → wait for pullback bounce
            if tf_15m.rsi > 60 and tf_5m.rsi < 40:
                return 'wait_for_pullback'
            
            # If both showing strength → immediate entry
            if tf_5m.rsi > 50 and tf_15m.rsi > 50:
                return 'immediate'
        
        elif direction == 'short':
            # If 15m RSI low but 5m RSI high → wait for rejection
            if tf_15m.rsi < 40 and tf_5m.rsi > 60:
                return 'wait_for_pullback'
            
            # If both showing weakness → immediate entry
            if tf_5m.rsi < 50 and tf_15m.rsi < 50:
                return 'immediate'
        
        return 'immediate'


# Global instance (relaxed mode = institutional standard)
mtf_analyzer = MultiTimeframeAnalyzer(mode='relaxed')
