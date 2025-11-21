"""
Analytics - Database analytics and performance queries
Provides win rate, PnL stats, and performance analysis
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from app.database.db_manager import get_db_manager

logger = logging.getLogger(__name__)


class Analytics:
    """
    Analytics engine for trade performance and statistics
    """
    
    def __init__(self, db_manager=None):
        """Initialize analytics"""
        self.db = db_manager if db_manager else get_db_manager()
    
    async def get_win_rate(self, days: int = 30) -> Dict[str, Any]:
        """
        Calculate win rate statistics
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Win rate statistics
        """
        try:
            if not self.db.pool:
                return {}
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT
                        COUNT(*) as total_trades,
                        COUNT(*) FILTER (WHERE pnl_usd > 0) as winning_trades,
                        COUNT(*) FILTER (WHERE pnl_usd < 0) as losing_trades,
                        COUNT(*) FILTER (WHERE pnl_usd = 0) as breakeven_trades,
                        AVG(CASE WHEN pnl_usd > 0 THEN pnl_usd END) as avg_win,
                        AVG(CASE WHEN pnl_usd < 0 THEN pnl_usd END) as avg_loss,
                        MAX(pnl_usd) as largest_win,
                        MIN(pnl_usd) as largest_loss,
                        SUM(pnl_usd) as total_pnl,
                        AVG(pnl_pct) as avg_pnl_pct
                    FROM trades
                    WHERE exit_time > $1 AND exit_time IS NOT NULL
                """, cutoff_date)
            
            if row['total_trades'] == 0:
                return {'win_rate': 0, 'total_trades': 0}
            
            win_rate = (row['winning_trades'] / row['total_trades']) * 100 if row['total_trades'] > 0 else 0
            
            # Calculate profit factor
            total_wins = row['avg_win'] * row['winning_trades'] if row['avg_win'] else 0
            total_losses = abs(row['avg_loss'] * row['losing_trades']) if row['avg_loss'] else 0
            profit_factor = total_wins / total_losses if total_losses > 0 else 0
            
            return {
                'period_days': days,
                'total_trades': row['total_trades'],
                'winning_trades': row['winning_trades'],
                'losing_trades': row['losing_trades'],
                'breakeven_trades': row['breakeven_trades'],
                'win_rate': round(win_rate, 2),
                'avg_win': float(row['avg_win']) if row['avg_win'] else 0,
                'avg_loss': float(row['avg_loss']) if row['avg_loss'] else 0,
                'largest_win': float(row['largest_win']) if row['largest_win'] else 0,
                'largest_loss': float(row['largest_loss']) if row['largest_loss'] else 0,
                'total_pnl': float(row['total_pnl']) if row['total_pnl'] else 0,
                'avg_pnl_pct': float(row['avg_pnl_pct']) if row['avg_pnl_pct'] else 0,
                'profit_factor': round(profit_factor, 2)
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate win rate: {e}")
            return {}
    
    async def get_strategy_performance(self, days: int = 30) -> Dict[str, Any]:
        """Get performance breakdown by strategy"""
        try:
            if not self.db.pool:
                return {}
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            async with self.db.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT
                        strategy,
                        COUNT(*) as total_trades,
                        COUNT(*) FILTER (WHERE pnl_usd > 0) as winning_trades,
                        SUM(pnl_usd) as total_pnl,
                        AVG(pnl_pct) as avg_pnl_pct,
                        MAX(pnl_usd) as best_trade,
                        MIN(pnl_usd) as worst_trade
                    FROM trades
                    WHERE exit_time > $1 AND exit_time IS NOT NULL
                    GROUP BY strategy
                    ORDER BY total_pnl DESC
                """, cutoff_date)
            
            strategies = {}
            for row in rows:
                win_rate = (row['winning_trades'] / row['total_trades'] * 100) if row['total_trades'] > 0 else 0
                
                strategies[row['strategy']] = {
                    'total_trades': row['total_trades'],
                    'winning_trades': row['winning_trades'],
                    'win_rate': round(win_rate, 2),
                    'total_pnl': float(row['total_pnl']) if row['total_pnl'] else 0,
                    'avg_pnl_pct': float(row['avg_pnl_pct']) if row['avg_pnl_pct'] else 0,
                    'best_trade': float(row['best_trade']) if row['best_trade'] else 0,
                    'worst_trade': float(row['worst_trade']) if row['worst_trade'] else 0
                }
            
            return strategies
            
        except Exception as e:
            logger.error(f"❌ Failed to get strategy performance: {e}")
            return {}
    
    async def get_daily_performance(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily performance metrics"""
        try:
            if not self.db.pool:
                return []
            
            cutoff_date = (datetime.now() - timedelta(days=days)).date()
            
            async with self.db.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM performance_metrics
                    WHERE date >= $1
                    ORDER BY date DESC
                """, cutoff_date)
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"❌ Failed to get daily performance: {e}")
            return []
    
    async def get_ml_performance(self) -> Dict[str, Any]:
        """Get ML prediction performance"""
        try:
            if not self.db.pool:
                return {}
            
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT
                        COUNT(*) as total_predictions,
                        COUNT(*) FILTER (WHERE prediction = actual_outcome) as correct_predictions,
                        AVG(probability) as avg_confidence
                    FROM ml_predictions
                    WHERE actual_outcome IS NOT NULL
                """)
            
            if row['total_predictions'] == 0:
                return {'accuracy': 0, 'total_predictions': 0}
            
            accuracy = (row['correct_predictions'] / row['total_predictions'] * 100) if row['total_predictions'] > 0 else 0
            
            return {
                'total_predictions': row['total_predictions'],
                'correct_predictions': row['correct_predictions'],
                'accuracy': round(accuracy, 2),
                'avg_confidence': float(row['avg_confidence']) if row['avg_confidence'] else 0
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get ML performance: {e}")
            return {}
    
    async def get_drawdown_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get drawdown history"""
        try:
            if not self.db.pool:
                return []
            
            cutoff_date = (datetime.now() - timedelta(days=days)).date()
            
            async with self.db.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT date, ending_balance, max_drawdown_pct
                    FROM performance_metrics
                    WHERE date >= $1
                    ORDER BY date ASC
                """, cutoff_date)
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"❌ Failed to get drawdown history: {e}")
            return []
    
    async def get_recent_signals(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent trading signals"""
        try:
            if not self.db.pool:
                return []
            
            async with self.db.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM signals
                    ORDER BY created_at DESC
                    LIMIT $1
                """, limit)
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"❌ Failed to get recent signals: {e}")
            return []
    
    async def get_signal_acceptance_rate(self, days: int = 7) -> Dict[str, Any]:
        """Get signal acceptance/rejection statistics"""
        try:
            if not self.db.pool:
                return {}
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT
                        COUNT(*) as total_signals,
                        COUNT(*) FILTER (WHERE was_taken = TRUE) as accepted_signals,
                        COUNT(*) FILTER (WHERE was_taken = FALSE) as rejected_signals
                    FROM signals
                    WHERE created_at > $1
                """, cutoff_date)
            
            if row['total_signals'] == 0:
                return {'acceptance_rate': 0, 'total_signals': 0}
            
            acceptance_rate = (row['accepted_signals'] / row['total_signals'] * 100) if row['total_signals'] > 0 else 0
            
            return {
                'period_days': days,
                'total_signals': row['total_signals'],
                'accepted_signals': row['accepted_signals'],
                'rejected_signals': row['rejected_signals'],
                'acceptance_rate': round(acceptance_rate, 2)
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get signal acceptance rate: {e}")
            return {}
    
    async def get_comprehensive_report(self, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive analytics report"""
        try:
            win_rate_stats = await self.get_win_rate(days)
            strategy_perf = await self.get_strategy_performance(days)
            ml_perf = await self.get_ml_performance()
            signal_stats = await self.get_signal_acceptance_rate(days)
            
            return {
                'period_days': days,
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'win_rate': win_rate_stats,
                'strategy_performance': strategy_perf,
                'ml_performance': ml_perf,
                'signal_statistics': signal_stats
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to generate comprehensive report: {e}")
            return {}


# Global analytics instance
_analytics: Optional[Analytics] = None


def get_analytics() -> Analytics:
    """Get global analytics instance"""
    global _analytics
    if _analytics is None:
        _analytics = Analytics()
    return _analytics
