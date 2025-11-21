"""
Database Manager - PostgreSQL connection and operations
Handles all database interactions with AsyncPG
"""

import logging
import asyncpg
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages PostgreSQL database connections and operations
    Uses AsyncPG for high-performance async queries
    """
    
    def __init__(self):
        """Initialize database manager"""
        self.pool: Optional[asyncpg.Pool] = None
        self.db_url = os.getenv('DATABASE_URL', '')
        
        if not self.db_url:
            logger.warning("⚠️  DATABASE_URL not set, database features disabled")
    
    async def connect(self):
        """Create database connection pool"""
        try:
            if not self.db_url:
                return False
            
            self.pool = await asyncpg.create_pool(
                self.db_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            
            logger.info("✅ Database connected")
            
            # Initialize schema
            await self._initialize_schema()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("📴 Database disconnected")
    
    async def _initialize_schema(self):
        """Initialize database schema"""
        try:
            # Read schema file
            schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
            
            # Execute schema
            async with self.pool.acquire() as conn:
                await conn.execute(schema_sql)
            
            logger.info("✅ Database schema initialized")
            
        except Exception as e:
            logger.error(f"❌ Schema initialization failed: {e}")
    
    # ============ TRADES TABLE ============
    
    async def insert_trade(self, trade_data: Dict[str, Any]) -> bool:
        """Insert new trade record"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO trades (
                        trade_id, symbol, strategy, side, entry_price, size, leverage,
                        entry_time, indicators, ml_prediction, ml_confidence
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """, 
                    trade_data['trade_id'],
                    trade_data['symbol'],
                    trade_data['strategy'],
                    trade_data['side'],
                    trade_data['entry_price'],
                    trade_data['size'],
                    trade_data['leverage'],
                    datetime.fromisoformat(trade_data['entry_time']),
                    trade_data.get('indicators'),
                    trade_data.get('ml_prediction'),
                    trade_data.get('ml_confidence')
                )
            
            logger.info(f"💾 Trade saved: {trade_data['trade_id']}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to insert trade: {e}")
            return False
    
    async def update_trade_exit(self, trade_id: str, exit_data: Dict[str, Any]) -> bool:
        """Update trade with exit information"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE trades SET
                        exit_price = $1,
                        exit_time = $2,
                        pnl_usd = $3,
                        pnl_pct = $4,
                        fees_usd = $5,
                        duration_seconds = $6,
                        exit_reason = $7
                    WHERE trade_id = $8
                """,
                    exit_data['exit_price'],
                    datetime.fromisoformat(exit_data['exit_time']),
                    exit_data['pnl_usd'],
                    exit_data['pnl_pct'],
                    exit_data.get('fees_usd', 0),
                    exit_data.get('duration_seconds', 0),
                    exit_data.get('exit_reason', 'Unknown'),
                    trade_id
                )
            
            logger.info(f"💾 Trade updated: {trade_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update trade: {e}")
            return False
    
    async def get_recent_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent trades"""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM trades
                    ORDER BY entry_time DESC
                    LIMIT $1
                """, limit)
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"❌ Failed to get recent trades: {e}")
            return []
    
    # ============ SIGNALS TABLE ============
    
    async def insert_signal(self, signal_data: Dict[str, Any]) -> bool:
        """Insert trading signal"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO signals (
                        signal_id, symbol, strategy, side, entry_price, sl_price, tp_price,
                        size, leverage, signal_strength, confidence, indicators, was_taken,
                        rejection_reason
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """,
                    signal_data['signal_id'],
                    signal_data['symbol'],
                    signal_data['strategy'],
                    signal_data['side'],
                    signal_data['entry_price'],
                    signal_data['sl_price'],
                    signal_data['tp_price'],
                    signal_data['size'],
                    signal_data['leverage'],
                    signal_data['signal_strength'],
                    signal_data['confidence'],
                    signal_data.get('indicators'),
                    signal_data.get('was_taken', False),
                    signal_data.get('rejection_reason')
                )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to insert signal: {e}")
            return False
    
    # ============ POSITIONS TABLE ============
    
    async def upsert_position(self, position_data: Dict[str, Any]) -> bool:
        """Insert or update position"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO positions (
                        position_id, symbol, side, entry_price, current_price, size,
                        leverage, unrealized_pnl, liquidation_price, status, opened_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (position_id) DO UPDATE SET
                        current_price = EXCLUDED.current_price,
                        unrealized_pnl = EXCLUDED.unrealized_pnl,
                        status = EXCLUDED.status,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    position_data['position_id'],
                    position_data['symbol'],
                    position_data['side'],
                    position_data['entry_price'],
                    position_data['current_price'],
                    position_data['size'],
                    position_data['leverage'],
                    position_data['unrealized_pnl'],
                    position_data.get('liquidation_price'),
                    position_data['status'],
                    datetime.fromisoformat(position_data['opened_at'])
                )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to upsert position: {e}")
            return False
    
    # ============ PERFORMANCE METRICS TABLE ============
    
    async def upsert_daily_metrics(self, date: str, metrics: Dict[str, Any]) -> bool:
        """Insert or update daily performance metrics"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO performance_metrics (
                        date, starting_balance, ending_balance, daily_pnl, daily_pnl_pct,
                        total_trades, winning_trades, losing_trades, win_rate,
                        avg_win, avg_loss, largest_win, largest_loss, total_fees,
                        sharpe_ratio, max_drawdown_pct
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                    ON CONFLICT (date) DO UPDATE SET
                        ending_balance = EXCLUDED.ending_balance,
                        daily_pnl = EXCLUDED.daily_pnl,
                        daily_pnl_pct = EXCLUDED.daily_pnl_pct,
                        total_trades = EXCLUDED.total_trades,
                        winning_trades = EXCLUDED.winning_trades,
                        losing_trades = EXCLUDED.losing_trades,
                        win_rate = EXCLUDED.win_rate,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    date,
                    metrics['starting_balance'],
                    metrics['ending_balance'],
                    metrics['daily_pnl'],
                    metrics['daily_pnl_pct'],
                    metrics['total_trades'],
                    metrics['winning_trades'],
                    metrics['losing_trades'],
                    metrics['win_rate'],
                    metrics.get('avg_win'),
                    metrics.get('avg_loss'),
                    metrics.get('largest_win'),
                    metrics.get('largest_loss'),
                    metrics.get('total_fees'),
                    metrics.get('sharpe_ratio'),
                    metrics.get('max_drawdown_pct')
                )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to upsert daily metrics: {e}")
            return False
    
    # ============ BOT STATE TABLE ============
    
    async def set_state(self, key: str, value: Any) -> bool:
        """Set bot state value"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO bot_state (key, value)
                    VALUES ($1, $2)
                    ON CONFLICT (key) DO UPDATE SET
                        value = EXCLUDED.value,
                        updated_at = CURRENT_TIMESTAMP
                """, key, value)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to set state: {e}")
            return False
    
    async def get_state(self, key: str) -> Optional[Any]:
        """Get bot state value"""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT value FROM bot_state WHERE key = $1
                """, key)
            
            return row['value'] if row else None
            
        except Exception as e:
            logger.error(f"❌ Failed to get state: {e}")
            return None


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Get global database manager instance"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
