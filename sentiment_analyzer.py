"""
News & Sentiment Analysis for Crypto Markets
"""
import aiohttp
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from logger import logger


@dataclass
class SentimentSignal:
    """Sentiment analysis signal"""
    sentiment: str  # "bullish", "bearish", "neutral"
    score: float  # -1.0 (very bearish) to +1.0 (very bullish)
    confidence: float  # 0.0 to 1.0
    reason: str
    sources: List[str]


class SentimentAnalyzer:
    """
    Analyzes crypto news and social sentiment
    
    Data sources:
    - CryptoCompare News API (free)
    - CoinGecko sentiment
    - Twitter/X trending topics
    - Fear & Greed Index
    """
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache = {}
        self.cache_duration = 300  # 5 minutes
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_fear_greed_index(self) -> Dict:
        """
        Get Crypto Fear & Greed Index
        
        0-25: Extreme Fear (bullish signal)
        25-45: Fear (slightly bullish)
        45-55: Neutral
        55-75: Greed (slightly bearish)
        75-100: Extreme Greed (bearish signal)
        """
        try:
            # Check cache
            cache_key = "fear_greed"
            if cache_key in self.cache:
                cached_time, cached_data = self.cache[cache_key]
                if datetime.now() - cached_time < timedelta(seconds=self.cache_duration):
                    return cached_data
            
            session = await self._get_session()
            url = "https://api.alternative.me/fng/?limit=1"
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data and 'data' in data and len(data['data']) > 0:
                        fng_data = data['data'][0]
                        value = int(fng_data.get('value', 50))
                        classification = fng_data.get('value_classification', 'Neutral')
                        
                        result = {
                            "value": value,
                            "classification": classification,
                            "timestamp": datetime.now()
                        }
                        
                        # Cache result
                        self.cache[cache_key] = (datetime.now(), result)
                        return result
            
            return {"value": 50, "classification": "Neutral", "timestamp": datetime.now()}
        
        except Exception as e:
            logger.error(f"Error fetching Fear & Greed Index: {e}")
            return {"value": 50, "classification": "Neutral", "timestamp": datetime.now()}
    
    async def get_crypto_news_sentiment(self, symbol: str = "BTC") -> Dict:
        """
        Get recent crypto news sentiment
        
        Uses CryptoCompare free API
        """
        try:
            # Check cache
            cache_key = f"news_{symbol}"
            if cache_key in self.cache:
                cached_time, cached_data = self.cache[cache_key]
                if datetime.now() - cached_time < timedelta(seconds=self.cache_duration):
                    return cached_data
            
            session = await self._get_session()
            
            # CryptoCompare News API (free, no key needed)
            url = f"https://min-api.cryptocompare.com/data/v2/news/?categories={symbol}"
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data and 'Data' in data:
                        news_items = data['Data'][:10]  # Last 10 news
                        
                        # Simple sentiment analysis based on keywords
                        positive_keywords = [
                            'bullish', 'surge', 'rally', 'gains', 'rises', 'breakthrough',
                            'adoption', 'partnership', 'upgrade', 'all-time high', 'ath',
                            'institutional', 'milestone', 'success'
                        ]
                        
                        negative_keywords = [
                            'bearish', 'crash', 'plunge', 'falls', 'drops', 'concern',
                            'regulation', 'ban', 'hack', 'scam', 'warning', 'risk',
                            'lawsuit', 'investigation', 'decline'
                        ]
                        
                        positive_count = 0
                        negative_count = 0
                        
                        for item in news_items:
                            title = item.get('title', '').lower()
                            body = item.get('body', '').lower()
                            text = title + " " + body
                            
                            positive_count += sum(1 for word in positive_keywords if word in text)
                            negative_count += sum(1 for word in negative_keywords if word in text)
                        
                        total_mentions = positive_count + negative_count
                        if total_mentions > 0:
                            sentiment_score = (positive_count - negative_count) / total_mentions
                        else:
                            sentiment_score = 0
                        
                        result = {
                            "sentiment_score": sentiment_score,  # -1 to +1
                            "positive_mentions": positive_count,
                            "negative_mentions": negative_count,
                            "news_count": len(news_items),
                            "timestamp": datetime.now()
                        }
                        
                        # Cache result
                        self.cache[cache_key] = (datetime.now(), result)
                        return result
            
            return {"sentiment_score": 0, "positive_mentions": 0, "negative_mentions": 0, "news_count": 0}
        
        except Exception as e:
            logger.error(f"Error fetching news sentiment: {e}")
            return {"sentiment_score": 0, "positive_mentions": 0, "negative_mentions": 0, "news_count": 0}
    
    async def get_coingecko_sentiment(self, coin_id: str = "bitcoin") -> Dict:
        """
        Get sentiment data from CoinGecko
        
        Includes social metrics and developer activity
        """
        try:
            # Check cache
            cache_key = f"coingecko_{coin_id}"
            if cache_key in self.cache:
                cached_time, cached_data = self.cache[cache_key]
                if datetime.now() - cached_time < timedelta(seconds=self.cache_duration):
                    return cached_data
            
            session = await self._get_session()
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract sentiment indicators
                    sentiment_votes_up = data.get('sentiment_votes_up_percentage', 50)
                    sentiment_votes_down = data.get('sentiment_votes_down_percentage', 50)
                    
                    # Community data
                    community = data.get('community_data', {})
                    twitter_followers = community.get('twitter_followers', 0)
                    
                    # Market data
                    market_data = data.get('market_data', {})
                    price_change_24h = market_data.get('price_change_percentage_24h', 0)
                    
                    result = {
                        "sentiment_up": sentiment_votes_up,
                        "sentiment_down": sentiment_votes_down,
                        "twitter_followers": twitter_followers,
                        "price_change_24h": price_change_24h,
                        "timestamp": datetime.now()
                    }
                    
                    # Cache result
                    self.cache[cache_key] = (datetime.now(), result)
                    return result
            
            return {"sentiment_up": 50, "sentiment_down": 50, "twitter_followers": 0, "price_change_24h": 0}
        
        except Exception as e:
            logger.error(f"Error fetching CoinGecko sentiment: {e}")
            return {"sentiment_up": 50, "sentiment_down": 50, "twitter_followers": 0, "price_change_24h": 0}
    
    async def get_combined_sentiment(self, symbol: str = "BTC") -> SentimentSignal:
        """
        Combine all sentiment sources into one signal
        
        Returns:
            SentimentSignal with overall market sentiment
        """
        try:
            # Fetch all sentiment sources
            fng = await self.get_fear_greed_index()
            news = await self.get_crypto_news_sentiment(symbol)
            
            # Map symbol to CoinGecko ID
            coin_map = {"BTC": "bitcoin", "ETH": "ethereum", "NEAR": "near", "PENGU": "pengu"}
            coin_id = coin_map.get(symbol, "bitcoin")
            coingecko = await self.get_coingecko_sentiment(coin_id)
            
            # Calculate combined sentiment score
            scores = []
            sources = []
            
            # Fear & Greed (inverse - fear is bullish)
            fng_value = fng.get('value', 50)
            fng_score = (50 - fng_value) / 50  # Convert to -1 to +1 (inverted)
            scores.append(fng_score * 1.5)  # Weight: 1.5x
            sources.append(f"Fear&Greed={fng_value} ({fng.get('classification')})")
            
            # News sentiment
            news_score = news.get('sentiment_score', 0)
            if news.get('news_count', 0) > 0:
                scores.append(news_score)  # Weight: 1.0x
                sources.append(f"News={news.get('positive_mentions')}/{news.get('negative_mentions')} pos/neg")
            
            # CoinGecko sentiment
            cg_up = coingecko.get('sentiment_up', 50)
            cg_score = (cg_up - 50) / 50  # Convert to -1 to +1
            scores.append(cg_score * 0.8)  # Weight: 0.8x
            sources.append(f"Community={cg_up:.0f}% bullish")
            
            # Calculate weighted average
            combined_score = sum(scores) / len(scores) if scores else 0
            combined_score = max(-1.0, min(1.0, combined_score))  # Clamp to -1 to +1
            
            # Determine sentiment
            if combined_score > 0.3:
                sentiment = "bullish"
                confidence = min(1.0, combined_score)
                reason = "Positive market sentiment across multiple sources"
            elif combined_score < -0.3:
                sentiment = "bearish"
                confidence = min(1.0, abs(combined_score))
                reason = "Negative market sentiment across multiple sources"
            else:
                sentiment = "neutral"
                confidence = 0.5
                reason = "Mixed or neutral market sentiment"
            
            return SentimentSignal(
                sentiment=sentiment,
                score=combined_score,
                confidence=confidence,
                reason=reason,
                sources=sources
            )
        
        except Exception as e:
            logger.error(f"Error in combined sentiment analysis: {e}")
            return SentimentSignal("neutral", 0.0, 0.3, f"Error: {e}", [])
