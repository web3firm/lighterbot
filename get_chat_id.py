#!/usr/bin/env python3
"""
Helper script to get your Telegram Chat ID
Run this after messaging your bot on Telegram
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv('TELEGRAM_BOT_TOKEN')

if not token:
    print("❌ Error: TELEGRAM_BOT_TOKEN not found in .env")
    print("Please add your bot token to .env first")
    sys.exit(1)

print("🔍 Fetching recent messages...")
print("")

try:
    response = requests.get(f"https://api.telegram.org/bot{token}/getUpdates")
    data = response.json()
    
    if not data.get('ok'):
        print("❌ Error fetching updates")
        print(data)
        sys.exit(1)
    
    updates = data.get('result', [])
    
    if not updates:
        print("❌ No messages found!")
        print("")
        print("Please:")
        print("1. Open Telegram")
        print("2. Search for your bot")
        print("3. Send /start to your bot")
        print("4. Run this script again")
        sys.exit(0)
    
    print("✅ Found messages! Your chat IDs:")
    print("")
    
    chat_ids = set()
    for update in updates:
        if 'message' in update:
            chat_id = update['message']['chat']['id']
            username = update['message']['chat'].get('username', 'N/A')
            first_name = update['message']['chat'].get('first_name', 'N/A')
            
            chat_ids.add(chat_id)
            print(f"  Chat ID: {chat_id}")
            print(f"  Username: @{username}")
            print(f"  Name: {first_name}")
            print("")
    
    if chat_ids:
        print("📝 Add this to your .env file:")
        print("")
        print(f"  TELEGRAM_CHAT_ID={list(chat_ids)[0]}")
        print("")
        print("(Use this to restrict bot access to only your chat)")
        
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
