"""
Quick script to reset kill switch for testing
USE WITH CAUTION - Only for test environments
"""
import asyncio
from app.bot import LighterBot

async def main():
    bot = LighterBot()
    await bot.initialize()
    
    # Get current equity
    account = await bot.lighter_client.get_account_state()
    current_equity = float(account.get('account_value', 0))
    
    print(f"Current equity: ${current_equity:.2f}")
    print(f"Kill switch triggered: {bot.risk_manager.kill_switch.is_triggered()}")
    
    if bot.risk_manager.kill_switch.is_triggered():
        confirm = input("\n⚠️  Reset kill switch and set NEW session start equity? (yes/no): ")
        if confirm.lower() == 'yes':
            bot.risk_manager.kill_switch.reset()
            bot.risk_manager.initialize_session(current_equity)
            print(f"✅ Kill switch reset!")
            print(f"✅ New session start equity: ${current_equity:.2f}")
        else:
            print("❌ Cancelled")
    else:
        print("✅ Kill switch not triggered")

if __name__ == "__main__":
    asyncio.run(main())
