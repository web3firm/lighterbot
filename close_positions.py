"""
Quick script to close all open positions
"""
import asyncio
from lighter_client import get_client, close_client
from logger import get_logger

logger = get_logger()

async def close_all_positions():
    """Close all open positions"""
    try:
        client = await get_client()
        
        # Get all open positions
        positions = await client.get_positions()
        
        if not positions:
            logger.info("No open positions to close")
            return
        
        logger.info(f"Found {len(positions)} open positions")
        
        for i, pos in enumerate(positions):
            logger.info(f"Position {i}: {pos}")
            
            # Parse position fields
            size_float = float(pos.get('position', 0))
            sign = int(pos.get('sign', 1))
            entry_price_float = float(pos.get('avg_entry_price', 0))
            
            # Calculate actual signed size
            actual_size = size_float * sign
            
            logger.info(f"Parsed - Size: {actual_size} (sign={sign}), Entry: ${entry_price_float}")
            
            if abs(actual_size) < 0.001:
                logger.warning("Position size too small, skipping")
                continue
            
            # Close position with market order (opposite side)
            is_ask = actual_size > 0  # If long, sell (ask). If short, buy (bid)
            size_abs = abs(actual_size)
            
            # Convert to base amount (ETH has 4 decimals)
            from utils import market_metadata
            base_decimals = market_metadata[0].base_decimals
            base_amount = int(size_abs * (10 ** base_decimals))
            
            # Get current price for worst price
            current_price = await client.get_market_price(0)
            # Allow 2% slippage
            if is_ask:
                worst_price = current_price * 0.98
            else:
                worst_price = current_price * 1.02
            
            price_decimals = market_metadata[0].price_decimals
            avg_execution_price = int(worst_price * (10 ** price_decimals))
            
            logger.info(f"Placing {'SELL' if is_ask else 'BUY'} order for {size_abs} ETH ({base_amount} base units)")
            
            # Place market order to close
            order = await client.create_market_order(
                market_index=0,  # ETH-PERP
                client_order_index=0,
                base_amount=base_amount,
                avg_execution_price=avg_execution_price,
                is_ask=is_ask,
                reduce_only=True  # Reduce-only to close position
            )
            
            if order:
                logger.info(f"✅ Position closed successfully")
            else:
                logger.error(f"❌ Failed to close position")
        
        logger.info("All positions closed")
        
    except Exception as e:
        logger.error(f"Error closing positions: {e}")
    finally:
        await close_client()

if __name__ == "__main__":
    asyncio.run(close_all_positions())
