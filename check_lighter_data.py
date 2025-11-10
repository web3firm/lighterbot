#!/usr/bin/env python3
"""
Check available markets and data on Lighter
"""
import asyncio
from lighter_client import get_client
from logger import get_logger

logger = get_logger()


async def main():
    client = await get_client()
    
    logger.info("=" * 60)
    logger.info("Checking Lighter API Available Data")
    logger.info("=" * 60)
    
    # 1. Check order books
    logger.info("\n1. Checking Order Books (all markets)...")
    try:
        result = await client.order_api.order_books(market_id=255)
        if hasattr(result, 'order_books'):
            logger.info(f"Found {len(result.order_books)} markets with order books")
            for ob in result.order_books[:10]:
                market_id = getattr(ob, 'market_id', None)
                bids = getattr(ob, 'bids', [])
                asks = getattr(ob, 'asks', [])
                logger.info(f"  Market {market_id}: {len(bids)} bids, {len(asks)} asks")
        else:
            logger.warning("No order_books attribute in response")
    except Exception as e:
        logger.error(f"Error getting order books: {e}")
    
    # 2. Check exchange stats
    logger.info("\n2. Checking Exchange Stats...")
    try:
        stats = await client.order_api.exchange_stats()
        if hasattr(stats, 'markets'):
            logger.info(f"Found {len(stats.markets)} active markets:")
            for market in stats.markets[:15]:
                market_id = getattr(market, 'market_id', None)
                symbol = getattr(market, 'symbol', None)
                volume_24h = getattr(market, 'volume_24h', 0)
                last_price = getattr(market, 'last_price', 0)
                logger.info(f"  Market {market_id}: {symbol} | Price: ${last_price} | Vol: ${volume_24h}")
        else:
            logger.warning("No markets attribute in stats")
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
    
    # 3. Check order book details for specific market
    logger.info("\n3. Checking BTC-PERP Order Book Details (market_id=0)...")
    try:
        details = await client.order_api.order_book_details(market_id=0)
        logger.info(f"Order book details response: {type(details)}")
        if hasattr(details, 'bids'):
            logger.info(f"  Bids: {len(details.bids)}")
            if details.bids:
                logger.info(f"  Best bid: {details.bids[0]}")
        if hasattr(details, 'asks'):
            logger.info(f"  Asks: {len(details.asks)}")
            if details.asks:
                logger.info(f"  Best ask: {details.asks[0]}")
    except Exception as e:
        logger.error(f"Error getting order book details: {e}")
    
    # 4. Check recent trades
    logger.info("\n4. Checking Recent Trades (market_id=0)...")
    try:
        trades = await client.get_recent_trades(market_id=0, limit=10)
        logger.info(f"Found {len(trades)} recent trades")
        for i, trade in enumerate(trades[:5]):
            logger.info(f"  Trade {i+1}: {trade}")
    except Exception as e:
        logger.error(f"Error getting recent trades: {e}")
    
    # 5. Check candlesticks
    logger.info("\n5. Checking Candlestick Data (market_id=0)...")
    try:
        candles = await client.get_candlesticks(market_id=0, resolution="1h", limit=5)
        logger.info(f"Found {len(candles)} candles")
        for i, candle in enumerate(candles[:3]):
            logger.info(f"  Candle {i+1}: {candle}")
    except Exception as e:
        logger.error(f"Error getting candlesticks: {e}")
    
    # 6. Try different markets
    logger.info("\n6. Checking Other Popular Markets...")
    for market_id in [1, 2, 3, 4, 5]:
        try:
            details = await client.order_api.order_book_details(market_id=market_id)
            bids_count = len(getattr(details, 'bids', []))
            asks_count = len(getattr(details, 'asks', []))
            logger.info(f"  Market {market_id}: {bids_count} bids, {asks_count} asks")
        except Exception as e:
            logger.info(f"  Market {market_id}: Error - {e}")
    
    await client.close()
    
    logger.info("\n" + "=" * 60)
    logger.info("Data Check Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
