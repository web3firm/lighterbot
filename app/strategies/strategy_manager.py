"""
Strategy Manager - Orchestrates all trading strategies
Manages signal generation, ML integration, and strategy allocation
"""

import logging
from typing import Dict, Any, Optional, List
import asyncio

logger = logging.getLogger(__name__)


class StrategyManager:
    """
    Manages all trading strategies and coordinates signal generation
    Integrates with ML auto-trainer for V2 predictions
    """
    
    def __init__(self, symbol: str, config: Optional[Dict[str, Any]] = None, auto_trainer=None):
        """
        Initialize strategy manager
        
        Args:
            symbol: Trading symbol
            config: Optional configuration
            auto_trainer: ML auto-trainer instance for V2 predictions
        """
        self.symbol = symbol
        self.config = config or {}
        self.auto_trainer = auto_trainer
        
        # Initialize strategies
        self.strategies = []
        self._initialize_strategies()
        
        # Strategy allocation from environment
        import os
        swing_alloc = float(os.getenv('SWING_ALLOCATION', '70')) / 100.0
        scalp_alloc = float(os.getenv('SCALPING_ALLOCATION', '30')) / 100.0
        self.strategy_weights = {
            'swing_trader': swing_alloc,
            'scalping_2pct': scalp_alloc
        }
        
        # Statistics
        self.total_signals = 0
        self.signals_by_strategy: Dict[str, int] = {}
        
        logger.info(f"🎯 Strategy Manager initialized for {symbol}")
        logger.info(f"   Active strategies: {len(self.strategies)}")
        logger.info(f"   ML Phase: {'V2 (Active)' if self.auto_trainer and self.auto_trainer.is_ml_active() else 'V1 (Collection)'}")
    
    def _initialize_strategies(self):
        """Initialize all active strategies"""
        try:
            # Import active strategies
            from app.strategies.rule_based.swing_trader import SwingTradingStrategy
            from app.strategies.rule_based.scalping_2pct import ScalpingStrategy2Pct
            
            # Initialize strategies based on allocation
            self.strategies.append(SwingTradingStrategy(self.symbol, self.config))
            self.strategies.append(ScalpingStrategy2Pct(self.symbol, self.config))
            
            logger.info(f"✅ Initialized {len(self.strategies)} strategies")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize strategies: {e}")
    
    async def generate_signal(self, market_data: Dict[str, Any],
                             account_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate trading signal from all strategies
        
        Args:
            market_data: Market data with indicators
            account_state: Current account state
            
        Returns:
            Best signal or None
        """
        try:
            # Generate signals from all strategies
            signals = []
            
            for strategy in self.strategies:
                try:
                    signal = await strategy.generate_signal(market_data, account_state)
                    if signal:
                        signals.append(signal)
                except Exception as e:
                    logger.error(f"Error in {strategy.name}: {e}")
            
            if not signals:
                return None
            
            # Select best signal
            best_signal = self._select_best_signal(signals, market_data)
            
            if best_signal:
                # Enhance with ML prediction if V2 active
                if self.auto_trainer and self.auto_trainer.is_ml_active():
                    best_signal = await self._enhance_with_ml(best_signal, market_data)
                
                # Update statistics
                self.total_signals += 1
                strategy_name = best_signal['strategy']
                self.signals_by_strategy[strategy_name] = self.signals_by_strategy.get(strategy_name, 0) + 1
                
                logger.info(f"✅ Signal selected: {best_signal['strategy']} - {best_signal['side'].upper()}")
                
                return best_signal
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error generating signal: {e}")
            return None
    
    def _select_best_signal(self, signals: List[Dict[str, Any]], 
                           market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Select best signal from multiple candidates
        
        Args:
            signals: List of signals
            market_data: Market data
            
        Returns:
            Best signal
        """
        if not signals:
            return None
        
        # Score signals
        scored_signals = []
        
        for signal in signals:
            score = signal.get('confidence', 0.5)
            
            # Apply strategy weight
            strategy_name = signal.get('strategy', '')
            weight = self.strategy_weights.get(strategy_name, 0.5)
            score *= weight
            
            # Apply signal strength
            strength = signal.get('signal_strength', 5)
            max_strength = signal.get('max_strength', 10)
            score *= (strength / max_strength)
            
            scored_signals.append((score, signal))
        
        # Return highest scored signal
        scored_signals.sort(key=lambda x: x[0], reverse=True)
        return scored_signals[0][1]
    
    async def _enhance_with_ml(self, signal: Dict[str, Any],
                               market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance signal with ML prediction (V2 phase)
        
        Args:
            signal: Original signal
            market_data: Market data
            
        Returns:
            Enhanced signal with ML confidence
        """
        try:
            # Prepare features for ML
            indicators = signal.get('indicators', {})
            features = {
                'rsi': indicators.get('rsi', 50),
                'macd': indicators.get('macd', 0),
                'ema_fast': indicators.get('ema_fast', 0),
                'ema_slow': indicators.get('ema_slow', 0),
                'adx': indicators.get('adx', 25),
                'atr': indicators.get('atr', 1.0),
                'bb_position': indicators.get('bb_position', 0.5),
                'volume_ratio': indicators.get('volume_ratio', 1.0),
                'price_change_1h': market_data.get('price_change_1h', 0),
                'price_change_4h': market_data.get('price_change_4h', 0),
                'price_change_24h': market_data.get('price_change_24h', 0),
                'signal_strength': signal.get('signal_strength', 5),
                'strategy': 0  # Will be mapped by auto_trainer
            }
            
            # Get ML prediction
            prediction = self.auto_trainer.predict(features)
            
            if prediction:
                # Enhance signal with ML confidence
                ml_confidence = prediction.get('probability', 0.5)
                original_confidence = signal.get('confidence', 0.5)
                
                # Combine confidences (weighted average)
                combined_confidence = (original_confidence * 0.6) + (ml_confidence * 0.4)
                
                signal['ml_prediction'] = prediction.get('prediction')
                signal['ml_probability'] = ml_confidence
                signal['ml_confidence'] = prediction.get('confidence')
                signal['original_confidence'] = original_confidence
                signal['confidence'] = combined_confidence
                signal['ml_phase'] = 'V2'
                
                logger.info(f"🔮 ML Enhancement:")
                logger.info(f"   Prediction: {'PROFITABLE' if prediction.get('prediction') == 1 else 'UNPROFITABLE'}")
                logger.info(f"   ML Confidence: {ml_confidence:.2%}")
                logger.info(f"   Combined: {combined_confidence:.2%}")
            
            return signal
            
        except Exception as e:
            logger.error(f"❌ Error enhancing with ML: {e}")
            return signal
    
    def get_stats(self) -> Dict[str, Any]:
        """Get strategy manager statistics"""
        strategy_stats = {}
        for strategy in self.strategies:
            strategy_stats[strategy.name] = strategy.get_stats()
        
        return {
            'total_signals': self.total_signals,
            'signals_by_strategy': self.signals_by_strategy,
            'strategy_weights': self.strategy_weights,
            'active_strategies': len(self.strategies),
            'ml_active': self.auto_trainer.is_ml_active() if self.auto_trainer else False,
            'strategies': strategy_stats
        }


if __name__ == "__main__":
    # Test strategy manager
    async def test():
        manager = StrategyManager('BTC-USD')
        
        market_data = {
            'mark_price': 50000,
            'indicators': {
                'rsi': 32,
                'ema_fast': 50100,
                'ema_slow': 49900,
                'macd': {'histogram': 0.5},
                'adx': 28,
                'volume_ratio': 1.3
            }
        }
        
        account_state = {
            'account_value': 1000
        }
        
        signal = await manager.generate_signal(market_data, account_state)
        print(f"Signal: {signal}")
        
        stats = manager.get_stats()
        print(f"Stats: {stats}")
    
    asyncio.run(test())
