"""
ML Auto-Trainer - Automatic model training when trade count reaches threshold
Implements V1 (collection) → V2 (ML predictions) transition

V1 Phase: Collect 1000+ trades to PostgreSQL database
V2 Phase: Train RandomForest model and activate ML predictions
"""

import logging
import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os
import asyncpg

logger = logging.getLogger(__name__)


class AutoTrainer:
    """
    Automatically monitors trade count and trains ML models
    
    Phase 1 (V1): Collects trades until threshold reached
    Phase 2 (V2): Trains model and activates predictions
    """
    
    def __init__(self, db_url: Optional[str] = None, min_trades: int = 1000, retrain_interval: int = 86400):
        """
        Initialize auto-trainer
        
        Args:
            db_url: PostgreSQL database URL (required for V2)
            min_trades: Minimum trades before first training (default: 1000)
            retrain_interval: Seconds between retraining (default: 86400 = 24h)
        """
        self.db_url = db_url or os.getenv('DATABASE_URL')
        self.min_trades = min_trades
        self.retrain_interval = retrain_interval
        
        # Paths
        self.models_dir = Path("ml/models")
        self.dataset_dir = Path("data/model_dataset")
        
        # Ensure directories exist
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.dataset_dir.mkdir(parents=True, exist_ok=True)
        
        # State
        self.model_trained = False
        self.last_train_time: Optional[datetime] = None
        self.trade_count = 0
        
        # Load existing model if available
        self._load_existing_model()
        
        logger.info(f"🤖 ML Auto-Trainer initialized (PostgreSQL mode)")
        logger.info(f"   Min trades for training: {self.min_trades}")
        logger.info(f"   Retrain interval: {self.retrain_interval}s ({self.retrain_interval/3600:.1f}h)")
        logger.info(f"   Current phase: {'V2 (ML Active)' if self.model_trained else 'V1 (Collection)'}")
    
    def _load_existing_model(self):
        """Load existing model if available"""
        model_path = self.models_dir / "random_forest_model.joblib"
        
        if model_path.exists():
            try:
                self.model = joblib.load(model_path)
                self.model_trained = True
                
                # Load metadata
                metadata_path = self.models_dir / "model_metadata.json"
                if metadata_path.exists():
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                        self.last_train_time = datetime.fromisoformat(metadata.get('trained_at'))
                        self.trade_count = metadata.get('total_trades', 0)
                
                logger.info(f"✅ Loaded existing trained model")
                logger.info(f"   Trained at: {self.last_train_time}")
                logger.info(f"   Total trades: {self.trade_count}")
            except Exception as e:
                logger.error(f"❌ Failed to load existing model: {e}")
                self.model_trained = False
    
    async def check_and_train(self) -> Optional[Dict[str, Any]]:
        """
        Check if training is needed and train if threshold reached
        
        Returns:
            Dict with training results if completed, None otherwise
        """
        # Count total trades
        total_trades = self._count_trades()
        self.trade_count = total_trades
        
        logger.info(f"📊 Trade count: {total_trades}/{self.min_trades}")
        
        # Check if we need to train
        should_train = False
        
        if not self.model_trained and total_trades >= self.min_trades:
            logger.info(f"🚀 Reached {total_trades} trades - ACTIVATING ML TRAINING (V1 → V2 TRANSITION)")
            should_train = True
        elif self.model_trained and self.last_train_time:
            # Check if retrain interval passed
            time_since_train = (datetime.now(timezone.utc) - self.last_train_time).total_seconds()
            if time_since_train >= self.retrain_interval:
                logger.info(f"🔄 Retrain interval reached ({time_since_train/3600:.1f}h) - retraining model")
                should_train = True
        
        if should_train:
            success = await self.train_model()
            if success and self.metrics:
                return {
                    'trade_count': total_trades,
                    'accuracy': self.metrics.get('accuracy', 0.0),
                    'phase': 'V2 (Active)' if self.model_trained else 'V1 (Collection)'
                }
        
        return None
    
    def _count_trades(self) -> int:
        """Count completed trades in database (trades with exit_time)"""
        if not self.db_url:
            logger.warning("No database URL configured")
            return 0
        
        try:
            # Use sync connection for simple count
            import psycopg2
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM trades WHERE exit_time IS NOT NULL")
            total = cur.fetchone()[0]
            cur.close()
            conn.close()
            return total
        except Exception as e:
            logger.error(f"Error counting trades: {e}")
            return 0
    
    async def train_model(self) -> bool:
        """
        Train RandomForest model on collected trades
        
        Returns:
            True if training successful, False otherwise
        """
        try:
            logger.info("🧠 STARTING ML MODEL TRAINING...")
            logger.info("=" * 80)
            
            # Step 1: Load all trades
            logger.info("📁 Step 1: Loading trade data...")
            trades = self._load_all_trades()
            
            if len(trades) < self.min_trades:
                logger.warning(f"⚠️  Not enough trades for training: {len(trades)}/{self.min_trades}")
                return False
            
            logger.info(f"   Loaded {len(trades)} trades")
            
            # Step 2: Build dataset with features
            logger.info("🔧 Step 2: Building feature dataset...")
            df = await self._build_dataset(trades)
            logger.info(f"   Dataset shape: {df.shape}")
            logger.info(f"   Features: {list(df.columns)}")
            
            # Step 3: Prepare training data
            logger.info("🎯 Step 3: Preparing training data...")
            X, y = self._prepare_training_data(df)
            logger.info(f"   Features shape: {X.shape}")
            logger.info(f"   Labels shape: {y.shape}")
            logger.info(f"   Positive samples: {sum(y)} ({sum(y)/len(y)*100:.1f}%)")
            
            # Step 4: Train model
            logger.info("🤖 Step 4: Training RandomForest model...")
            model = await self._train_random_forest(X, y)
            
            # Step 5: Evaluate model
            logger.info("📊 Step 5: Evaluating model performance...")
            metrics = await self._evaluate_model(model, X, y)
            
            logger.info(f"   Accuracy: {metrics['accuracy']:.2%}")
            logger.info(f"   Precision: {metrics['precision']:.2%}")
            logger.info(f"   Recall: {metrics['recall']:.2%}")
            logger.info(f"   F1-Score: {metrics['f1']:.2%}")
            
            # Step 6: Save model
            logger.info("💾 Step 6: Saving trained model...")
            self._save_model(model, metrics)
            
            # Update state
            self.model = model
            self.model_trained = True
            self.last_train_time = datetime.now(timezone.utc)
            
            logger.info("=" * 80)
            logger.info("✅ ML MODEL TRAINING COMPLETE!")
            logger.info(f"🎉 V2 PHASE ACTIVATED - ML PREDICTIONS NOW AVAILABLE")
            logger.info("=" * 80)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Model training failed: {e}", exc_info=True)
            return False
    
    def _load_all_trades(self) -> List[Dict[str, Any]]:
        """Load all completed trades from database"""
        if not self.db_url:
            logger.warning("No database URL configured")
            return []
        
        try:
            import psycopg2
            import psycopg2.extras
            
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Query completed trades with all data
            cur.execute("""
                SELECT 
                    trade_id, symbol, strategy, side,
                    entry_price, exit_price, size, leverage,
                    entry_time, exit_time,
                    pnl_usd, pnl_pct,
                    indicators, ml_prediction, ml_confidence
                FROM trades 
                WHERE exit_time IS NOT NULL
                ORDER BY entry_time
            """)
            
            trades = []
            for row in cur.fetchall():
                trades.append(dict(row))
            
            cur.close()
            conn.close()
            
            logger.info(f"Loaded {len(trades)} completed trades from database")
            return trades
            
        except Exception as e:
            logger.error(f"Error loading trades: {e}")
            return []
    
    async def _build_dataset(self, trades: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Build feature dataset from completed trades
        
        Features extracted:
        - RSI, MACD, EMA, ADX, ATR
        - Volume ratio
        - Price changes (1h, 4h, 24h)
        - Bollinger band position
        - Signal strength
        
        Target: Trade outcome (profit/loss)
        """
        rows = []
        
        logger.info(f"   Processing {len(trades)} completed trades")
        
        for trade in trades:
            # Extract indicators (stored as JSONB in database)
            indicators = trade.get('indicators', {})
            if isinstance(indicators, str):
                indicators = json.loads(indicators)
            
            # Extract features
            row = {
                # Technical indicators
                'rsi': indicators.get('rsi', 50),
                'macd': indicators.get('macd', {}).get('histogram', 0) if isinstance(indicators.get('macd'), dict) else indicators.get('macd', 0),
                'ema_fast': indicators.get('ema_fast', 0),
                'ema_slow': indicators.get('ema_slow', 0),
                'adx': indicators.get('adx', 25),
                'atr': indicators.get('atr', 1.0),
                'bb_position': indicators.get('bb_position', 0.5),
                
                # Volume
                'volume_ratio': indicators.get('volume_ratio', 1.0),
                
                # Price changes
                'price_change_1h': indicators.get('price_change_1h', 0),
                'price_change_4h': indicators.get('price_change_4h', 0),
                'price_change_24h': indicators.get('price_change_24h', 0),
                
                # Signal info
                'signal_strength': indicators.get('signal_strength', 5),
                'strategy': trade.get('strategy', 'unknown'),
                'leverage': trade.get('leverage', 1),
                
                # Target: Did trade make profit?
                'profitable': 1 if trade.get('pnl_usd', 0) > 0 else 0,
                'pnl_pct': trade.get('pnl_pct', 0)
            }
            
            rows.append(row)
        
        df = pd.DataFrame(rows)
        
        if df.empty:
            logger.warning("⚠️  No trades available for training")
            return df
        
        logger.info(f"   Built {len(df)} trade samples")
        logger.info(f"   Profitable trades: {df['profitable'].sum()} ({df['profitable'].mean()*100:.1f}%)")
        
        # Convert strategy to numeric
        strategy_map = {'swing_trader': 0, 'scalping_2pct': 1, 'breakout': 2, 'mean_reversion': 3, 'volume_spike': 4}
        df['strategy'] = df['strategy'].map(strategy_map).fillna(0)
        
        return df
    
    def _prepare_training_data(self, df: pd.DataFrame):
        """Prepare X (features) and y (labels) for training"""
        # Features
        feature_columns = [
            'rsi', 'macd', 'ema_fast', 'ema_slow', 'adx', 'atr',
            'bb_position', 'volume_ratio', 'price_change_1h',
            'price_change_4h', 'price_change_24h', 'signal_strength', 'strategy'
        ]
        
        X = df[feature_columns].values
        y = df['profitable'].values
        
        return X, y
    
    async def _train_random_forest(self, X, y):
        """Train RandomForest classifier"""
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Train model
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=20,
            min_samples_leaf=10,
            random_state=42,
            n_jobs=-1
        )
        
        model.fit(X_train, y_train)
        
        # Store test set for evaluation
        self.X_test = X_test
        self.y_test = y_test
        
        return model
    
    async def _evaluate_model(self, model, X, y) -> Dict[str, float]:
        """Evaluate model performance"""
        # Predict on test set
        y_pred = model.predict(self.X_test)
        
        # Calculate metrics
        accuracy = accuracy_score(self.y_test, y_pred)
        
        # Get classification report
        report = classification_report(self.y_test, y_pred, output_dict=True, zero_division=0)
        
        metrics = {
            'accuracy': accuracy,
            'precision': report.get('1', {}).get('precision', 0),
            'recall': report.get('1', {}).get('recall', 0),
            'f1': report.get('1', {}).get('f1-score', 0)
        }
        
        return metrics
    
    def _save_model(self, model, metrics: Dict[str, float]):
        """Save trained model and metadata"""
        # Save model
        model_path = self.models_dir / "random_forest_model.joblib"
        joblib.dump(model, model_path)
        logger.info(f"   Saved model to {model_path}")
        
        # Save metadata
        metadata = {
            'trained_at': datetime.now(timezone.utc).isoformat(),
            'total_trades': self.trade_count,
            'model_type': 'RandomForestClassifier',
            'metrics': metrics,
            'min_trades_threshold': self.min_trades
        }
        
        metadata_path = self.models_dir / "model_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"   Saved metadata to {metadata_path}")
    
    def predict(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Make prediction using trained model
        
        Args:
            features: Dictionary with feature values
            
        Returns:
            Prediction dict with 'profitable' probability and 'confidence'
        """
        if not self.model_trained:
            return None
        
        try:
            # Prepare feature vector
            feature_vector = [
                features.get('rsi', 50),
                features.get('macd', 0),
                features.get('ema_fast', 0),
                features.get('ema_slow', 0),
                features.get('adx', 25),
                features.get('atr', 1.0),
                features.get('bb_position', 0.5),
                features.get('volume_ratio', 1.0),
                features.get('price_change_1h', 0),
                features.get('price_change_4h', 0),
                features.get('price_change_24h', 0),
                features.get('signal_strength', 0),
                features.get('strategy', 0)
            ]
            
            # Predict
            prediction = self.model.predict([feature_vector])[0]
            probability = self.model.predict_proba([feature_vector])[0]
            
            return {
                'prediction': int(prediction),
                'probability': float(probability[1]),  # Probability of profit
                'confidence': float(max(probability)),
                'phase': 'V2'
            }
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return None
    
    def is_ml_active(self) -> bool:
        """Check if ML predictions are active (V2 phase)"""
        return self.model_trained
    
    def get_status(self) -> Dict[str, Any]:
        """Get auto-trainer status"""
        return {
            'phase': 'V2 (ML Active)' if self.model_trained else 'V1 (Collection)',
            'model_trained': self.model_trained,
            'trade_count': self.trade_count,
            'min_trades': self.min_trades,
            'progress_pct': (self.trade_count / self.min_trades * 100) if not self.model_trained else 100,
            'last_train_time': self.last_train_time.isoformat() if self.last_train_time else None,
            'next_retrain_in': self.retrain_interval - (datetime.now(timezone.utc) - self.last_train_time).total_seconds() if self.last_train_time else None
        }


if __name__ == "__main__":
    # Test auto-trainer
    async def test():
        trainer = AutoTrainer(min_trades=10)  # Low threshold for testing
        
        print("\n📊 Status:")
        status = trainer.get_status()
        for key, value in status.items():
            print(f"   {key}: {value}")
        
        print("\n🔍 Checking if training needed...")
        await trainer.check_and_train()
    
    asyncio.run(test())
