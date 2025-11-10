#!/usr/bin/env python3
"""
Test Order Flow and Sentiment Analysis
"""
import asyncio
from orderflow_analyzer import OrderFlowAnalyzer
from sentiment_analyzer import SentimentAnalyzer
from lighter_client import get_client
from config import settings
from logger import get_logger

logger = get_logger()


async def test_orderflow():
    """Test order flow analysis"""
    logger.info("=" * 60)
    logger.info("Testing Order Flow Analysis")
    logger.info("=" * 60)
    
    analyzer = OrderFlowAnalyzer()
    
    try:
        signal = await analyzer.get_combined_orderflow_signal(
            market_id=settings.trading_market_id
        )
        
        if signal:
            logger.info(f"Signal: {signal.signal.upper()}")
            logger.info(f"Strength: {signal.strength:.2f}")
            logger.info(f"Reason: {signal.reason}")
            logger.info(f"\nMetrics:")
            for key, value in signal.metrics.items():
                if isinstance(value, float):
                    logger.info(f"  {key}: {value:.4f}")
                else:
                    logger.info(f"  {key}: {value}")
        else:
            logger.warning("No order flow signal generated")
    
    except Exception as e:
        logger.error(f"Order flow test failed: {e}")


async def test_sentiment():
    """Test sentiment analysis"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Sentiment Analysis")
    logger.info("=" * 60)
    
    analyzer = SentimentAnalyzer()
    
    try:
        # Extract symbol from trading symbol
        symbol = settings.trading_symbol.split('-')[0]
        logger.info(f"Analyzing sentiment for: {symbol}")
        
        signal = await analyzer.get_combined_sentiment(symbol)
        
        if signal:
            logger.info(f"\nSentiment: {signal.sentiment.upper()}")
            logger.info(f"Score: {signal.score:.2f} (-1 to +1)")
            logger.info(f"Confidence: {signal.confidence:.2f}")
            logger.info(f"Reason: {signal.reason}")
            logger.info(f"\nSources:")
            for source in signal.sources:
                logger.info(f"  • {source}")
        else:
            logger.warning("No sentiment signal generated")
        
        await analyzer.close()
    
    except Exception as e:
        logger.error(f"Sentiment test failed: {e}")


async def test_fear_greed():
    """Test Fear & Greed Index specifically"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Fear & Greed Index")
    logger.info("=" * 60)
    
    analyzer = SentimentAnalyzer()
    
    try:
        fng = await analyzer.get_fear_greed_index()
        
        value = fng.get('value', 50)
        classification = fng.get('classification', 'Neutral')
        
        logger.info(f"Fear & Greed Index: {value}/100")
        logger.info(f"Classification: {classification}")
        
        if value < 25:
            logger.info("🟢 Extreme Fear - Potential buying opportunity!")
        elif value < 45:
            logger.info("🟡 Fear - Market cautious")
        elif value < 55:
            logger.info("⚪ Neutral - Balanced market")
        elif value < 75:
            logger.info("🟡 Greed - Market optimistic")
        else:
            logger.info("🔴 Extreme Greed - Potential selling opportunity!")
        
        await analyzer.close()
    
    except Exception as e:
        logger.error(f"Fear & Greed test failed: {e}")


async def main():
    """Run all tests"""
    logger.info("Testing New Trading Strategies\n")
    
    await test_orderflow()
    await test_sentiment()
    await test_fear_greed()
    
    logger.info("\n" + "=" * 60)
    logger.info("Testing Complete!")
    logger.info("=" * 60)
    logger.info("\nNext steps:")
    logger.info("1. Review the signals above")
    logger.info("2. Run 'python main.py' to start trading with these strategies")
    logger.info("3. Check STRATEGY_GUIDE.md for detailed documentation")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}")
