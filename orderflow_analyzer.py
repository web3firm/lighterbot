"""
Order Flow Analysis - Analyze trade flow and market microstructure
Uses REAL-TIME TRADE DATA from Lighter (order books are empty, so we use trades)
"""
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import statistics
from lighter_client import get_client
from logger import logger


@dataclass
class OrderFlowSignal:
    """Order flow analysis signal"""
    signal: str  # "bullish", "bearish", "neutral"
    strength: float  # 0.0 to 1.0
    reason: str
    metrics: Dict[str, float]


class OrderFlowAnalyzer:
    """
    Analyzes real-time trade flow and market microstructure
    
    Features (all based on RECENT TRADES):
    - Buy/Sell pressure from actual executed trades
    - Whale trade detection (large volume trades)
    - Aggressive buyer vs seller analysis  
    - Trade size and frequency patterns
    - Price momentum from trade flow
    
    NOTE: Lighter's order books are currently empty, so we analyze
    the trade feed which gives us REAL executed transactions.
    """
    
    def __init__(self):
        self.recent_trades_cache = []
        self.cache_timestamp = None
        self.cache_duration = 10  # 10 seconds
    
    async def get_recent_trades(self, market_id: int = 0, limit: int = 100) -> List[Dict]:
        """
        Get recent trades with caching
        
        Returns list of trades with keys:
        - size: trade size
        - price: trade price
        - is_maker_ask: True if maker was selling (taker bought = BULLISH)
        - usd_amount: USD value
        - timestamp: trade timestamp
        """
        try:
            # Check cache
            if (self.cache_timestamp and 
                datetime.now() - self.cache_timestamp < timedelta(seconds=self.cache_duration) and
                self.recent_trades_cache):
                return self.recent_trades_cache
            
            client = await get_client()
            trades = await client.get_recent_trades(market_id=market_id, limit=limit)
            
            self.recent_trades_cache = trades
            self.cache_timestamp = datetime.now()
            
            return trades
        
        except Exception as e:
            logger.error(f"Error fetching recent trades: {e}")
            return []
    
    async def analyze_trade_flow(self, market_id: int = 0, lookback: int = 30) -> OrderFlowSignal:
        """
        Analyze recent trade flow for buy/sell pressure
        
        OPTIMIZED FOR 1M SCALPING: 30 trades instead of 50 (faster signals)
        
        Key insight:
        - is_maker_ask = True means maker had a SELL order, taker BOUGHT (BULLISH)
        - is_maker_ask = False means maker had a BUY order, taker SOLD (BEARISH)
        
        We're looking at WHO was the AGGRESSOR (taker)
        """
        try:
            trades = await self.get_recent_trades(market_id, lookback)
            
            if not trades or len(trades) < 5:
                return OrderFlowSignal("neutral", 0.0, "Not enough trade data", {})
            
            # Analyze trade flow
            buy_volume = 0.0  # Aggressive market buys (bullish)
            sell_volume = 0.0  # Aggressive market sells (bearish)
            buy_count = 0
            sell_count = 0
            total_volume = 0.0
            
            trade_sizes = []
            prices = []
            buy_usd = 0.0
            sell_usd = 0.0
            
            for trade in trades:
                size = float(trade.get('size', 0))
                price = float(trade.get('price', 0))
                is_maker_ask = trade.get('is_maker_ask', False)
                usd_amount = float(trade.get('usd_amount', 0))
                
                if size == 0 or price == 0:
                    continue
                
                trade_sizes.append(size)
                prices.append(price)
                total_volume += size
                
                if is_maker_ask:
                    # Taker bought (aggressive buying = bullish)
                    buy_volume += size
                    buy_count += 1
                    buy_usd += usd_amount
                else:
                    # Taker sold (aggressive selling = bearish)
                    sell_volume += size
                    sell_count += 1
                    sell_usd += usd_amount
            
            if total_volume == 0:
                return OrderFlowSignal("neutral", 0.0, "No volume in trades", {})
            
            # Calculate metrics
            buy_ratio = buy_volume / total_volume
            sell_ratio = sell_volume / total_volume
            
            # Detect large trades (whales)
            avg_trade_size = statistics.mean(trade_sizes) if trade_sizes else 0
            std_trade_size = statistics.stdev(trade_sizes) if len(trade_sizes) > 1 else 0
            whale_threshold = avg_trade_size + (2 * std_trade_size) if std_trade_size > 0 else avg_trade_size * 3
            
            whale_buys = []
            whale_sells = []
            for trade in trades:
                size = float(trade.get('size', 0))
                if size > whale_threshold:
                    if trade.get('is_maker_ask', False):
                        whale_buys.append(size)
                    else:
                        whale_sells.append(size)
            
            # Calculate price momentum
            if len(prices) >= 2:
                recent_prices = prices[:min(10, len(prices)//2)]
                old_prices = prices[max(1, len(prices)//2):]
                price_momentum = (statistics.mean(recent_prices) - statistics.mean(old_prices)) / statistics.mean(old_prices) * 100
            else:
                price_momentum = 0
            
            # Trade velocity (trades per minute)
            if trades:
                time_range = (max(t.get('timestamp', 0) for t in trades) - 
                            min(t.get('timestamp', 0) for t in trades)) / 1000 / 60  # minutes
                trade_velocity = len(trades) / time_range if time_range > 0 else 0
            else:
                trade_velocity = 0
            
            # Determine signal
            if buy_ratio > 0.6:  # 60%+ aggressive buying
                strength = min(1.0, buy_ratio * 1.3)
                signal = "bullish"
                reason = f"{buy_ratio*100:.0f}% aggressive buying (${buy_usd:.0f})"
                if len(whale_buys) > 0:
                    reason += f" + {len(whale_buys)} whale buy(s)"
                if price_momentum > 0.1:
                    reason += f" + price momentum"
            
            elif sell_ratio > 0.6:  # 60%+ aggressive selling
                strength = min(1.0, sell_ratio * 1.3)
                signal = "bearish"
                reason = f"{sell_ratio*100:.0f}% aggressive selling (${sell_usd:.0f})"
                if len(whale_sells) > 0:
                    reason += f" + {len(whale_sells)} whale sell(s)"
                if price_momentum < -0.1:
                    reason += f" + negative momentum"
            
            else:
                strength = 0.4
                signal = "neutral"
                reason = f"Balanced: {buy_ratio*100:.0f}% buy / {sell_ratio*100:.0f}% sell"
            
            metrics = {
                "buy_volume": buy_volume,
                "sell_volume": sell_volume,
                "buy_ratio": buy_ratio,
                "sell_ratio": sell_ratio,
                "total_volume": total_volume,
                "buy_count": buy_count,
                "sell_count": sell_count,
                "buy_usd": buy_usd,
                "sell_usd": sell_usd,
                "avg_trade_size": avg_trade_size,
                "whale_buys": len(whale_buys),
                "whale_sells": len(whale_sells),
                "price_momentum_pct": price_momentum,
                "trade_count": len(trades),
                "trade_velocity": trade_velocity
            }
            
            return OrderFlowSignal(signal, strength, reason, metrics)
        
        except Exception as e:
            logger.error(f"Error analyzing trade flow: {e}")
            return OrderFlowSignal("neutral", 0.0, f"Error: {e}", {})
    
    async def get_combined_orderflow_signal(self, market_id: int = 0) -> OrderFlowSignal:
        """
        Get orderflow signal based on recent trades
        
        Since order books are empty on Lighter, we use only trade flow analysis
        This gives us REAL executed trades showing actual market behavior
        """
        try:
            # Analyze trade flow (this is the most reliable data we have)
            return await self.analyze_trade_flow(market_id, lookback=30)  # 30 trades for 1m scalping
        
        except Exception as e:
            logger.error(f"Error in orderflow analysis: {e}")
            return OrderFlowSignal("neutral", 0.0, f"Error: {e}", {})
