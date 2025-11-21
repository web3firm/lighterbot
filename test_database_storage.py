"""
Test script to verify PostgreSQL storage is working correctly
Run: python test_database_storage.py
"""

import os
import asyncio
import json
from datetime import datetime, timezone
from app.database.db_manager import DatabaseManager

async def test_database_storage():
    """Test complete trade lifecycle in database"""
    
    print("🧪 Testing PostgreSQL Storage System")
    print("=" * 60)
    
    # Check environment
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ DATABASE_URL not set in environment")
        print("   Run: export DATABASE_URL=postgresql://user:pass@host:5432/lighterbot")
        return False
    
    print(f"✅ Database URL configured")
    
    # Initialize database manager
    print("\n1️⃣  Connecting to database...")
    try:
        db_manager = DatabaseManager(db_url)
        await db_manager.connect()
        print("✅ Connected successfully")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False
    
    # Test trade insertion
    print("\n2️⃣  Testing trade insertion...")
    trade_id = f"test_{int(datetime.now(timezone.utc).timestamp())}"
    trade_data = {
        'trade_id': trade_id,
        'symbol': 'ETH-USD',
        'strategy': 'test_strategy',
        'side': 'long',
        'entry_price': 2500.50,
        'size': 0.1,
        'leverage': 5,
        'entry_time': datetime.now(timezone.utc).isoformat(),
        'indicators': {
            'rsi': 65.5,
            'macd': 12.3,
            'adx': 28.7,
            'atr': 45.2,
            'ema_fast': 2495.0,
            'ema_slow': 2480.0,
            'bb_position': 0.75,
            'volume_ratio': 1.5,
            'price_change_1h': 1.2,
            'price_change_4h': 2.5,
            'price_change_24h': 5.8,
            'signal_strength': 8
        },
        'ml_prediction': 1,
        'ml_confidence': 0.85
    }
    
    try:
        success = await db_manager.insert_trade(trade_data)
        if success:
            print(f"✅ Trade inserted: {trade_id}")
        else:
            print("❌ Trade insertion failed")
            return False
    except Exception as e:
        print(f"❌ Trade insertion error: {e}")
        return False
    
    # Test trade update (exit)
    print("\n3️⃣  Testing trade exit update...")
    exit_data = {
        'exit_price': 2550.75,
        'exit_time': datetime.now(timezone.utc).isoformat(),
        'pnl_usd': 5.025,  # (2550.75 - 2500.50) * 0.1
        'pnl_pct': 2.01,   # ((2550.75 - 2500.50) / 2500.50) * 100
        'fees_usd': 0.15,
        'duration_seconds': 300,
        'exit_reason': 'Take profit hit'
    }
    
    try:
        success = await db_manager.update_trade_exit(trade_id, exit_data)
        if success:
            print(f"✅ Trade updated with exit data")
        else:
            print("❌ Trade update failed")
            return False
    except Exception as e:
        print(f"❌ Trade update error: {e}")
        return False
    
    # Verify trade retrieval
    print("\n4️⃣  Testing trade retrieval...")
    try:
        trades = await db_manager.get_recent_trades(limit=1)
        if trades and trades[0]['trade_id'] == trade_id:
            print(f"✅ Trade retrieved successfully")
            print(f"   Entry: ${trades[0]['entry_price']:.2f}")
            print(f"   Exit:  ${trades[0]['exit_price']:.2f}")
            print(f"   PnL:   ${trades[0]['pnl_usd']:.2f} ({trades[0]['pnl_pct']:.2f}%)")
            print(f"   Indicators stored: {len(trades[0].get('indicators', {}))} fields")
        else:
            print("❌ Trade retrieval failed")
            return False
    except Exception as e:
        print(f"❌ Trade retrieval error: {e}")
        return False
    
    # Test ML auto-trainer integration
    print("\n5️⃣  Testing ML AutoTrainer database integration...")
    try:
        from ml.auto_trainer import AutoTrainer
        
        trainer = AutoTrainer(db_url=db_url, min_trades=1)
        print("✅ AutoTrainer initialized with database URL")
        
        # Count trades
        trade_count = trainer._count_trades()
        print(f"✅ Trade count query successful: {trade_count} completed trades")
        
        # Load trades
        trades = trainer._load_all_trades()
        print(f"✅ Trade loading successful: {len(trades)} trades loaded")
        
        if len(trades) > 0:
            print(f"   Sample trade: {trades[0].get('symbol')} {trades[0].get('side')}")
            print(f"   Has indicators: {'Yes' if trades[0].get('indicators') else 'No'}")
        
    except Exception as e:
        print(f"❌ AutoTrainer integration error: {e}")
        return False
    
    # Cleanup test trade
    print("\n6️⃣  Cleaning up test data...")
    try:
        async with db_manager.pool.acquire() as conn:
            await conn.execute("DELETE FROM trades WHERE trade_id = $1", trade_id)
        print(f"✅ Test trade deleted: {trade_id}")
    except Exception as e:
        print(f"⚠️  Cleanup warning: {e}")
    
    # Close connection
    await db_manager.close()
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("\n🎉 PostgreSQL storage system is working correctly")
    print("   - Trades can be saved to database")
    print("   - Exit data can be updated")
    print("   - ML trainer can read from database")
    print("   - Ready for production use!")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    # Run tests
    success = asyncio.run(test_database_storage())
    
    if not success:
        print("\n❌ Tests failed - please check your database configuration")
        print("   1. Is PostgreSQL running?")
        print("   2. Is DATABASE_URL set correctly?")
        print("   3. Did you run the schema.sql?")
        exit(1)
    
    exit(0)
