import asyncio
import os
import logging
from dotenv import load_dotenv
import lighter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ConnectionTest")

async def test_connection():
    load_dotenv()
    
    api_url = os.getenv('LIGHTER_API_URL')
    private_key = os.getenv('LIGHTER_API_PRIVATE_KEY')
    key_index = int(os.getenv('LIGHTER_API_KEY_INDEX', '0'))
    account_index = int(os.getenv('LIGHTER_ACCOUNT_INDEX', '0'))
    
    logger.info(f"Testing connection to: {api_url}")
    logger.info(f"Account Index: {account_index} | Key Index: {key_index}")
    
    if not private_key or private_key == "0xYourPrivateKeyHere":
        logger.error("❌ Private key not configured in .env!")
        return

    try:
        # 1. Init API Client
        config = lighter.Configuration(host=api_url)
        api_client = lighter.ApiClient(configuration=config)
        logger.info("✅ API Client created")
        
        # 2. Init Signer (Updated for correct SDK signature)
        signer = lighter.SignerClient(
            url=api_url,
            account_index=account_index,
            api_private_keys={key_index: private_key}
        )
        logger.info("✅ Signer Client created")
        
        # 3. Check Credentials
        logger.info("🔄 Verifying credentials on-chain...")
        err = signer.check_client()
        
        if err:
            logger.error(f"❌ Connection FAILED: {err}")
            logger.error("Possible causes:")
            logger.error("- Wrong Private Key")
            logger.error("- Wrong Account Index or API Key Index")
            logger.error("- Public Key is not registered on Lighter Protocol")
        else:
            logger.info("✅ SUCCESS! Credentials are valid.")
            
            # 4. Try to fetch account
            account_api = lighter.AccountApi(api_client)
            result = await account_api.account(by="index", value=str(account_index))
           
            if result.accounts:
                acc = result.accounts[0]
                val = acc.total_asset_value if hasattr(acc, 'total_asset_value') else 'Unknown'
                logger.info(f"   Account Balance: ${val}")
            else:
                logger.warning("   Connected but no account data found (New account?)")

    except Exception as e:
        logger.error(f"❌ Exception during connection: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_connection())
