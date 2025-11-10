"""
Order Flow Analysis - Analyze order book and trade flow
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
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
    Analyzes order book depth, trade flow, and market microstructure
    
    Features:
    - Bid/Ask imbalance detection
    - Large order identification (whale activity)
    - Trade flow analysis (aggressive buy vs sell)
    - Order book depth analysis
    """
    
    def __init__(self):
        self.recent_trades = []
        self.max_trade_history = 100
    
    async def analyze_order_book(self, market_id: int = 0) -> OrderFlowSignal:
        """
        Analyze order book for buy/sell pressure
        
        Returns:
            OrderFlowSignal with analysis
        """
        try:
            client = await get_client()
            
            # Get order book
            order_books_response = await client.order_api.order_books(market_id=market_id)
            
            if not order_books_response or not hasattr(order_books_response, 'order_books'):
                return OrderFlowSignal("neutral", 0.0, "No order book data", {})
            
            order_books = order_books_response.order_books
            if not order_books:
                return OrderFlowSignal("neutral", 0.0, "Empty order book", {})
            
            order_book = order_books[0]
            
            # Calculate bid/ask metrics
            bids = getattr(order_book, 'bids', [])
            asks = getattr(order_book, 'asks', [])
            
            if not bids or not asks:
                return OrderFlowSignal("neutral", 0.0, "Incomplete order book", {})
            
            # Calculate total bid/ask volume
            total_bid_volume = sum(float(bid.size) for bid in bids[:10])  # Top 10 levels
            total_ask_volume = sum(float(ask.size) for ask in asks[:10])
            
            # Calculate bid/ask imbalance
            total_volume = total_bid_volume + total_ask_volume
            if total_volume == 0:
                return OrderFlowSignal("neutral", 0.0, "No volume", {})
            
            bid_ratio = total_bid_volume / total_volume
            ask_ratio = total_ask_volume / total_volume
            imbalance = bid_ratio - ask_ratio  # -1 to +1
            
            # Check for large orders (whales)
            avg_bid_size = total_bid_volume / len(bids[:10])
            avg_ask_size = total_ask_volume / len(asks[:10])
            
            large_bids = [b for b in bids[:10] if float(b.size) > avg_bid_size * 3]
            large_asks = [a for a in asks[:10] if float(a.size) > avg_ask_size * 3]
            
            # Calculate spread
            best_bid = float(bids[0].price) if bids else 0
            best_ask = float(asks[0].price) if asks else 0
            spread_bps = ((best_ask - best_bid) / best_bid * 10000) if best_bid > 0 else 0
            
            # Determine signal
            if imbalance > 0.2:  # More bids than asks
                signal = "bullish"
                strength = min(1.0, abs(imbalance) * 2)
                reason = f"Strong bid pressure: {bid_ratio:.1%} bids vs {ask_ratio:.1%} asks"
            elif imbalance < -0.2:  # More asks than bids
                signal = "bearish"
                strength = min(1.0, abs(imbalance) * 2)
                reason = f"Strong ask pressure: {ask_ratio:.1%} asks vs {bid_ratio:.1%} bids"
            else:
                signal = "neutral"
                strength = 0.3
                reason = f"Balanced order book: {bid_ratio:.1%} bids, {ask_ratio:.1%} asks"
            
            # Whale detection
            if len(large_bids) > len(large_asks) * 2:
                reason += f" + {len(large_bids)} large buy walls"
                strength = min(1.0, strength + 0.2)
            elif len(large_asks) > len(large_bids) * 2:
                reason += f" + {len(large_asks)} large sell walls"
                strength = min(1.0, strength + 0.2)
            
            metrics = {
                "bid_volume": total_bid_volume,
                "ask_volume": total_ask_volume,
                "imbalance": imbalance,
                "spread_bps": spread_bps,
                "large_bids": len(large_bids),
                "large_asks": len(large_asks),
                "best_bid": best_bid,
                "best_ask": best_ask
            }
            
            return OrderFlowSignal(signal, strength, reason, metrics)
        
        except Exception as e:
            logger.error(f"Error analyzing order book: {e}")
            return OrderFlowSignal("neutral", 0.0, f"Error: {e}", {})
    
    async def analyze_recent_trades(self, market_id: int = 0, limit: int = 50) -> OrderFlowSignal:
        """
        Analyze recent trades for aggressive buying/selling
        
        Aggressive buyers = market orders hitting asks (bullish)
        Aggressive sellers = market orders hitting bids (bearish)
        """
        try:
            client = await get_client()
            
            # Get recent trades
            trades_response = await client.order_api.recent_trades(
                market_id=market_id,
                limit=limit
            )
            
            if not trades_response or not hasattr(trades_response, 'trades'):
                return OrderFlowSignal("neutral", 0.0, "No trade data", {})
            
            trades = trades_response.trades
            if not trades:
                return OrderFlowSignal("neutral", 0.0, "No recent trades", {})
            
            # Analyze trade direction (taker side)
            buy_volume = 0.0
            sell_volume = 0.0
            
            for trade in trades:
                size = float(getattr(trade, 'size', 0))
                side = getattr(trade, 'side', 'unknown')
                
                # Taker side indicates aggressor
                if side.lower() == 'buy':
                    buy_volume += size  # Aggressive buyer hit the ask
                elif side.lower() == 'sell':
                    sell_volume += size  # Aggressive seller hit the bid
            
            total_volume = buy_volume + sell_volume
            if total_volume == 0:
                return OrderFlowSignal("neutral", 0.0, "No volume in trades", {})
            
            buy_ratio = buy_volume / total_volume
            sell_ratio = sell_volume / total_volume
            flow_imbalance = buy_ratio - sell_ratio
            
            # Calculate recent price momentum
            if len(trades) >= 2:
                first_price = float(getattr(trades[-1], 'price', 0))
                last_price = float(getattr(trades[0], 'price', 0))
                price_change_pct = ((last_price - first_price) / first_price * 100) if first_price > 0 else 0
            else:
                price_change_pct = 0
            
            # Determine signal
            if flow_imbalance > 0.15 and price_change_pct > 0:
                signal = "bullish"
                strength = min(1.0, flow_imbalance * 3)
                reason = f"Aggressive buying: {buy_ratio:.1%} buy volume, price +{price_change_pct:.2f}%"
            elif flow_imbalance < -0.15 and price_change_pct < 0:
                signal = "bearish"
                strength = min(1.0, abs(flow_imbalance) * 3)
                reason = f"Aggressive selling: {sell_ratio:.1%} sell volume, price {price_change_pct:.2f}%"
            else:
                signal = "neutral"
                strength = 0.3
                reason = f"Mixed flow: {buy_ratio:.1%} buys, {sell_ratio:.1%} sells"
            
            metrics = {
                "buy_volume": buy_volume,
                "sell_volume": sell_volume,
                "flow_imbalance": flow_imbalance,
                "price_change_pct": price_change_pct,
                "trade_count": len(trades)
            }
            
            return OrderFlowSignal(signal, strength, reason, metrics)
        
        except Exception as e:
            logger.error(f"Error analyzing trades: {e}")
            return OrderFlowSignal("neutral", 0.0, f"Error: {e}", {})
    
    async def get_combined_orderflow_signal(self, market_id: int = 0) -> OrderFlowSignal:
        """
        Combine order book and trade flow analysis
        
        Returns:
            Combined signal with higher confidence
        """
        try:
            # Analyze both order book and trade flow
            book_signal = await self.analyze_order_book(market_id)
            trade_signal = await self.analyze_recent_trades(market_id)
            
            # Combine signals
            if book_signal.signal == trade_signal.signal:
                # Both agree - high confidence
                combined_signal = book_signal.signal
                combined_strength = (book_signal.strength + trade_signal.strength) / 2
                combined_reason = f"Order book: {book_signal.reason} | Trade flow: {trade_signal.reason}"
            elif book_signal.signal == "neutral":
                # Use trade flow signal
                combined_signal = trade_signal.signal
                combined_strength = trade_signal.strength * 0.7
                combined_reason = f"Trade flow dominant: {trade_signal.reason}"
            elif trade_signal.signal == "neutral":
                # Use order book signal
                combined_signal = book_signal.signal
                combined_strength = book_signal.strength * 0.7
                combined_reason = f"Order book dominant: {book_signal.reason}"
            else:
                # Conflicting signals - reduce confidence
                combined_signal = "neutral"
                combined_strength = 0.3
                combined_reason = f"Conflicting: Book={book_signal.signal}, Flow={trade_signal.signal}"
            
            # Combine metrics
            combined_metrics = {**book_signal.metrics, **trade_signal.metrics}
            
            return OrderFlowSignal(combined_signal, combined_strength, combined_reason, combined_metrics)
        
        except Exception as e:
            logger.error(f"Error in combined order flow analysis: {e}")
            return OrderFlowSignal("neutral", 0.0, f"Error: {e}", {})
