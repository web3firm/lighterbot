"""
Win Rate Performance Tracker

Tracks all trades and calculates actual win rate to validate 80%+ target
"""

import json
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path

from logger import logger


@dataclass
class TradeRecord:
    """Record of a single trade"""
    id: str  # Unique trade ID
    timestamp: datetime
    market_id: int
    symbol: str
    direction: str  # "long" or "short"
    entry_price: float
    exit_price: Optional[float] = None
    size: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    confidence: float = 0.0  # Expected win rate
    
    # Exit details
    exit_timestamp: Optional[datetime] = None
    exit_reason: Optional[str] = None  # "take_profit", "stop_loss", "trailing_stop", "manual"
    
    # Performance
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    is_winner: Optional[bool] = None
    holding_time_minutes: Optional[int] = None
    
    # Analysis
    reasons: List[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.reasons is None:
            self.reasons = []
        if self.warnings is None:
            self.warnings = []


class WinRateTracker:
    """
    Track trade performance and calculate win rate
    
    Automatically saves trades to JSON for persistent tracking
    """
    
    def __init__(self, data_file: str = "trade_history.json"):
        self.data_file = Path(data_file)
        self.trades: Dict[str, TradeRecord] = {}
        self.load_history()
    
    def load_history(self):
        """Load trade history from file"""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    
                for trade_data in data:
                    # Convert string timestamps back to datetime
                    trade_data['timestamp'] = datetime.fromisoformat(trade_data['timestamp'])
                    if trade_data.get('exit_timestamp'):
                        trade_data['exit_timestamp'] = datetime.fromisoformat(trade_data['exit_timestamp'])
                    
                    trade = TradeRecord(**trade_data)
                    self.trades[trade.id] = trade
                
                logger.info(f"Loaded {len(self.trades)} trades from history")
            
            except Exception as e:
                logger.error(f"Error loading trade history: {e}")
    
    def save_history(self):
        """Save trade history to file"""
        try:
            trades_list = []
            for trade in self.trades.values():
                trade_dict = asdict(trade)
                # Convert datetime to string for JSON
                trade_dict['timestamp'] = trade.timestamp.isoformat()
                if trade.exit_timestamp:
                    trade_dict['exit_timestamp'] = trade.exit_timestamp.isoformat()
                trades_list.append(trade_dict)
            
            with open(self.data_file, 'w') as f:
                json.dump(trades_list, f, indent=2)
            
            logger.debug(f"Saved {len(trades_list)} trades to history")
        
        except Exception as e:
            logger.error(f"Error saving trade history: {e}")
    
    def open_trade(
        self,
        trade_id: str,
        market_id: int,
        symbol: str,
        direction: str,
        entry_price: float,
        size: float,
        stop_loss: float,
        take_profit: float,
        confidence: float,
        reasons: List[str],
        warnings: List[str]
    ) -> TradeRecord:
        """Record a new trade opening"""
        
        trade = TradeRecord(
            id=trade_id,
            timestamp=datetime.now(),
            market_id=market_id,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            size=size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            reasons=reasons,
            warnings=warnings
        )
        
        self.trades[trade_id] = trade
        self.save_history()
        
        logger.info(f"📝 Recorded trade open: {trade_id} ({direction} {symbol} @ ${entry_price:.2f})")
        
        return trade
    
    def close_trade(
        self,
        trade_id: str,
        exit_price: float,
        exit_reason: str
    ) -> Optional[TradeRecord]:
        """Record a trade closing"""
        
        trade = self.trades.get(trade_id)
        if not trade:
            logger.warning(f"Trade {trade_id} not found in history")
            return None
        
        # Update exit details
        trade.exit_timestamp = datetime.now()
        trade.exit_price = exit_price
        trade.exit_reason = exit_reason
        
        # Calculate PnL
        if trade.direction == "long":
            trade.pnl = (exit_price - trade.entry_price) * trade.size
            trade.pnl_percent = ((exit_price - trade.entry_price) / trade.entry_price) * 100
        else:  # short
            trade.pnl = (trade.entry_price - exit_price) * trade.size
            trade.pnl_percent = ((trade.entry_price - exit_price) / trade.entry_price) * 100
        
        # Determine if winner
        trade.is_winner = trade.pnl > 0
        
        # Calculate holding time
        if trade.exit_timestamp and trade.timestamp:
            holding_time = trade.exit_timestamp - trade.timestamp
            trade.holding_time_minutes = int(holding_time.total_seconds() / 60)
        
        self.save_history()
        
        result = "WIN ✅" if trade.is_winner else "LOSS ❌"
        logger.info(f"📝 Recorded trade close: {trade_id} - {result} (PnL: ${trade.pnl:.2f}, {trade.pnl_percent:+.2f}%)")
        
        return trade
    
    def get_statistics(self, days: Optional[int] = None) -> Dict:
        """
        Calculate comprehensive statistics
        
        Args:
            days: Only include trades from last N days (None = all time)
        """
        
        # Filter trades
        closed_trades = [t for t in self.trades.values() if t.exit_price is not None]
        
        if days:
            cutoff = datetime.now() - timedelta(days=days)
            closed_trades = [t for t in closed_trades if t.timestamp >= cutoff]
        
        if not closed_trades:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "message": "No closed trades yet"
            }
        
        # Calculate statistics
        total_trades = len(closed_trades)
        winners = [t for t in closed_trades if t.is_winner]
        losers = [t for t in closed_trades if not t.is_winner]
        
        win_rate = (len(winners) / total_trades) * 100
        
        total_pnl = sum(t.pnl for t in closed_trades)
        avg_win = sum(t.pnl for t in winners) / len(winners) if winners else 0
        avg_loss = sum(t.pnl for t in losers) / len(losers) if losers else 0
        
        # Risk/Reward ratio
        profit_factor = abs(sum(t.pnl for t in winners) / sum(t.pnl for t in losers)) if losers and sum(t.pnl for t in losers) != 0 else 0
        
        # Average holding time
        avg_holding_time = sum(t.holding_time_minutes for t in closed_trades if t.holding_time_minutes) / total_trades
        
        # Group by exit reason
        exit_reasons = {}
        for trade in closed_trades:
            reason = trade.exit_reason or "unknown"
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
        
        # Best and worst trades
        best_trade = max(closed_trades, key=lambda t: t.pnl)
        worst_trade = min(closed_trades, key=lambda t: t.pnl)
        
        return {
            "total_trades": total_trades,
            "winners": len(winners),
            "losers": len(losers),
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "avg_holding_time_minutes": avg_holding_time,
            "exit_reasons": exit_reasons,
            "best_trade": {
                "id": best_trade.id,
                "pnl": best_trade.pnl,
                "pnl_percent": best_trade.pnl_percent
            },
            "worst_trade": {
                "id": worst_trade.id,
                "pnl": worst_trade.pnl,
                "pnl_percent": worst_trade.pnl_percent
            },
            "target_achieved": win_rate >= 80.0
        }
    
    def print_statistics(self, days: Optional[int] = None):
        """Print formatted statistics"""
        
        stats = self.get_statistics(days)
        
        if stats["total_trades"] == 0:
            print("\n📊 No trades recorded yet\n")
            return
        
        period = f"Last {days} days" if days else "All time"
        
        print("\n" + "="*60)
        print(f"📊 WIN RATE STATISTICS - {period}")
        print("="*60)
        
        # Win rate (highlighted if above 80%)
        win_rate = stats["win_rate"]
        if win_rate >= 80:
            print(f"🎯 WIN RATE: {win_rate:.1f}% ✅ (TARGET ACHIEVED!)")
        elif win_rate >= 70:
            print(f"📈 WIN RATE: {win_rate:.1f}% (Close to target)")
        else:
            print(f"📉 WIN RATE: {win_rate:.1f}% (Below target)")
        
        print(f"\nTrades:")
        print(f"  Total: {stats['total_trades']}")
        print(f"  Winners: {stats['winners']} ({stats['winners']/stats['total_trades']*100:.1f}%)")
        print(f"  Losers: {stats['losers']} ({stats['losers']/stats['total_trades']*100:.1f}%)")
        
        print(f"\nProfitability:")
        pnl_color = "🟢" if stats['total_pnl'] > 0 else "🔴"
        print(f"  Total PnL: {pnl_color} ${stats['total_pnl']:.2f}")
        print(f"  Avg Win: ${stats['avg_win']:.2f}")
        print(f"  Avg Loss: ${stats['avg_loss']:.2f}")
        print(f"  Profit Factor: {stats['profit_factor']:.2f}")
        
        print(f"\nPerformance:")
        print(f"  Avg Holding Time: {stats['avg_holding_time_minutes']:.0f} minutes")
        
        print(f"\nExit Reasons:")
        for reason, count in stats['exit_reasons'].items():
            print(f"  {reason}: {count}")
        
        print(f"\nBest Trade:")
        print(f"  {stats['best_trade']['id']}: ${stats['best_trade']['pnl']:.2f} ({stats['best_trade']['pnl_percent']:+.2f}%)")
        
        print(f"\nWorst Trade:")
        print(f"  {stats['worst_trade']['id']}: ${stats['worst_trade']['pnl']:.2f} ({stats['worst_trade']['pnl_percent']:+.2f}%)")
        
        print("="*60 + "\n")
    
    def get_open_trades(self) -> List[TradeRecord]:
        """Get all currently open trades"""
        return [t for t in self.trades.values() if t.exit_price is None]
    
    def get_closed_trades(self, limit: int = 10) -> List[TradeRecord]:
        """Get recent closed trades"""
        closed = [t for t in self.trades.values() if t.exit_price is not None]
        closed.sort(key=lambda t: t.exit_timestamp, reverse=True)
        return closed[:limit]


# Global instance
win_rate_tracker = WinRateTracker()
