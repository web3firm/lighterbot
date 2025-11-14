"""
Strategy Performance Tracker

Tracks P&L, win rate, and trade count per strategy to identify winners/losers.
Automatically disables underperforming strategies.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
from logger import get_logger

logger = get_logger()


@dataclass
class StrategyStats:
    """Performance statistics for a single strategy"""
    name: str
    trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    consecutive_losses: int = 0
    last_trade_time: Optional[datetime] = None
    enabled: bool = True
    
    @property
    def win_rate(self) -> float:
        """Calculate win rate percentage"""
        if self.trades == 0:
            return 0.0
        return (self.wins / self.trades) * 100
    
    @property
    def profit_factor(self) -> float:
        """Calculate profit factor (total wins / total losses)"""
        total_wins = self.wins * abs(self.avg_win) if self.avg_win else 0
        total_losses = self.losses * abs(self.avg_loss) if self.avg_loss else 0
        if total_losses == 0:
            return float('inf') if total_wins > 0 else 0
        return total_wins / total_losses
    
    @property
    def avg_pnl(self) -> float:
        """Average P&L per trade"""
        if self.trades == 0:
            return 0.0
        return self.total_pnl / self.trades


class StrategyPerformanceTracker:
    """
    Track and analyze performance of each trading strategy
    
    Features:
    - Win rate per strategy
    - P&L per strategy
    - Auto-disable strategies with <40% win rate after 10+ trades
    - Detect which strategies work best in current market
    """
    
    def __init__(self, persistence_file: str = "strategy_stats.json"):
        self.stats: Dict[str, StrategyStats] = {}
        self.persistence_file = persistence_file
        self.logger = logger
        
        # Auto-disable thresholds
        self.min_trades_for_eval = 10  # Need 10 trades before evaluating
        self.min_win_rate = 40.0  # Disable if <40% win rate
        self.max_consecutive_losses = 5  # Disable after 5 straight losses
        
        self._load_stats()
    
    def record_trade(
        self,
        strategy_name: str,
        pnl_percent: float,
        entry_price: float,
        exit_price: float
    ):
        """Record a completed trade for a strategy"""
        
        # Initialize strategy if new
        if strategy_name not in self.stats:
            self.stats[strategy_name] = StrategyStats(name=strategy_name)
        
        stats = self.stats[strategy_name]
        
        # Update counts
        stats.trades += 1
        stats.last_trade_time = datetime.now()
        
        # Win or loss
        is_win = pnl_percent > 0
        if is_win:
            stats.wins += 1
            stats.consecutive_losses = 0
            stats.avg_win = ((stats.avg_win * (stats.wins - 1)) + pnl_percent) / stats.wins
            if pnl_percent > stats.best_trade:
                stats.best_trade = pnl_percent
        else:
            stats.losses += 1
            stats.consecutive_losses += 1
            stats.avg_loss = ((stats.avg_loss * (stats.losses - 1)) + pnl_percent) / stats.losses
            if pnl_percent < stats.worst_trade:
                stats.worst_trade = pnl_percent
        
        # Update total P&L
        stats.total_pnl += pnl_percent
        
        # Log trade
        result = "WIN" if is_win else "LOSS"
        self.logger.info(
            f"📊 {strategy_name}: {result} {pnl_percent:+.2f}% | "
            f"WR: {stats.win_rate:.1f}% ({stats.wins}/{stats.trades}) | "
            f"Total: {stats.total_pnl:+.2f}%"
        )
        
        # Check if strategy should be disabled
        self._evaluate_strategy(strategy_name)
        
        # Persist stats
        self._save_stats()
    
    def _evaluate_strategy(self, strategy_name: str):
        """Evaluate if strategy should be disabled"""
        stats = self.stats[strategy_name]
        
        # Not enough trades yet
        if stats.trades < self.min_trades_for_eval:
            return
        
        # Disable if win rate too low
        if stats.win_rate < self.min_win_rate:
            if stats.enabled:
                stats.enabled = False
                self.logger.error(
                    f"❌ DISABLED {strategy_name}: Win rate {stats.win_rate:.1f}% < {self.min_win_rate}% "
                    f"after {stats.trades} trades"
                )
        
        # Disable if too many consecutive losses
        if stats.consecutive_losses >= self.max_consecutive_losses:
            if stats.enabled:
                stats.enabled = False
                self.logger.error(
                    f"❌ DISABLED {strategy_name}: {stats.consecutive_losses} consecutive losses"
                )
        
        # Re-enable if recovered (3 wins in a row and win rate >45%)
        if not stats.enabled and stats.consecutive_losses == 0 and stats.win_rate > 45.0:
            stats.enabled = True
            self.logger.info(
                f"✅ RE-ENABLED {strategy_name}: Win rate recovered to {stats.win_rate:.1f}%"
            )
    
    def is_strategy_enabled(self, strategy_name: str) -> bool:
        """Check if strategy is enabled"""
        if strategy_name not in self.stats:
            return True  # New strategies start enabled
        return self.stats[strategy_name].enabled
    
    def get_best_strategies(self, top_n: int = 3) -> List[str]:
        """Get top N strategies by profit factor"""
        if not self.stats:
            return []
        
        # Filter strategies with enough trades
        qualified = [
            (name, stats) 
            for name, stats in self.stats.items() 
            if stats.trades >= self.min_trades_for_eval and stats.enabled
        ]
        
        # Sort by profit factor
        qualified.sort(key=lambda x: x[1].profit_factor, reverse=True)
        
        return [name for name, _ in qualified[:top_n]]
    
    def get_summary(self) -> str:
        """Get formatted summary of all strategies"""
        if not self.stats:
            return "No strategy data yet"
        
        lines = ["\n" + "=" * 80]
        lines.append("📊 STRATEGY PERFORMANCE REPORT")
        lines.append("=" * 80)
        
        # Sort by total P&L
        sorted_strategies = sorted(
            self.stats.items(),
            key=lambda x: x[1].total_pnl,
            reverse=True
        )
        
        for name, stats in sorted_strategies:
            status = "✅" if stats.enabled else "❌"
            lines.append(f"\n{status} {name}")
            lines.append(f"   Trades: {stats.trades} | Wins: {stats.wins} | Losses: {stats.losses}")
            lines.append(f"   Win Rate: {stats.win_rate:.1f}%")
            lines.append(f"   Total P&L: {stats.total_pnl:+.2f}%")
            lines.append(f"   Avg Win: {stats.avg_win:+.2f}% | Avg Loss: {stats.avg_loss:+.2f}%")
            lines.append(f"   Profit Factor: {stats.profit_factor:.2f}")
            lines.append(f"   Best: {stats.best_trade:+.2f}% | Worst: {stats.worst_trade:+.2f}%")
            
            if stats.consecutive_losses > 0:
                lines.append(f"   ⚠️ Consecutive Losses: {stats.consecutive_losses}")
        
        lines.append("\n" + "=" * 80)
        
        # Best strategies
        best = self.get_best_strategies(3)
        if best:
            lines.append(f"🏆 Top Strategies: {', '.join(best)}")
            lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def _save_stats(self):
        """Persist statistics to file"""
        try:
            data = {
                name: {
                    'trades': stats.trades,
                    'wins': stats.wins,
                    'losses': stats.losses,
                    'total_pnl': stats.total_pnl,
                    'avg_win': stats.avg_win,
                    'avg_loss': stats.avg_loss,
                    'best_trade': stats.best_trade,
                    'worst_trade': stats.worst_trade,
                    'consecutive_losses': stats.consecutive_losses,
                    'enabled': stats.enabled,
                }
                for name, stats in self.stats.items()
            }
            
            with open(self.persistence_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving strategy stats: {e}")
    
    def _load_stats(self):
        """Load statistics from file"""
        try:
            with open(self.persistence_file, 'r') as f:
                data = json.load(f)
            
            for name, stats_dict in data.items():
                self.stats[name] = StrategyStats(
                    name=name,
                    trades=stats_dict['trades'],
                    wins=stats_dict['wins'],
                    losses=stats_dict['losses'],
                    total_pnl=stats_dict['total_pnl'],
                    avg_win=stats_dict['avg_win'],
                    avg_loss=stats_dict['avg_loss'],
                    best_trade=stats_dict['best_trade'],
                    worst_trade=stats_dict['worst_trade'],
                    consecutive_losses=stats_dict['consecutive_losses'],
                    enabled=stats_dict.get('enabled', True),
                )
            
            self.logger.info(f"Loaded stats for {len(self.stats)} strategies")
        except FileNotFoundError:
            self.logger.info("No existing strategy stats found, starting fresh")
        except Exception as e:
            self.logger.error(f"Error loading strategy stats: {e}")


# Global instance
strategy_tracker = StrategyPerformanceTracker()
