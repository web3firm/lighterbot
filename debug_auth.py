import asyncio
import os
import logging
from dotenv import load_dotenv
import lighter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AuthDebug")

async def debug_auth():
    load_dotenv()
    
    api_url = os.getenv('LIGHTER_API_URL')
    private_key = os.getenv('LIGHTER_API_PRIVATE_KEY')
    api_key_index = int(os.getenv('LIGHTER_API_KEY_INDEX', '0'))
    
    logger.info(f"Target API Key Index from env: {api_key_index}")
    
    if not private_key:
        logger.error("❌ Private key not found")
        return

    try:
        from eth_account import Account
        # Add '0x' prefix if missing
        pk = private_key if private_key.startswith('0x') else f'0x{private_key}'
        account = Account.from_key(pk)
        logger.info(f"🔑 Private Key resolves to Wallet Address: {account.address}")
        logger.info("👉 Check if this matches the address in your Lighter Protocol dashboard!")
    except Exception as e:
        logger.warning(f"⚠️ Could not derive address from private key: {e}")


    # Try Account Indices 0 to 4
    for acc_idx in range(5):
        logger.info(f"--- Testing Account Index {acc_idx} ---")
        try:
            # Init Signer with current account index attempt
            signer = lighter.SignerClient(
                url=api_url,
                account_index=acc_idx,
                api_private_keys={api_key_index: private_key}
            )
            
            err = signer.check_client()
            
            if err:
                logger.warning(f"❌ Failed for Index {acc_idx}: {err}")
            else:
                logger.info(f"✅ SUCCESS! Account Index {acc_idx} is valid for API Key Index {api_key_index}")
                print(f"\n🎉 FOUND CORRECT CONFIGURATION:\nLIGHTER_ACCOUNT_INDEX={acc_idx}\n")
                return

        except Exception as e:
            logger.error(f"❌ Exception testing index {acc_idx}: {e}")

    logger.error("\n❌ Could not find a valid account index. Please check your Private Key and API Key Index.")

if __name__ == "__main__":
    asyncio.run(debug_auth())
